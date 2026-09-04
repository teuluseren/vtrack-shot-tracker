# Installation & Troubleshooting

This guide is for golfers installing **vTrack Shot Tracker** on a Windows simulator PC.

If you only want the shortest possible setup, use the **[Quick Start](QUICK_START.md)**.

This page adds update, uninstall, recovery, and troubleshooting details.

## Beginner path — normal Windows install

### What you need

Before installing Shot Tracker, make sure your simulator already has:

- Windows 10 or Windows 11;
- LAON VTrack installed and working;
- GSPro working with VTrack;
- permission to install a Windows program.

Python is **not** required for the normal installer.

Microsoft Edge WebView2 Runtime is also used for the dedicated Shot Tracker window. It is normally already present on Windows 11 and many Windows 10 systems.

### 1. Download the correct file

Open the project's **Releases** page and download the newest stable installer named like:

```text
VTrackShotTracker-Setup-<version>.exe
```

For a normal install, do **not** download:

- `Source code.zip`;
- `Source code.tar.gz`;
- the portable ZIP.

Those are for advanced users and developers.

### 2. Run the installer

Double-click the installer.

Early builds may show a Windows SmartScreen message because the installer is not yet code-signed.

Only continue when you downloaded the file from this project's GitHub Release.

If Windows shows **Windows protected your PC**:

1. choose **More info**;
2. choose **Run anyway**.

Keep the default install location unless you have a specific reason to change it:

```text
C:\Program Files\VTrack Shot Tracker\
```

Finish setup.

### 3. Start Shot Tracker

Open the Windows Start menu and choose:

**Start vTrack Shot Tracker**

The Shot Tracker window should open.

Shot Tracker and VTrack are separate programs. Opening Shot Tracker does **not** start VTrackToolKit.

### 4. Start VTrack and GSPro normally

Use the same process you already use before hitting balls.

Then return to Shot Tracker.

### 5. Hit a test shot

Look at the upper-right status area. The collector should show that it is live/running.

Hit one normal test shot.

The new shot should appear under **Sessions & shots** on the left.

If **Follow live** is on, that new shot should automatically become selected.

You may also see:

- a point on the Range;
- shot numbers across the bottom;
- Impact Replay;
- strike location.

Not every source provides every metric or media file for every shot, so an individual missing value is not automatically an error.

## What gets installed, and where are my shots?

The program and your shot history are stored separately:

```text
C:\Program Files\VTrack Shot Tracker\       the app itself
%USERPROFILE%\Documents\VTrackArchive\      your shots and database
%LOCALAPPDATA%\VTrackShotTracker\           app logs and temporary/runtime state
```

The important folder to back up is:

```text
%USERPROFILE%\Documents\VTrackArchive\
```

Installing an update or uninstalling Shot Tracker is designed to leave that archive in place.

## Updating

The version button near the top of Shot Tracker shows the installed version.

Select it to check for an update.

When an update is available:

1. choose the update;
2. confirm it;
3. Shot Tracker downloads and verifies the installer;
4. Shot Tracker closes its own running pieces;
5. complete the Windows installer that opens;
6. start Shot Tracker again if needed.

Your archive under `Documents\VTrackArchive` should remain in place.

## Uninstalling

Use either:

**Windows Settings → Apps → Installed apps → vTrack Shot Tracker → Uninstall**

or the Shot Tracker uninstall shortcut in the Start menu.

Uninstalling the program is designed not to delete your shot history.

If you intentionally want to delete all saved Shot Tracker data too, first make any backup you want, then manually remove:

```text
Documents\VTrackArchive\
```

Do not delete that folder as part of normal troubleshooting.

# Troubleshooting for everyone

## The Shot Tracker window does not appear

First try starting **Shot Review** from the Start menu.

If that still does not appear, restart Windows once and try again.

If the problem continues and you are comfortable using PowerShell, use the [Advanced Guide](ADVANCED_GUIDE.md#troubleshooting-with-status) to check the individual Shot Tracker components.

A dedicated Windows window requires Microsoft Edge WebView2 Runtime. Shot Tracker is designed to fall back to a normal browser when the native window cannot start.

## The app opens, but new shots do not appear

Check the simple things first:

1. Is VTrack running?
2. Is GSPro connected and receiving VTrack shots normally?
3. Does Shot Tracker's upper-right collector status show live/running?
4. Are you looking at the current session in **Sessions & shots**?
5. Did you accidentally hide the session, club, or shot from the Range?

If VTrack and GSPro are working but the Shot Tracker collector is stopped, continue with the advanced troubleshooting section below.

## I can see old shots but not new shots

That usually means the review side of the app is working but the collector is not currently capturing.

This is useful information: your archive is probably fine.

Check the collector status, then use the advanced log steps if needed.

## A replay or metric is missing

Not every shot contains every source value or camera file.

For example, the app may have enough data to save distance and ball speed even if it could not match a camera folder for that particular shot.

A single missing replay does not necessarily mean collection failed.

## I clicked Clear range and everything disappeared

**Clear range does not delete anything.**

It only hides the plotted groups.

Use the visibility controls in **Sessions & shots** to show the session or club again.

# Advanced installation and troubleshooting

If the steps above are enough, you can stop reading here.

The sections below are for users who are comfortable with Windows command-line tools.

## Check Shot Tracker status

Open PowerShell and run:

```powershell
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' status
```

This shows the state of the viewer, desktop window, and collector.

## Open Shot Review in a normal browser

```powershell
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' review --browser
```

If browser mode works but the normal Shot Tracker window does not, the problem is likely with the desktop/WebView2 side rather than the shot archive.

## Logs

Shot Tracker logs are normally here:

```text
%LOCALAPPDATA%\VTrackShotTracker\logs\
```

If new shots are not being captured, start with:

```text
collector.log
```

If the dedicated window is failing, inspect the desktop log.

If the local review page is failing, inspect the viewer log.

## Collector shows stopped

Possible causes include:

- the collector process exited;
- VTrack is not installed in the package location this project currently expects;
- the archive location is not writable;
- a packaged dependency or runtime is missing;
- the installed build is damaged or incomplete.

The collector status is based on a current heartbeat, not just on whether the review screen is open.

## Stop Shot Tracker from PowerShell

```powershell
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' stop
```

This stops Shot Tracker only and should leave VTrack running.

## Portable package

Advanced users may use:

```text
VTrackShotTracker-<version>-portable.zip
```

Extract the **entire** folder, then run:

```powershell
.\VTrackShotTracker.exe start
```

Do not move only the EXE out of the portable folder. Supporting runtime files are required.

For more power-user options, Home Assistant integration, command-line modes, and development workflows, see the **[Advanced Guide](ADVANCED_GUIDE.md)**.
