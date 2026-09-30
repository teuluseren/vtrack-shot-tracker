"""Windows bundle smoke tests on a private desktop; no user windows or real shots."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

BUNDLE = Path(os.environ.get("SHOTFORGE_CONNECTOR_TEST_BUNDLE") or
              Path(__file__).resolve().parents[1] / "shotforge_vtrack_connector" / "dist")


class StartupInfo(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("reserved", wintypes.LPWSTR),
                ("desktop", wintypes.LPWSTR), ("title", wintypes.LPWSTR),
                ("x", wintypes.DWORD), ("y", wintypes.DWORD),
                ("width", wintypes.DWORD), ("height", wintypes.DWORD),
                ("xchars", wintypes.DWORD), ("ychars", wintypes.DWORD),
                ("fill", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("show", wintypes.WORD), ("reserved_size", wintypes.WORD),
                ("reserved_ptr", ctypes.c_void_p), ("stdin", wintypes.HANDLE),
                ("stdout", wintypes.HANDLE), ("stderr", wintypes.HANDLE)]


class ProcessInfo(ctypes.Structure):
    _fields_ = [("process", wintypes.HANDLE), ("thread", wintypes.HANDLE),
                ("pid", wintypes.DWORD), ("tid", wintypes.DWORD)]


class DesktopProcess:
    """subprocess.STARTUPINFO does not expose lpDesktop; use CreateProcessW."""
    def __init__(self, kernel, executable, desktop):
        self.kernel = kernel
        startup = StartupInfo()
        startup.cb = ctypes.sizeof(startup)
        startup.desktop = desktop
        info = ProcessInfo()
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(executable)]))
        if not kernel.CreateProcessW(str(executable), command, None, None, False, 0, None, str(executable.parent), ctypes.byref(startup), ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        self.handle = info.process
        self.pid = info.pid
        kernel.CloseHandle(info.thread)

    def poll(self):
        code = wintypes.DWORD()
        self.kernel.GetExitCodeProcess(self.handle, ctypes.byref(code))
        return None if code.value == 259 else code.value

    def wait(self, timeout):
        if self.kernel.WaitForSingleObject(self.handle, int(timeout * 1000)) != 0:
            raise TimeoutError("Process did not exit")
        return self.poll()

    def kill(self):
        self.kernel.TerminateProcess(self.handle, 1)


@unittest.skipUnless(os.name == "nt" and (BUNDLE / "GSPLauncher.exe").exists(), "Build the Windows connector bundle to run launcher smoke tests")
class LauncherTests(unittest.TestCase):
    def setUp(self):
        # Private desktops hide test windows, but process names remain visible
        # across desktops. A live toolkit can attach to a test GSPro process.
        try:
            processes = subprocess.check_output(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 "Get-Process -ErrorAction Stop | Select-Object -ExpandProperty ProcessName"],
                text=True, errors="replace", stderr=subprocess.STDOUT, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError):
            self.skipTest("Cannot verify that live simulator processes are closed")
        if any(name.strip().casefold() in ("lpgagent", "gspro", "gsplauncher", "gspconnect")
               for name in processes.splitlines()):
            self.skipTest("Close VTrackToolKit and GSPro/connector before running launcher smoke tests")
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.user.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
        self.user.CreateDesktopW.restype = wintypes.HANDLE
        self.user.CloseDesktop.argtypes = [wintypes.HANDLE]
        self.callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self.user.EnumDesktopWindows.argtypes = [wintypes.HANDLE, self.callback_type, wintypes.LPARAM]
        self.user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(StartupInfo), ctypes.POINTER(ProcessInfo)]
        self.kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.desktop_name = "ShotForgeTest_" + uuid.uuid4().hex
        self.desktop = self.user.CreateDesktopW(self.desktop_name, None, None, 0, 0x01FF, None)
        if not self.desktop:
            raise ctypes.WinError(ctypes.get_last_error())
        self.addCleanup(self.user.CloseDesktop, self.desktop)
        self.folder = tempfile.TemporaryDirectory(prefix="shotforge connector test ")
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        for name in ("GSPLauncher.exe", "GSPro.exe", "GSPconnect.exe", "bridge.py"):
            shutil.copyfile(BUNDLE / name, self.root / name)
        python = sys.executable
        if (BUNDLE / "python" / "python.exe").exists():
            shutil.copytree(BUNDLE / "python", self.root / "python")
            python = "python\\python.exe"
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            self.port = reservation.getsockname()[1]
        self.sf = socket.socket()
        self.sf.bind(("127.0.0.1", 0))
        self.sf.listen()
        self.sf.settimeout(5)
        self.addCleanup(self.sf.close)
        config = {"python": python, "listen_port": self.port,
                  "launch_shotforge": False,
                  "shotforge_port": self.sf.getsockname()[1]}
        self.configure_apps(config)
        (self.root / "connector.json").write_text(json.dumps(config), encoding="utf-8")
        self.process = self.launch()
        self.addCleanup(self.stop_launcher)

    def configure_apps(self, config):
        pass

    def launch(self):
        process = DesktopProcess(self.kernel, self.root / "GSPLauncher.exe", self.desktop_name)
        self.addCleanup(self.kernel.CloseHandle, process.handle)
        return process

    def stop_launcher(self):
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=5)
        # After a successful handoff GSPro intentionally outlives the launcher.
        path = self.root / "logs" / "launcher.log"
        if path.exists():
            match = re.search(r"GSPro compatibility host PID=(\d+)", path.read_text())
            if match:
                handle = self.kernel.OpenProcess(0x00100001, False, int(match[1]))
                if handle:
                    self.kernel.TerminateProcess(handle, 1)
                    self.kernel.WaitForSingleObject(handle, 5000)
                    self.kernel.CloseHandle(handle)
        # Job termination is asynchronous; wait for executable file locks to clear.
        time.sleep(.2)

    def until(self, predicate, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(.05)
        logs = "\n".join(p.read_text(errors="replace") for p in (self.root / "logs").glob("*.log"))
        self.fail("Launcher smoke condition timed out.\n" + logs)

    def windows(self, pid):
        found = []

        @self.callback_type
        def visit(hwnd, unused):
            owner = wintypes.DWORD()
            self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid and self.user.IsWindowVisible(hwnd):
                found.append(hwnd)
            return True

        self.user.EnumDesktopWindows(self.desktop, visit, 0)
        return found

    def status(self):
        for path in (self.root / "runtime").glob("*.json"):
            try:
                value = json.loads(path.read_text())
                if value.get("listening"):
                    return value
            except (OSError, ValueError):
                pass
        return None

    def ready(self):
        self.until(lambda: self.windows(self.process.pid))
        state = self.until(self.status)

        def gspro_pid():
            path = self.root / "logs" / "launcher.log"
            if not path.exists():
                return None
            match = re.search(r"GSPro compatibility host PID=(\d+)", path.read_text())
            return int(match[1]) if match else None

        gspro = self.until(gspro_pid)
        self.until(lambda: self.windows(gspro))
        self.host_pid = gspro
        handles = [self.kernel.OpenProcess(0x00100001, False, pid) for pid in (state["pid"], gspro, state["parent_pid"])]
        for handle in handles:
            self.assertTrue(handle)
            self.addCleanup(self.kernel.CloseHandle, handle)
        # Regression: VTrack waits for launcher exit before it begins monitoring.
        self.assertEqual(self.process.wait(timeout=5), 0)
        for handle in handles:
            self.assertEqual(self.kernel.WaitForSingleObject(handle, 0), 258)
        return handles

    def assert_children_stopped(self, handles):
        self.process.wait(timeout=5)
        for handle in handles:
            self.assertEqual(self.kernel.WaitForSingleObject(handle, 5000), 0)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", self.port))

    def test_real_windows_relay_duplicate_start_and_graceful_stop(self):
        handles = self.ready()
        duplicate = self.launch()
        self.assertEqual(duplicate.wait(timeout=5), 0)
        self.assertTrue(self.windows(self.host_pid))
        with socket.create_connection(("127.0.0.1", self.port), timeout=5) as client:
            connection, _ = self.sf.accept()
            with connection:
                connection.settimeout(5)
                # Synthetic heartbeat, no ball data or real application endpoint.
                raw = b'{"ShotDataOptions":{"IsHeartBeat":true}}\0'
                client.sendall(raw)
                incoming = b""
                while len(incoming) < len(raw):
                    incoming += connection.recv(1024)
                self.assertEqual(incoming, raw)
                connection.sendall(b'{"Code":201,"Player":{"Club":"PT","Handed":"LH"}}\0')
                response = b""
                while b"\0" not in response:
                    response += client.recv(1024)
                self.assertEqual(json.loads(response.rstrip(b"\0"))["Player"]["Club"], "PT")
        self.user.PostMessageW(self.windows(self.host_pid)[0], 0x0010, 0, 0)
        self.assert_children_stopped(handles)

    def test_forced_gspro_exit_releases_bridge_after_handoff(self):
        handles = self.ready()
        self.kernel.TerminateProcess(handles[1], 1)
        self.assert_children_stopped(handles)


class OwnedAppLauncherTests(LauncherTests):
    """Use disposable app/toolkit processes; never touch the installed apps."""

    def configure_apps(self, config):
        source = self.root / "Stub.cs"
        source.write_text('''using System; using System.Diagnostics; using System.IO;
using System.Threading; using System.Windows.Forms;
static class Stub {
    [STAThread] static void Main(string[] args) {
        string dir=AppDomain.CurrentDomain.BaseDirectory;
        string name=Process.GetCurrentProcess().ProcessName;
        if(args.Length > 0) {
            File.WriteAllText(Path.Combine(dir,"helper.pid"), Process.GetCurrentProcess().Id.ToString());
            Thread.Sleep(Timeout.Infinite); return;
        }
        var form=new Form();
        form.Shown += delegate {
            File.WriteAllText(Path.Combine(dir,name+".pid"), Process.GetCurrentProcess().Id.ToString());
            if(name != "LPGAgent") Process.Start(new ProcessStartInfo {
                FileName=Application.ExecutablePath, Arguments="--helper", UseShellExecute=false });
        };
        form.FormClosed += delegate { File.WriteAllText(Path.Combine(dir,name+".closed"), "yes"); };
        Application.Run(form);
    }
}''')
        compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        app = self.root / ("ShotForgeStub_" + uuid.uuid4().hex + ".exe")
        self.app_name = app.stem
        subprocess.run([str(compiler), "/nologo", "/target:winexe", "/reference:System.Windows.Forms.dll",
                        "/out:" + str(app), str(source)], check=True, capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        toolkit = self.root / "LPGAgent.exe"
        shutil.copyfile(app, toolkit)
        self.toolkit = DesktopProcess(self.kernel, toolkit, self.desktop_name)
        self.addCleanup(self.cleanup_desktop_process, self.toolkit)
        self.until(lambda: (self.root / "LPGAgent.pid").exists())
        self.preexisting = "preexisting" in self._testMethodName
        if self.preexisting:
            process = DesktopProcess(self.kernel, app, self.desktop_name)
            self.addCleanup(self.cleanup_desktop_process, process)
            # Register cleanup immediately, even if a later assertion fails.
            self.addCleanup(self.cleanup_helper)
            self.until(lambda: (self.root / "helper.pid").exists())
        config.update(launch_shotforge=True, shotforge_exe=str(app))

    def cleanup_desktop_process(self, process):
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        self.kernel.CloseHandle(process.handle)

    def cleanup_helper(self):
        path = self.root / "helper.pid"
        if path.exists():
            handle = self.kernel.OpenProcess(0x00100001, False, int(path.read_text()))
            if handle:
                self.kernel.TerminateProcess(handle, 1)
                self.kernel.WaitForSingleObject(handle, 5000)
                self.kernel.CloseHandle(handle)

    def ready(self):
        handles = super().ready()
        self.until(lambda: (self.root / "helper.pid").exists())
        self.app_handles = []
        for name in (self.app_name + ".pid", "helper.pid"):
            handle = self.kernel.OpenProcess(0x00100001, False, int((self.root / name).read_text()))
            self.assertTrue(handle)
            self.addCleanup(self.kernel.CloseHandle, handle)
            self.assertEqual(self.kernel.WaitForSingleObject(handle, 0), 258)
            self.app_handles.append(handle)
        return handles if self.preexisting else handles + self.app_handles

    def test_vtrack_exit_closes_owned_app_and_helper(self):
        handles = self.ready()
        self.toolkit.kill()
        self.assert_children_stopped(handles)
        self.assertTrue((self.root / (self.app_name + ".closed")).exists(), "App should receive graceful close")

    def test_preexisting_app_survives_vtrack_exit(self):
        handles = self.ready()
        self.toolkit.kill()
        self.assert_children_stopped(handles)
        for handle in self.app_handles:
            self.assertEqual(self.kernel.WaitForSingleObject(handle, 0), 258)
        self.assertFalse((self.root / (self.app_name + ".closed")).exists())


if __name__ == "__main__":
    unittest.main()
