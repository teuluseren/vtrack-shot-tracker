"""Exercise the compiled auto-start logic with a harmless, uniquely named app."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "Windows process-launch integration")
class ShotForgeAutoStartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix="shotforge auto start ")
        cls.addClassCleanup(cls.folder.cleanup)
        cls.root = Path(cls.folder.name)
        compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        if not compiler.exists():
            raise unittest.SkipTest(".NET Framework compiler unavailable")
        harness = cls.root / "Harness.cs"
        harness.write_text('''using System; using System.IO; using System.Threading;
public static class Harness {
    public static int Main() {
        try {
            using(var job = new OwnedJob())
            using(var app = Program.EnsureShotForge(job)) {
                if(app != null) {
                    File.WriteAllText(Path.Combine(Program.Root,"owned"), app.Id.ToString());
                    while(!File.Exists(Path.Combine(Program.Root,"release"))) Thread.Sleep(30);
                    Program.RequestAppClose(app);
                }
            }
            return 0;
        }
        catch (Exception e) { Console.WriteLine(e.Message); return 2; }
    }
}''')
        cls.harness = cls.root / "Harness.exe"
        subprocess.run([str(compiler), "/nologo", "/target:exe", "/main:Harness",
                        "/out:" + str(cls.harness), "/reference:System.Windows.Forms.dll",
                        "/reference:System.Drawing.dll", "/reference:System.Web.Extensions.dll",
                        str(ROOT / "shotforge_vtrack_connector/CompatibilityHost.cs"), str(harness)],
                       check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        stub = cls.root / "Stub.cs"
        stub.write_text('''using System; using System.Diagnostics; using System.IO; using System.Windows.Forms;
public static class Stub {
    [STAThread]
    public static void Main() {
        string dir=AppDomain.CurrentDomain.BaseDirectory;
        var form = new Form { Opacity=0, FormBorderStyle=FormBorderStyle.FixedToolWindow };
        form.Shown += delegate { File.AppendAllText(Path.Combine(dir,"starts.txt"), Process.GetCurrentProcess().Id+"\\n"); };
        form.FormClosed += delegate { File.WriteAllText(Path.Combine(dir,"stopped"), "yes"); };
        var timer = new Timer { Interval=30 };
        timer.Tick += delegate { if(File.Exists(Path.Combine(dir,"stop"))) form.Close(); };
        timer.Start();
        Application.Run(form);
    }
}''')
        cls.stub = cls.root / ("ShotForgeStub_" + uuid.uuid4().hex + ".exe")
        subprocess.run([str(compiler), "/nologo", "/target:winexe", "/reference:System.Windows.Forms.dll",
                        "/out:" + str(cls.stub), str(stub)],
                       check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

    def setUp(self):
        for name in ("stop", "stopped", "starts.txt", "owned", "release"):
            (self.root / name).unlink(missing_ok=True)
        self.processes = []
        self.addCleanup(self.stop_processes)

    def stop_processes(self):
        (self.root / "stop").touch()
        (self.root / "release").touch()
        for process in self.processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        time.sleep(.1)

    def until_file(self, name):
        deadline = time.monotonic() + 5
        while not (self.root / name).exists() and time.monotonic() < deadline:
            time.sleep(.03)
        self.assertTrue((self.root / name).exists(), name)

    def start_process(self, executable):
        process = subprocess.Popen([str(executable)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        self.processes.append(process)
        return process

    def run_launcher(self, **config):
        (self.root / "connector.json").write_text(json.dumps(config))
        # The independent app may inherit output handles. A file keeps its
        # lifetime from holding subprocess.communicate's capture pipe open.
        with tempfile.TemporaryFile() as output:
            result = subprocess.run([str(self.harness)], stdout=output, stderr=output, timeout=5,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            output.seek(0)
            result.stdout = output.read().decode(errors="replace")
            return result

    def test_owned_app_starts_once_and_closes_gracefully_with_owner(self):
        # An absolute path containing spaces must work without manual quoting.
        config = {"shotforge_exe": str(self.stub)}
        (self.root / "connector.json").write_text(json.dumps(config))
        owner = self.start_process(self.harness)
        self.until_file("starts.txt")
        self.assertEqual(self.run_launcher(**config).returncode, 0)
        self.assertEqual(len((self.root / "starts.txt").read_text().splitlines()), 1)
        self.assertFalse((self.root / "stopped").exists())
        self.assertIn("already running", (self.root / "logs/launcher.log").read_text())
        (self.root / "release").touch()
        self.assertEqual(owner.wait(timeout=5), 0)
        self.until_file("stopped")

    def test_preexisting_app_stays_open_when_connector_exits(self):
        app = self.start_process(self.stub)
        self.until_file("starts.txt")
        self.assertEqual(self.run_launcher(shotforge_exe=str(self.stub)).returncode, 0)
        self.assertIsNone(app.poll())
        self.assertFalse((self.root / "owned").exists())
        self.assertEqual(len((self.root / "starts.txt").read_text().splitlines()), 1)

    def test_disabled_autostart_does_not_require_installed_app(self):
        result = self.run_launcher(launch_shotforge=False, shotforge_exe=str(self.root / "missing.exe"))
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.root / "starts.txt").exists())

    def test_remote_target_does_not_start_local_app(self):
        result = self.run_launcher(shotforge_host="192.0.2.10", shotforge_exe=str(self.stub))
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.root / "starts.txt").exists())

    def test_missing_app_reports_configuration_fix(self):
        result = self.run_launcher(shotforge_exe=str(self.root / "missing.exe"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("shotforge_exe", result.stdout)


if __name__ == "__main__":
    unittest.main()
