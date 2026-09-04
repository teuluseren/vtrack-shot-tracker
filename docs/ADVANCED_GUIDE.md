# Advanced Guide

This guide is for users who are comfortable with Windows configuration and want more control over vTrack Shot Tracker.

You do **not** need this guide for normal practice use.

Start with the [Quick Start](QUICK_START.md) or [User Guide](USER_GUIDE.md) if you only want to install the app, hit shots, and review them.

## Who this guide is for

Use this guide if you want to:

- run Shot Tracker from the command line;
- use browser or headless mode;
- use a portable build;
- connect Shot Tracker to Home Assistant or other simulator automation;
- inspect logs when something fails;
- understand where application state is stored;
- work with exports or the SQLite archive directly;
- build or test the project from source.

## Application boundaries

The core Shot Tracker executable and VTrack are intentionally separate.

These commands manage **Shot Tracker only**:

```powershell
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' start
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' stop
```

They do not start or terminate VTrackToolKit.

The optional root-level `Start-VTrack.ps1` and `Stop-VTrack.ps1` scripts are different: they are external simulator-automation helpers that intentionally compose VTrack and Shot Tracker into one action.

## Command-line interface

The installed executable supports these primary commands:

```powershell
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' start
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' stop
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' status
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' review
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' check-update
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' update
```

### `start`

Starts the Shot Tracker-owned collector, local review service, and normal desktop window.

Useful variants include:

```powershell
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' start --browser
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' start --no-window
```

`--browser` opens the UI in the default browser.

`--no-window` starts the tracker without opening the visible review window.

### `stop`

Stops Shot Tracker-owned processes and leaves VTrack alone.

### `status`

Shows whether the viewer, desktop host, and collector are running and shows their log locations.

### `review`

Starts or opens the historical review UI without requiring a live collector session.

Browser mode:

```powershell
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' review --browser
```

### Update commands

`check-update` checks the newest stable GitHub Release without installing it.

`update` downloads and verifies a compatible installer, stops Shot Tracker-owned processes, and opens the installer.

## Home Assistant / combined simulator automation

The repository includes:

```text
Start-VTrack.ps1
Stop-VTrack.ps1
```

These scripts are intended for setups where one Home Assistant action should control the simulator workflow.

The start helper:

1. checks whether VTrackToolKit is already running;
2. starts it through the Windows Start Apps registration if needed;
3. starts the installed Shot Tracker.

The stop helper:

1. stops Shot Tracker;
2. closes VTrack-related processes managed by that automation workflow.

This behavior is intentional **only in these external helper scripts**.

If you want Home Assistant to control Shot Tracker but not VTrack, call the installed executable directly instead of the combined scripts.

## Portable build

A release may also include:

```text
VTrackShotTracker-<version>-portable.zip
```

Extract the entire archive to a normal folder. Do not copy only the EXE out of it; the portable release is a one-folder application with supporting runtime files.

Start it with:

```powershell
.\VTrackShotTracker.exe start
```

The normal installer is recommended for most users because Start-menu shortcuts, update behavior, and installation paths are more predictable.

## Data and runtime locations

Shot Tracker intentionally separates program files, user data, and temporary/runtime state.

```text
C:\Program Files\VTrack Shot Tracker\       installed program
%USERPROFILE%\Documents\VTrackArchive\      shot database and archived media
%LOCALAPPDATA%\VTrackShotTracker\           logs and runtime/window state
```

### Archive

The important user-data directory is:

```text
%USERPROFILE%\Documents\VTrackArchive\
```

It normally contains:

- `vtrack_shots.sqlite3`;
- archived shot folders under `shots\`;
- collector heartbeat state;
- durable UI/Bag Mapping preferences stored in SQLite.

Back up the whole archive directory if you want a complete Shot Tracker backup.

### Media storage cleanup

For new copied shots, Shot Tracker registers the database row immediately, then
converts each available BMP frame sequence to H.264 MP4 on a background worker.
The worker removes a sequence only after the replacement video exists, is
non-empty, and its path has been saved. Database records, strike data, and
generated videos are preserved. Frames are also preserved when video conversion
fails or when `--no-copy` is used. FFmpeg runs without opening a console window
on Windows.

Preview recoverable space in an existing archive:

```powershell
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' cleanup-storage
```

Perform the cleanup:

```powershell
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' cleanup-storage --apply
```

The apply command stops Shot Tracker's own processes before deleting eligible
frames. To retain source BMPs for future shots, set the
`VTRACK_KEEP_SOURCE_FRAMES=1` environment variable before starting Shot
Tracker, or pass `--keep-source-frames` when running the collector directly.

### Logs

Logs are normally under:

```text
%LOCALAPPDATA%\VTrackShotTracker\logs\
```

Useful files include collector, viewer, and desktop-host logs.

## Troubleshooting with `status`

Start with:

```powershell
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' status
```

Think of the app as three pieces:

- **viewer** — serves the local Shot Review UI;
- **desktop** — displays that UI in the dedicated Windows window;
- **collector** — watches for new VTrack/GSPro shots.

This distinction is useful because historical review can work even when the collector is stopped.

## If the desktop window does not open

Try browser mode:

```powershell
& 'C:\Program Files\VTrack Shot Tracker\VTrackShotTracker.exe' review --browser
```

If browser mode works but the dedicated window does not, check Microsoft Edge WebView2 Runtime and the desktop log.

Shot Tracker is designed to fall back to a browser when the native window cannot initialize.

## If new shots are not appearing

Check these in order:

1. Run `status` and confirm the collector is running.
2. Confirm VTrack is running and producing shots normally.
3. Confirm GSPro communication is working.
4. Inspect `%LOCALAPPDATA%\VTrackShotTracker\logs\collector.log`.
5. Confirm the expected VTrack Windows package exists.
6. Confirm new `GSProJsonClient_*.log` and `VTrackToolKit_*.log` data is being written.
7. Confirm `LPGDLL\ShotData` is being created/updated for camera data.

The collector is intentionally live-only. Restarting it does not reread every historical VTrack log line.

## Understanding Bag Mapping data

The database keeps two useful club concepts:

- `gspro_club_raw` — what GSPro originally reported;
- `club` — the normalized/mapped club Shot Tracker uses for grouping and display.

For example:

```text
gspro_club_raw = SW
club            = 54DEG
```

The original value is preserved so a user mapping does not destroy source provenance.

## Reports and exports

Shot Tracker can create several portable outputs depending on available data:

- selected-shot CSV;
- session CSV;
- printable session/coaching report;
- range image/SVG;
- impact/swing MP4;
- strike/heatmap image;
- self-contained comparison HTML.

These are useful when you want to share results without sharing the complete SQLite archive.

## Working with the SQLite archive

The database is:

```text
%USERPROFILE%\Documents\VTrackArchive\vtrack_shots.sqlite3
```

Treat it as personal user data.

If you inspect or query it manually, make a backup first. Avoid direct schema changes unless you are developing the application and understand its migrations.

## Development mode

From a source checkout:

```powershell
python .\vtrack_shot_tracker.py dev
```

This opens the current source UI against the normal archive.

Browser development mode:

```powershell
python .\vtrack_shot_tracker.py dev --browser
```

Stop only the development desktop/viewer:

```powershell
python .\vtrack_shot_tracker.py dev-stop
```

Because development mode can use the real archive, edits such as moving shots or changing sessions affect real data.

## Build from source

Install the pinned build requirements:

```powershell
python -m pip install --requirement requirements-build.txt
```

Then run:

```powershell
.\packaging\build.ps1
```

The release build uses PyInstaller, FFmpeg, and Inno Setup.

For architecture and engineering rules, read:

- [Requirements & Tenets](REQUIREMENTS_AND_TENETS.md)
- [Architecture](ARCHITECTURE.md)
