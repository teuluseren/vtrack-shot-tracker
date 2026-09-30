using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

// Built as GSPLauncher.exe, GSPro.exe and GSPconnect.exe. Independent compatibility
// hosts, not copies of either vendor executable. VTrack requires a launcher UI.
static class Program
{
    internal static readonly string Root = AppDomain.CurrentDomain.BaseDirectory;
    internal static readonly JavaScriptSerializer Json = new JavaScriptSerializer();

    [DllImport("user32.dll")]
    static extern bool SetWindowPos(IntPtr window, IntPtr after, int x, int y, int width, int height, uint flags);

    internal static bool PlaceWindowBehind(IntPtr window, IntPtr toolkitWindow)
    {
        if (window == IntPtr.Zero || toolkitWindow == IntPtr.Zero) return false;
        // Change only stacking order; keep position, size, focus and the impact
        // anchor's own stacking order intact.
        return SetWindowPos(window, toolkitWindow, 0, 0, 0, 0, 0x213);
    }

    internal static string Quote(string value)
    {
        // Windows CommandLineToArgvW quoting: ordinary path backslashes stay single.
        var output = new StringBuilder("\"");
        int slashes = 0;
        foreach (char c in value)
        {
            if (c == '\\') { slashes++; continue; }
            output.Append('\\', c == '"' ? slashes * 2 + 1 : slashes);
            output.Append(c);
            slashes = 0;
        }
        output.Append('\\', slashes * 2);
        return output.Append('"').ToString();
    }

    internal static void Log(string message)
    {
        try
        {
            Directory.CreateDirectory(Path.Combine(Root, "logs"));
            string path = Path.Combine(Root, "logs", "launcher.log");
            if (File.Exists(path) && new FileInfo(path).Length > 2000000)
                File.WriteAllText(path, "Log rotated\r\n");
            File.AppendAllText(path, DateTime.Now.ToString("s") + " " + message + Environment.NewLine);
        }
        catch (IOException) { }
    }

    // Null means the app belongs to the user, or automatic launch is disabled.
    internal static Process EnsureShotForge(OwnedJob job)
    {
        var config = Json.Deserialize<Dictionary<string, object>>(File.ReadAllText(Path.Combine(Root, "connector.json")));
        if (config.ContainsKey("launch_shotforge") && !Convert.ToBoolean(config["launch_shotforge"]))
        { Log("ShotForge automatic launch disabled."); return null; }
        string host = config.ContainsKey("shotforge_host") ? Convert.ToString(config["shotforge_host"]) : "127.0.0.1";
        if (host != "127.0.0.1" && host != "::1" && !String.Equals(host, "localhost", StringComparison.OrdinalIgnoreCase))
        { Log("ShotForge target is remote; no local app launch."); return null; }

        string configured = config.ContainsKey("shotforge_exe") ? Convert.ToString(config["shotforge_exe"]) : "";
        string executable = String.IsNullOrWhiteSpace(configured) ? null :
            Path.GetFullPath(Path.Combine(Root, Environment.ExpandEnvironmentVariables(configured)));
        // A configured app may have a different filename. Scope reuse to this
        // Windows session, without needing access to another process's memory.
        string processName = executable == null ? "ShotForge" : Path.GetFileNameWithoutExtension(executable);
        int session = Process.GetCurrentProcess().SessionId;
        foreach (var process in Process.GetProcessesByName(processName))
        {
            using (process)
            {
                try
                {
                    if (!process.HasExited && process.SessionId == session)
                    { Log("ShotForge already running; leaving ownership with user. PID=" + process.Id); return null; }
                }
                catch (InvalidOperationException) { }
                catch (System.ComponentModel.Win32Exception) { }
            }
        }
        if (executable == null)
        {
            string[] candidates = {
                Path.Combine(Path.GetPathRoot(Environment.SystemDirectory), "ShotForge", "ShotForge.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "ShotForge", "ShotForge.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "ShotForge", "ShotForge.exe")
            };
            foreach (string candidate in candidates)
                if (File.Exists(candidate)) { executable = candidate; break; }
        }
        if (executable == null || !File.Exists(executable))
            throw new FileNotFoundException("ShotForge was not found. Set shotforge_exe in connector.json to your ShotForge.exe, or set launch_shotforge to false and open it manually.");
        var app = job.StartApp(executable);
        Log("Started owned ShotForge PID=" + app.Id);
        return app;
    }

    internal static Process FindVTrack()
    {
        Process selected = null;
        int count = 0;
        int session = Process.GetCurrentProcess().SessionId;
        foreach (var process in Process.GetProcessesByName("LPGAgent"))
        {
            bool keep = false;
            try
            {
                if (!process.HasExited && process.SessionId == session)
                {
                    count++;
                    if (selected == null)
                    {
                        // Retain a process handle so PID reuse cannot change the owner.
                        IntPtr handle = process.Handle;
                        selected = process;
                        keep = true;
                    }
                }
            }
            catch (InvalidOperationException) { }
            catch (System.ComponentModel.Win32Exception) { }
            finally { if (!keep) process.Dispose(); }
        }
        if (count != 1 && selected != null) { selected.Dispose(); selected = null; }
        Log(selected == null ? "No unique VTrack process to watch; close the GSPro window to stop." :
            "Watching VTrack PID=" + selected.Id);
        return selected;
    }

    internal static void RequestAppClose(Process app)
    {
        if (app == null) return;
        try
        {
            if (!app.HasExited)
            {
                Log("Closing owned ShotForge PID=" + app.Id);
                app.CloseMainWindow();
                if (!app.WaitForExit(3000)) Log("ShotForge did not exit in 3 seconds; cleaning up its job.");
            }
        }
        catch (InvalidOperationException) { }
        catch (System.ComponentModel.Win32Exception ex) { Log("ShotForge close request failed: " + ex.Message); }
    }

    [STAThread]
    static int Main(string[] args)
    {
        if (String.Equals(Path.GetFileNameWithoutExtension(Application.ExecutablePath), "GSPconnect", StringComparison.OrdinalIgnoreCase))
            return RunBridgeHost(args);
        bool launcher = String.Equals(Path.GetFileNameWithoutExtension(Application.ExecutablePath), "GSPLauncher", StringComparison.OrdinalIgnoreCase);
        if (launcher)
        {
            try
            {
                using (Mutex.OpenExisting("Local\\ShotForgeVTrack_GSPro"))
                { Log("GSPro connector already running; duplicate launcher ignored."); return 0; }
            }
            catch (WaitHandleCannotBeOpenedException) { }
        }
        // One launcher per Windows session, including copies in other directories.
        bool created;
        using (var mutex = new Mutex(true, "Local\\ShotForgeVTrack_" + (launcher ? "Launcher" : "GSPro"), out created))
        {
            if (!created) { Log("Already running; duplicate invocation ignored."); return 0; }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new HostForm(launcher, args));
            return 0;
        }
    }

    static int RunBridgeHost(string[] args)
    {
        // A real GSPconnect process is part of VTrack's simulator-ready check.
        // This host owns the Python bridge; GSPro owns this host in another job.
        if (args.Length != 2 || args[0] != "--status-file") return 2;
        try
        {
            var config = Json.Deserialize<Dictionary<string, object>>(File.ReadAllText(Path.Combine(Root, "connector.json")));
            string python = config.ContainsKey("python") ? Convert.ToString(config["python"]) : "python.exe";
            if (python.IndexOf('\\') >= 0 || python.IndexOf('/') >= 0)
                python = Path.GetFullPath(Path.Combine(Root, python));
            using (var job = new OwnedJob())
            using (var child = new Process { StartInfo = new ProcessStartInfo {
                FileName = python, WorkingDirectory = Root, UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardInput = true,
                Arguments = "-u " + Quote(Path.Combine(Root, "bridge.py")) + " --config " +
                    Quote(Path.Combine(Root, "connector.json")) + " --status-file " + Quote(args[1]) + " --parent-stdin"
            }})
            {
                child.Start();
                try { job.Add(child); }
                catch { if (!child.HasExited) child.Kill(); throw; }
                Log("GSPconnect owns Python bridge PID=" + child.Id);
                using (var stop = new ManualResetEvent(false))
                {
                    var watcher = new Thread(delegate() {
                        try { Console.OpenStandardInput().ReadByte(); stop.Set(); }
                        catch (ObjectDisposedException) { }
                        catch (IOException) { }
                    });
                    watcher.IsBackground = true;
                    watcher.Start();
                    while (!child.HasExited && !stop.WaitOne(100)) { }
                    if (!child.HasExited) { child.StandardInput.Close(); child.WaitForExit(1200); }
                    return child.HasExited ? child.ExitCode : 0;
                }
            }
        }
        catch (Exception ex) { Log("GSPconnect ERROR " + ex.Message); return 2; }
    }
}

sealed class HostForm : Form
{
    readonly bool launcher;
    readonly Label status;
    readonly System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer();
    Process bridge;
    Process gspro;
    Process shotforge;
    Process vtrack;
    ImpactWindowTracker impactTracker;
    OwnedJob job;
    string statusPath;
    DateTime started;
    bool ready;
    bool failed;
    EventWaitHandle handoffReady;
    bool handedOff;
    bool statusPlacedBehindToolkit;

    protected override bool ShowWithoutActivation { get { return true; } }

    void PlaceStatusBehindToolkit()
    {
        if (statusPlacedBehindToolkit || vtrack == null || vtrack.HasExited) return;
        vtrack.Refresh();
        if (Program.PlaceWindowBehind(Handle, vtrack.MainWindowHandle))
        {
            statusPlacedBehindToolkit = true;
            Program.Log("GSPro status window placed behind VTrack toolkit.");
        }
    }

    internal HostForm(bool isLauncher, string[] args)
    {
        launcher = isLauncher;
        Text = launcher ? "GSPLauncher - ShotForge VTrack Connector" : "GSPro";
        ClientSize = new Size(490, 185);
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        status = new Label { Left = 18, Top = 18, Width = 455, Height = 110,
            Text = "Starting ShotForge VTrack Connector..." };
        if (!launcher && args.Length == 2 && args[0] == "--ready-event")
            handoffReady = EventWaitHandle.OpenExisting(args[1]);
        Controls.Add(status);
        var close = new Button { Text = "Stop connector", Left = 18, Top = 140, Width = 130 };
        close.Click += delegate { Close(); };
        Controls.Add(close);
        var logs = new Button { Text = "Open logs", Left = 165, Top = 140, Width = 110 };
        logs.Click += delegate {
            string folder = Path.Combine(Program.Root, "logs");
            Directory.CreateDirectory(folder);
            Process.Start(new ProcessStartInfo(folder) { UseShellExecute = true });
        };
        Controls.Add(logs);
        // Shown + BeginInvoke ensures VTrack sees an initialized top-level window
        // before Python/config/network startup runs. Never hide it off-screen.
        Shown += delegate {
            Program.Log((launcher ? "GSPLauncher" : "GSPro") + " UI ready; PID=" + Process.GetCurrentProcess().Id + " HWND=" + Handle);
            BeginInvoke(new Action(launcher ? (Action)StartHandoff : StartConnector));
        };
        timer.Interval = 500;
        timer.Tick += delegate { Poll(); };
        FormClosed += delegate { StopChildren(); };
    }

    void StartHandoff()
    {
        try
        {
            // VTrack waits for the launcher to EXIT before it monitors GSPro.
            // Own startup children until GSPro reports its listener is ready.
            job = new OwnedJob();
            string eventName = "Local\\ShotForgeVTrackReady_" + Guid.NewGuid().ToString("N");
            handoffReady = new EventWaitHandle(false, EventResetMode.ManualReset, eventName);
            gspro = StartOwned(Path.Combine(Program.Root, "GSPro.exe"), "--ready-event " + Program.Quote(eventName), false);
            Program.Log("GSPro compatibility host PID=" + gspro.Id);
            started = DateTime.UtcNow;
            timer.Start();
        }
        catch (Exception ex) { Fail(ex.Message); }
    }

    Process StartOwned(string executable, string arguments, bool input)
    {
        var process = new Process { StartInfo = new ProcessStartInfo {
            FileName = executable, Arguments = arguments, WorkingDirectory = Program.Root,
            UseShellExecute = false, CreateNoWindow = input,
            RedirectStandardInput = input
        }};
        if (!process.Start()) throw new IOException("Failed to start " + executable);
        try { job.Add(process); }
        catch { if (!process.HasExited) process.Kill(); process.Dispose(); throw; }
        return process;
    }

    void StartConnector()
    {
        try
        {
            job = new OwnedJob();
            vtrack = Program.FindVTrack();
            PlaceStatusBehindToolkit();
            shotforge = Program.EnsureShotForge(job);
            var config = Program.Json.Deserialize<Dictionary<string, object>>(File.ReadAllText(Path.Combine(Program.Root, "connector.json")));
            string targetHost = config.ContainsKey("shotforge_host") ? Convert.ToString(config["shotforge_host"]) : "127.0.0.1";
            bool local = targetHost == "127.0.0.1" || targetHost == "::1" || String.Equals(targetHost, "localhost", StringComparison.OrdinalIgnoreCase);
            if (local && (!config.ContainsKey("follow_shotforge_window") || Convert.ToBoolean(config["follow_shotforge_window"])))
            {
                string appPath = config.ContainsKey("shotforge_exe") ? Convert.ToString(config["shotforge_exe"]) : "";
                string name = String.IsNullOrWhiteSpace(appPath) ? "ShotForge" : Path.GetFileNameWithoutExtension(Environment.ExpandEnvironmentVariables(appPath));
                impactTracker = new ImpactWindowTracker(this, name);
            }
            Directory.CreateDirectory(Path.Combine(Program.Root, "runtime"));
            statusPath = Path.Combine(Program.Root, "runtime", Guid.NewGuid().ToString("N") + ".json");
            bridge = StartOwned(Path.Combine(Program.Root, "GSPconnect.exe"), "--status-file " + Program.Quote(statusPath), true);
            Program.Log("GSPconnect started; PID=" + bridge.Id);
            started = DateTime.UtcNow;
            timer.Start();
        }
        catch (Exception ex) { Fail(ex.Message); }
    }

    void Poll()
    {
        if (failed) return;
        try
        {
            if (launcher)
            {
                if (gspro.HasExited) { Fail("GSPro compatibility host exited before startup completed. Check launcher.log."); return; }
                if (handoffReady.WaitOne(0) && (DateTime.UtcNow - started).TotalSeconds >= 1.5)
                {
                    // GSPro now owns the bridge job. The startup job must allow
                    // those processes to survive the launcher's normal exit.
                    job.AllowChildrenToContinue();
                    handedOff = true;
                    Program.Log("Handoff complete; GSPLauncher exiting for VTrack process monitoring.");
                    Close();
                }
                else if ((DateTime.UtcNow - started).TotalSeconds > 12)
                    Fail("GSPro did not become ready within 12 seconds. Check connector logs.");
                return;
            }
            if (vtrack != null && vtrack.HasExited)
            {
                Program.Log("VTrack exited; stopping connector and owned ShotForge.");
                Close();
                return;
            }
            if (bridge.HasExited) { Fail("Bridge exited (code " + bridge.ExitCode + "). Check logs/bridge.log for a port conflict or startup error."); return; }
            PlaceStatusBehindToolkit();
            if (impactTracker != null)
            {
                try { impactTracker.Update(); }
                catch (System.ComponentModel.Win32Exception ex)
                {
                    Program.Log("Impact window tracking unavailable: " + ex.Message);
                    impactTracker.Dispose();
                    impactTracker = null;
                }
            }
            Dictionary<string, object> state = null;
            try
            {
                if (File.Exists(statusPath))
                    state = Program.Json.Deserialize<Dictionary<string, object>>(File.ReadAllText(statusPath));
            }
            catch (IOException) { return; } // Atomic file replacement can race reads.
            if (state != null && Convert.ToInt32(state["parent_pid"]) == bridge.Id && Convert.ToBoolean(state["listening"]))
            {
                if (!ready)
                {
                    ready = true;
                    if (handoffReady != null) handoffReady.Set();
                    Program.Log("GSPro owns ready GSPconnect host; PID=" + bridge.Id);
                }
                status.Text = "ShotForge VTrack Connector\r\n" +
                    "VTrack: " + (Convert.ToBoolean(state["vtrack_connected"]) ? "connected" : "waiting for toolkit") + "\r\n" +
                    "ShotForge: " + (Convert.ToBoolean(state["shotforge_connected"]) ? "connected" : "waiting for connection") + "\r\n" +
                    "Shots forwarded: " + state["shots_forwarded"] + "   Responses: " + state["responses_received"] + "\r\n" + state["last_error"];
            }
            else if (!ready && (DateTime.UtcNow - started).TotalSeconds > 8)
                Fail("Bridge did not become ready within 8 seconds. Check logs/bridge.log.");
        }
        catch (Exception ex) { Fail(ex.Message); }
    }

    void Fail(string message)
    {
        failed = true;
        StopChildren();
        status.Text = "Connector could not start.\r\n" + message;
        Program.Log("ERROR " + message);
    }

    void StopChildren()
    {
        timer.Stop();
        if (impactTracker != null) { impactTracker.Dispose(); impactTracker = null; }
        // Only processes launched by this instance are owned. Never kill by name/port.
        if (bridge != null)
        {
            try { bridge.StandardInput.Close(); if (!bridge.HasExited) bridge.WaitForExit(1500); }
            catch (InvalidOperationException) { }
            catch (IOException) { }
        }
        Program.RequestAppClose(shotforge);
        if (job != null) { job.Dispose(); job = null; }
        if (shotforge != null) { shotforge.Dispose(); shotforge = null; }
        if (vtrack != null) { vtrack.Dispose(); vtrack = null; }
        if (bridge != null) { bridge.Dispose(); bridge = null; }
        if (gspro != null) { gspro.Dispose(); gspro = null; }
        if (handoffReady != null) { handoffReady.Dispose(); handoffReady = null; }
        if (launcher && !handedOff) Program.Log("Launcher stopped before handoff; startup children cleaned up.");
        if (statusPath != null)
        {
            try { File.Delete(statusPath); } catch (IOException) { }
        }
    }
}

// VTrack positions its replay relative to Process.MainWindowHandle for GSPro.
// Keep a transparent, unowned native window as that anchor; the status window
// is owned by it so .NET's main-window search excludes the status dialog.
// We only read ShotForge window geometry. No vendor windows/code are modified.
sealed class ImpactWindowTracker : NativeWindow, IDisposable
{
    readonly Form status;
    readonly string appName;
    readonly string courseName;
    readonly int session = Process.GetCurrentProcess().SessionId;
    IntPtr target;
    bool parked;
    bool disposed;
    [StructLayout(LayoutKind.Sequential)]
    struct Rect { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential)]
    struct Point { public int X, Y; }
    delegate bool EnumCallback(IntPtr window, IntPtr data);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumCallback callback, IntPtr data);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr window, out int pid);
    [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr window, uint command);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr window);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr window);
    [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr window, out Rect rect);
    [DllImport("user32.dll")] static extern bool ClientToScreen(IntPtr window, ref Point point);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr window, IntPtr after, int x, int y, int width, int height, uint flags);
    [DllImport("user32.dll")] static extern bool SetLayeredWindowAttributes(IntPtr window, uint color, byte alpha, uint flags);
    [DllImport("user32.dll", EntryPoint = "SetWindowLongPtrW", SetLastError = true)]
    static extern IntPtr SetWindowLongPtr(IntPtr window, int index, IntPtr value);

    internal ImpactWindowTracker(Form statusWindow, string processName, string courseProcessName = "ShotForgeCoursePlay")
    {
        status = statusWindow;
        appName = processName;
        courseName = courseProcessName;
    }

    IntPtr FindWindow(string name)
    {
        var pids = new HashSet<int>();
        foreach (var process in Process.GetProcessesByName(name))
        {
            using (process)
            {
                try { if (!process.HasExited && process.SessionId == session) pids.Add(process.Id); }
                catch (InvalidOperationException) { }
                catch (System.ComponentModel.Win32Exception) { }
            }
        }
        IntPtr best = IntPtr.Zero;
        long area = -1;
        EnumWindows(delegate(IntPtr window, IntPtr unused) {
            int pid;
            GetWindowThreadProcessId(window, out pid);
            if (!pids.Contains(pid) || !IsWindowVisible(window) || GetWindow(window, 4 /* GW_OWNER */) != IntPtr.Zero) return true;
            Rect rect;
            if (!GetClientRect(window, out rect)) return true;
            long size = (long)(rect.Right - rect.Left) * (rect.Bottom - rect.Top);
            if (size > area) { best = window; area = size; }
            return true;
        }, IntPtr.Zero);
        return best;
    }

    internal void Update()
    {
        if (disposed) return;
        // Course Play is a separate native game, not the Electron launcher.
        IntPtr next = FindWindow(courseName);
        if (next == IntPtr.Zero) next = FindWindow(appName);
        Rect client;
        var origin = new Point();
        bool visible = next != IntPtr.Zero && !IsIconic(next);
        if (visible && GetClientRect(next, out client) && ClientToScreen(next, ref origin) && client.Right > 0 && client.Bottom > 0)
        {
            if (Handle == IntPtr.Zero)
            {
                CreateHandle(new CreateParams {
                    Caption = "GSPro", Style = unchecked((int)0x80000000), // WS_POPUP, initially hidden
                    ExStyle = 0x080800A0, // NOACTIVATE | LAYERED | TOOLWINDOW | TRANSPARENT
                    X = origin.X, Y = origin.Y, Width = client.Right, Height = client.Bottom
                });
                if (!SetLayeredWindowAttributes(Handle, 0, 0, 2 /* LWA_ALPHA */))
                    throw new System.ComponentModel.Win32Exception();
                SetWindowLongPtr(status.Handle, -8 /* GWLP_HWNDPARENT */, Handle);
                if (GetWindow(status.Handle, 4) != Handle) throw new System.ComponentModel.Win32Exception();
                Program.Log("Impact replay anchor created; HWND=" + Handle);
            }
            // VTrack adds/subtracts CaptionHeight even for borderless windows.
            // Compensate so its normalized replay rectangle uses the app client.
            int caption = SystemInformation.CaptionHeight;
            if (!SetWindowPos(Handle, IntPtr.Zero, origin.X, origin.Y - caption,
                client.Right, client.Bottom + caption, 0x54 /* NOACTIVATE | NOZORDER | SHOWWINDOW */))
                throw new System.ComponentModel.Win32Exception();
            if (next != target || parked) Program.Log("Impact replay following ShotForge HWND=" + next);
            parked = false;
        }
        else if (Handle != IntPtr.Zero && !parked)
        {
            // Keep a main-window handle for VTrack, with its replay outside the
            // virtual desktop while the app is minimized/closed. No focus changes.
            var desktop = SystemInformation.VirtualScreen;
            SetWindowPos(Handle, IntPtr.Zero, desktop.Left - 10000, desktop.Top - 10000, 100, 100, 0x54);
            parked = true;
            Program.Log("Impact replay parked; ShotForge has no visible game window.");
        }
        target = next;
    }

    protected override void WndProc(ref Message message)
    {
        if (message.Msg == 0x10 /* WM_CLOSE */) { status.Close(); return; }
        if (message.Msg == 0x84 /* WM_NCHITTEST */) { message.Result = new IntPtr(-1); return; }
        if (message.Msg == 0x21 /* WM_MOUSEACTIVATE */) { message.Result = new IntPtr(3); return; }
        base.WndProc(ref message);
    }

    public void Dispose()
    {
        if (disposed) return;
        disposed = true;
        if (status.IsHandleCreated) SetWindowLongPtr(status.Handle, -8, IntPtr.Zero);
        if (Handle != IntPtr.Zero) DestroyHandle();
    }
}

// GSPro keeps its bridge and any app it launches in a kill-on-close job. The launcher uses a separate
// startup job, whose kill-on-close limit is removed only after a ready handoff.
sealed class OwnedJob : IDisposable
{
    IntPtr handle;
    [StructLayout(LayoutKind.Sequential)]
    struct BasicLimits {
        public long ProcessTime, JobTime; public uint Flags;
        public UIntPtr MinimumWorkingSet, MaximumWorkingSet;
        public uint ActiveProcessLimit; public UIntPtr Affinity;
        public uint PriorityClass, SchedulingClass;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct IoCounters { public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes; }
    [StructLayout(LayoutKind.Sequential)]
    struct Limits {
        public BasicLimits Basic; public IoCounters Io;
        public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
    }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateJobObject(IntPtr attributes, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetInformationJobObject(IntPtr job, int kind, ref Limits limits, uint size);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr handle);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct StartupInfo {
        public uint Size; public string Reserved, Desktop, Title;
        public uint X, Y, Width, Height, XChars, YChars, Fill, Flags;
        public ushort Show, ReservedSize;
        public IntPtr ReservedPointer, Input, Output, Error;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct ProcessInfo { public IntPtr Process, Thread; public uint Pid, Tid; }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool CreateProcess(string app, StringBuilder command, IntPtr processAttributes,
        IntPtr threadAttributes, bool inherit, uint flags, IntPtr environment, string directory,
        ref StartupInfo startup, out ProcessInfo process);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern uint ResumeThread(IntPtr thread);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool TerminateProcess(IntPtr process, uint code);

    internal Process StartApp(string executable)
    {
        // Assign before running any app code: Electron helpers must inherit the
        // same job, including if the compatibility host is forcibly terminated.
        var startup = new StartupInfo();
        startup.Size = (uint)Marshal.SizeOf(startup);
        ProcessInfo info;
        if (!CreateProcess(executable, new StringBuilder(Program.Quote(executable)), IntPtr.Zero,
            IntPtr.Zero, false, 4 /* CREATE_SUSPENDED */, IntPtr.Zero,
            Path.GetDirectoryName(executable), ref startup, out info))
            throw new System.ComponentModel.Win32Exception();
        Process app = null;
        try
        {
            if (!AssignProcessToJobObject(handle, info.Process)) throw new System.ComponentModel.Win32Exception();
            app = Process.GetProcessById((int)info.Pid);
            IntPtr retained = app.Handle;
            if (ResumeThread(info.Thread) == UInt32.MaxValue) throw new System.ComponentModel.Win32Exception();
            return app;
        }
        catch
        {
            TerminateProcess(info.Process, 1);
            if (app != null) app.Dispose();
            throw;
        }
        finally { CloseHandle(info.Thread); CloseHandle(info.Process); }
    }

    internal OwnedJob()
    {
        handle = CreateJobObject(IntPtr.Zero, null);
        if (handle == IntPtr.Zero) throw new System.ComponentModel.Win32Exception();
        var limits = new Limits();
        limits.Basic.Flags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if (!SetInformationJobObject(handle, 9, ref limits, (uint)Marshal.SizeOf(limits)))
        { int error = Marshal.GetLastWin32Error(); Dispose(); throw new System.ComponentModel.Win32Exception(error); }
    }
    internal void Add(Process process)
    {
        if (!AssignProcessToJobObject(handle, process.Handle)) throw new System.ComponentModel.Win32Exception();
    }
    internal void AllowChildrenToContinue()
    {
        var limits = new Limits();
        if (!SetInformationJobObject(handle, 9, ref limits, (uint)Marshal.SizeOf(limits)))
            throw new System.ComponentModel.Win32Exception();
    }
    public void Dispose() { if (handle != IntPtr.Zero) { CloseHandle(handle); handle = IntPtr.Zero; } }
}
