"""Native window tracking on a private desktop using uniquely named dummy apps."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import uuid

from test_shotforge_vtrack_launcher import DesktopProcess, StartupInfo, ProcessInfo

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "Windows window tracking")
class ImpactWindowTests(unittest.TestCase):
    def test_tracks_client_area_and_course_window_without_taking_input(self):
        with tempfile.TemporaryDirectory(prefix="shotforge impact test ") as folder:
            root = Path(folder)
            name = "ImpactTest_" + uuid.uuid4().hex
            source = root / "Test.cs"
            source.write_text(r'''
using System; using System.Diagnostics; using System.IO; using System.Threading;
using System.Drawing; using System.Runtime.InteropServices; using System.Windows.Forms;
static class TrackerSmoke {
    [StructLayout(LayoutKind.Sequential)] struct Rect { public int L,T,R,B; }
    [StructLayout(LayoutKind.Sequential)] struct Point { public int X,Y; }
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr w, out Rect r);
    [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr w, out Rect r);
    [DllImport("user32.dll")] static extern bool ClientToScreen(IntPtr w, ref Point p);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr w, IntPtr z, int x,int y,int cx,int cy,uint f);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr w,int cmd);
    [DllImport("user32.dll")] static extern IntPtr GetActiveWindow();
    [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr w,uint cmd);
    [DllImport("user32.dll", EntryPoint="GetWindowLongPtrW")] static extern IntPtr GetWindowLongPtr(IntPtr w,int n);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr w,int msg,IntPtr a,IntPtr b);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr w,int msg,IntPtr a,IntPtr b);
    [DllImport("user32.dll")] static extern bool GetLayeredWindowAttributes(IntPtr w,out uint c,out byte a,out uint f);
    static void Assert(bool condition,string message) { if(!condition) throw new Exception(message); }
    static void Pump() { Application.DoEvents(); Thread.Sleep(30); }
    static IntPtr WaitWindow(Process p) {
        for(int n=0;n<150;n++) { p.Refresh(); if(p.MainWindowHandle!=IntPtr.Zero) return p.MainWindowHandle; Pump(); }
        throw new Exception("Dummy window did not open");
    }
    static void CheckBounds(IntPtr anchor,IntPtr app) {
        Rect a,c; var p=new Point(); GetWindowRect(anchor,out a); GetClientRect(app,out c); ClientToScreen(app,ref p);
        int caption=SystemInformation.CaptionHeight;
        Assert(a.L==p.X && a.T+caption==p.Y && a.R-a.L==c.R && a.B-a.T-caption==c.B,
            "Anchor did not match target client area: "+a.L+","+a.T+","+a.R+","+a.B+" vs "+p.X+","+p.Y+","+c.R+","+c.B);
    }
    static void Stop(Process p) {
        if(p==null) return;
        if(!p.HasExited) { p.Kill(); p.WaitForExit(5000); } p.Dispose();
    }
    [STAThread] static int Main() {
        string dir=AppDomain.CurrentDomain.BaseDirectory;
        string name=Process.GetCurrentProcess().ProcessName;
        if(name.EndsWith("_app") || name.EndsWith("_course")) {
            var appForm=new Form { Text="Dummy ShotForge", StartPosition=FormStartPosition.Manual,
                Bounds=new Rectangle(90,110,900,600) };
            Application.Run(appForm); return 0;
        }
        Process app=null, course=null;
        try {
            using(var status=new Form { Text="Connector status", Width=490, Height=200 }) {
                status.Show(); Pump();
                using(var tracker=new ImpactWindowTracker(status,name+"_app",name+"_course")) {
                    tracker.Update(); Assert(tracker.Handle==IntPtr.Zero,"No app must not create an anchor");
                    app=Process.Start(new ProcessStartInfo(Path.Combine(dir,name+"_app.exe")) { UseShellExecute=false });
                    IntPtr appWindow=WaitWindow(app);
                    IntPtr active=GetActiveWindow(); tracker.Update(); Pump();
                    Assert(active==GetActiveWindow(),"Tracker stole activation");
                    IntPtr anchor=tracker.Handle; Assert(anchor!=IntPtr.Zero,"Anchor missing");
                    using(var self=Process.GetCurrentProcess()) {
                        self.Refresh(); Assert(self.MainWindowHandle==anchor,"VTrack main-window lookup found status instead of anchor");
                    }
                    Assert(GetWindow(status.Handle,4)==anchor,"Status must be owned by anchor");
                    long style=GetWindowLongPtr(anchor,-20).ToInt64();
                    Assert((style & 0x080800A0)==0x080800A0,"Missing click-through/no-activate styles");
                    uint color,flags; byte alpha; Assert(GetLayeredWindowAttributes(anchor,out color,out alpha,out flags) && alpha==0,"Anchor must be invisible");
                    Assert(SendMessage(anchor,0x84,IntPtr.Zero,IntPtr.Zero).ToInt64()==-1,"Hit testing must pass through");
                    Assert(SendMessage(anchor,0x21,IntPtr.Zero,IntPtr.Zero).ToInt64()==3,"Mouse must not activate anchor");
                    CheckBounds(anchor,appWindow);
                    IntPtr beforeStack=GetActiveWindow(); Rect beforeStatus,afterStatus;
                    GetWindowRect(status.Handle,out beforeStatus);
                    Assert(Program.PlaceWindowBehind(status.Handle,appWindow),"Could not place status behind toolkit stand-in");
                    GetWindowRect(status.Handle,out afterStatus);
                    Assert(GetWindow(appWindow,2)==status.Handle,"Status is not immediately behind toolkit stand-in");
                    Assert(GetActiveWindow()==beforeStack,"Background placement changed focus");
                    Assert(beforeStatus.L==afterStatus.L && beforeStatus.T==afterStatus.T && beforeStatus.R==afterStatus.R && beforeStatus.B==afterStatus.B,"Background placement moved/resized status");
                    CheckBounds(anchor,appWindow);
                    SetWindowPos(appWindow,IntPtr.Zero,-500,230,1200,710,0x14); Pump(); tracker.Update(); CheckBounds(anchor,appWindow);
                    ShowWindow(appWindow,6); Pump(); tracker.Update(); Rect parked; GetWindowRect(anchor,out parked);
                    Assert(parked.R<SystemInformation.VirtualScreen.Left,"Minimized app must park replay outside desktop");
                    ShowWindow(appWindow,9); Pump(); tracker.Update(); CheckBounds(anchor,appWindow);
                    ShowWindow(status.Handle,6); Pump(); tracker.Update(); CheckBounds(anchor,appWindow);
                    ShowWindow(status.Handle,9); Pump();
                    course=Process.Start(new ProcessStartInfo(Path.Combine(dir,name+"_course.exe")) { UseShellExecute=false });
                    IntPtr courseWindow=WaitWindow(course);
                    SetWindowPos(courseWindow,IntPtr.Zero,350,170,1100,750,0x14); Pump(); tracker.Update(); CheckBounds(anchor,courseWindow);
                    ShowWindow(courseWindow,6); Pump(); tracker.Update(); GetWindowRect(anchor,out parked);
                    Assert(parked.R<SystemInformation.VirtualScreen.Left,"Minimized course must not fall back to launcher cover");
                    Stop(course); course=null; tracker.Update(); CheckBounds(anchor,appWindow);
                    Stop(app); app=null; tracker.Update(); GetWindowRect(anchor,out parked);
                    Assert(parked.R<SystemInformation.VirtualScreen.Left,"Closed app must park replay");
                    app=Process.Start(new ProcessStartInfo(Path.Combine(dir,name+"_app.exe")) { UseShellExecute=false });
                    appWindow=WaitWindow(app); tracker.Update(); CheckBounds(anchor,appWindow);
                    tracker.Dispose(); Assert(GetWindow(status.Handle,4)==IntPtr.Zero,"Shutdown must detach status owner");
                }
                status.Close();
            }
            File.WriteAllText(Path.Combine(dir,"result.txt"),"PASS"); return 0;
        } catch(Exception e) { File.WriteAllText(Path.Combine(dir,"result.txt"),e.ToString()); return 1; }
        finally { Stop(course); Stop(app); }
    }
}
''', encoding="utf-8")
            compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
            exe = root / (name + ".exe")
            result = subprocess.run([str(compiler), "/nologo", "/target:winexe", "/platform:x64", "/main:TrackerSmoke",
                                     "/out:" + str(exe), "/reference:System.Windows.Forms.dll",
                                     "/reference:System.Drawing.dll", "/reference:System.Web.Extensions.dll",
                                     str(ROOT / "shotforge_vtrack_connector/CompatibilityHost.cs"), str(source)],
                                    capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for suffix in ("_app", "_course"):
                shutil.copyfile(exe, root / (name + suffix + ".exe"))
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            user = ctypes.WinDLL("user32", use_last_error=True)
            user.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
            user.CreateDesktopW.restype = wintypes.HANDLE
            user.CloseDesktop.argtypes = [wintypes.HANDLE]
            kernel.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
                                              wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
                                              ctypes.POINTER(StartupInfo), ctypes.POINTER(ProcessInfo)]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
            desktop = user.CreateDesktopW(name, None, None, 0, 0x01FF, None)
            self.assertTrue(desktop)
            process = None
            try:
                process = DesktopProcess(kernel, exe, name)
                code = process.wait(timeout=30)
                report = (root / "result.txt").read_text() if (root / "result.txt").exists() else "No result"
                self.assertEqual(code, 0, report)
                self.assertEqual(report, "PASS")
            finally:
                if process:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=5)
                    kernel.CloseHandle(process.handle)
                user.CloseDesktop(desktop)


if __name__ == "__main__":
    unittest.main()
