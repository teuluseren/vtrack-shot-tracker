# ShotForge VTrack Connector

An experimental Windows connector that forwards LAON VTrack shot data to
ShotForge through VTrackToolKit's GSPro simulator integration.

The connector provides `GSPLauncher.exe`, `GSPro.exe`, and `GSPconnect.exe` compatibility programs
with the process names and windows VTrackToolKit expects, plus a bridge that
relays shot data and simulator responses. It runs separately from vTrack Shot
Tracker; the archive application is not required to use the connector.

This is an independent community integration, not an official LAON, GSPro or
ShotForge product. No GSPro binaries are included, copied or patched.

## Requirements

- Windows x64 with .NET Framework 4.x.
- VTrack hardware and VTrackToolKit configured to connect to the sensor.
- ShotForge with its Open Connect listener enabled.

## Download the beta

Get the Windows ZIP from the
[connector beta release](https://github.com/teuluseren/vtrack-shot-tracker/releases/tag/connector-v0.1.0-beta.1).
Extract the entire folder somewhere writable and follow `QUICKSTART.txt`.
Select the extracted `GSPLauncher.exe` in VTrackToolKit's GSPro settings.
The ZIP includes its own Python runtime; Python installation, a compiler, and
the archive app are not required. Keep its `python/` folder alongside the EXEs.

Connector releases use `connector-v...` tags and are versioned independently
from the archive app. This beta is not the archive app's latest stable release.

## Build from source

Building requires a local copy of this repository, Python 3.10 or newer, and
the Windows .NET Framework 4.x C# compiler. No additional Python packages are
needed. `Build-Connector.ps1` creates a development bundle using your installed
Python. To create the standalone release ZIP with embedded Python instead:

```powershell
.\shotforge_vtrack_connector\Package-Connector.ps1
```

The packaging script downloads the official CPython 3.13.15 embeddable runtime,
verifies its pinned SHA-256 checksum, and writes the ZIP and checksum file to
the repository's `dist/` folder. It includes fresh default settings, not your
local configuration, logs, or runtime state. See
[third-party notices](THIRD_PARTY_NOTICES.md) and [release notes](RELEASE_NOTES.md).

### Development build and setup

Run the commands below in PowerShell from the repository root.

1. Build once from the repository root:

   ```powershell
   .\shotforge_vtrack_connector\Build-Connector.ps1
   ```

2. Ensure ShotForge is installed and its launch-monitor/Open Connect listener is
   configured for port `921`. The connector opens ShotForge automatically when
   needed; an already running instance is reused.
3. In VTrackToolKit's GSPro simulator settings, select the built launcher:

   ```text
   <repository>\shotforge_vtrack_connector\dist\GSPLauncher.exe
   ```

4. Launch the GSPro simulator **from VTrackToolKit**. A launcher window appears
   briefly, then closes once the `GSPro` connector status window and bridge are
   ready. Keep the GSPro window open and use ShotForge to play. Starting the
   executable alone does not activate VTrack's simulator session.
5. Check that both connections show connected, then hit a shot. The forwarded
   shot count and response count should increase. Confirm the shot in ShotForge.

The build writes its output to `shotforge_vtrack_connector/dist/` and records
the selected Python executable in `dist/connector.json`. To select a specific
Python installation:

```powershell
.\shotforge_vtrack_connector\Build-Connector.ps1 -Python 'C:\Path\To\Python\python.exe'
```

Stop the connector before rebuilding. Rebuilding preserves an existing
`dist/connector.json`; update its `python` value if your Python installation
changes or you move the bundle to another PC.

### ShotForge automatic launch

The connector checks for ShotForge in the current Windows session before opening
it. With `shotforge_exe` left empty, it looks in `C:\ShotForge\ShotForge.exe`
(using your Windows system drive), `%ProgramFiles%\ShotForge\ShotForge.exe`, and
`%LOCALAPPDATA%\Programs\ShotForge\ShotForge.exe`.

For another installation location, set `shotforge_exe` in `dist/connector.json`
to the full application path, for example:

```json
"shotforge_exe": "D:\\Golf Apps\\ShotForge\\ShotForge.exe"
```

Set `launch_shotforge` to `false` to open ShotForge yourself. Automatic launch
is also skipped when `shotforge_host` points to another PC. Opening the app does
not mean its listener is ready yet; wait for both connection indicators before
hitting a shot. If the app cannot be found, the launcher displays a configuration
error. If the connector opens ShotForge, it closes that instance when the
connector stops or VTrackToolKit exits. If ShotForge was already running, it
stays open.

### VTrack face-impact replay

Enable VTrackToolKit's impact/shot-replay overlay in its simulator settings.
This is separate from **Swing Replay**, which controls the swing cameras.
Alternatively, with VTrackToolKit closed, run:

```powershell
.\shotforge_vtrack_connector\Enable-VTrackImpactReplay.ps1
```

The script enables only the impact-overlay setting and saves a backup of the
original settings. It refuses to edit settings while VTrackToolKit is running.

With `follow_shotforge_window` enabled (the default), the impact popup follows
ShotForge's client area as its window moves or resizes. It switches to the
separate ShotForge Course Play window when that opens, then returns to the main
app when Course Play closes. Minimize the game to move its replay off-screen;
restoring the game restores the replay position. The connector status window
can be moved or minimized independently.

VTrack still renders the popup and controls its playback, visibility, and
relative placement. The connector provides an invisible, click-through GSPro
window with matching geometry for VTrack to follow. It does not send impact
video through Open Connect or modify ShotForge or VTrack binaries. Use windowed
or borderless fullscreen mode so Windows can display VTrack's popup over the
game. Tracking applies to ShotForge on the same PC only.

## Status and shutdown

The GSPro compatibility window shows the VTrack and ShotForge connection states, forwarded shot
count, response count, and latest connection error. Its **Open logs** button
opens the diagnostic log folder. A forwarded count means data was written to
the connection; confirm successful shots in ShotForge itself.
The status window opens without taking focus and is placed behind VTrackToolKit
at startup. You can bring it forward when needed; it is not continually sent
to the background. This does not change the impact popup's position.

Close the GSPro window, or click **Stop connector**, to stop the connector.
GSPro requests bridge shutdown and cleans up its GSPconnect host and Python
bridge. If it launched ShotForge, it also requests that app's window close,
allows up to three seconds for it to exit, then terminates any remaining owned
processes. Forced GSPro termination also cleans up the bridge and any ShotForge
processes it launched. Closing the launcher during startup cancels startup and
cleans up its children. A ShotForge instance that was already running is never
owned or closed by the connector. VTrackToolKit and vTrack Shot Tracker remain
independently controlled.

The launcher's normal exit is part of the startup handoff: VTrackToolKit waits
for GSPLauncher to finish before monitoring GSPro. After a successful handoff,
GSPro owns GSPconnect, which hosts the bridge, and stays running independently
of the launcher. VTrackToolKit checks for both GSPro and GSPconnect before
marking the simulator as running.

At startup, the GSPro host watches the single VTrackToolKit (`LPGAgent`)
process in the current Windows session. When that process exits, including a
crash, the connector stops and closes ShotForge if it launched it. If no unique
toolkit process can be identified (for example, when starting the connector
manually without VTrack), use **Stop connector** or close the GSPro window.

Duplicate launcher starts do not create another bridge. Startup failures are
reported in the compatibility windows and logs. The connector does not terminate unrelated
programs to free a port.

To return to GSPro, stop the connector and restore your GSPro executable path
in VTrackToolKit's simulator settings.

## Data path and configuration

```text
VTrackToolKit / LPGAgent GSPro JSON client
    -> 127.0.0.1:12485 (this bridge)
    -> 127.0.0.1:921   (ShotForge)
    <- acknowledgements, errors and player/club changes
```

By default, the bridge accepts local VTrack connections on port `12485` and
connects to ShotForge on port `921`. The public
[GSPro Open Connect v1 documentation](https://gsprogolf.com/GSProConnectV1.html)
describes TCP `921`, success code `200`, player information `201`, and `5xx`
errors. Compatibility with individual VTrackToolKit and ShotForge versions
still requires live testing.

Edit `dist/connector.json` with the connector stopped. See
[connector.example.json](connector.example.json) for the default configuration.

| Setting | Default | Purpose |
| --- | --- | --- |
| `python` | Selected during build | Python executable used by the launcher. |
| `listen_host` | `127.0.0.1` | Local VTrack interface; restricted to loopback. |
| `listen_port` | `12485` | Port accepting VTrack connections; must match VTrack's destination. |
| `shotforge_host` | `127.0.0.1` | PC running ShotForge. |
| `shotforge_port` | `921` | ShotForge's Open Connect listening port. |
| `launch_shotforge` | `true` | Open the local ShotForge app if it is not already running. |
| `shotforge_exe` | Empty (auto-detect) | Path to ShotForge.exe; environment variables and bundle-relative paths are supported. |
| `follow_shotforge_window` | `true` | Make VTrack's impact replay follow local ShotForge and its Course Play window. Requires VTrack's impact overlay enabled. |
| `shot_mode` | `vtrack` | Adapt VTrack shot flags for ShotForge, or use `passthrough` for exact outgoing bytes. |
| `reply_mode` | `gspro` | Normalize response messages, or use `passthrough` for exact response bytes. |
| `reply_delimiter` | `nul` | Response separator: `nul`, `newline`, or `none`; used in `gspro` mode. |
| `connect_timeout` | `5.0` | Seconds allowed to establish the ShotForge connection. |

For ShotForge on another PC, set `shotforge_host` to that PC's address and allow
the configured destination port through its firewall. VTrack and the connector
must run on the same PC. Do not configure the bridge to connect to itself.

### Data handling

- `reply_mode: "gspro"` normalizes response messages for codes 200 and 201 while
  preserving actual response codes, Player data, errors, and extension fields.
- `reply_mode: "passthrough"` relays response bytes exactly for comparison.
- In `shot_mode: "vtrack"`, a packet with `ContainsBallData: true` and a finite,
  positive ball speed is sent with `IsHeartBeat: false`. Some VTrack versions
  mark real shots as heartbeats, which ShotForge ignores. Status-only packets
  are not promoted to shots.
- The adapter also supplies the standard `APIversion` field when VTrack uses
  `APIVersion`. It preserves the original field and all measured ball/club
  values, units, and any supplied shot number. Outgoing JSON uses NUL separators.
- `shot_mode: "passthrough"` preserves outgoing bytes exactly for diagnostics;
  it disables the heartbeat correction. No shot numbers or measurements are
  fabricated in either mode.
- Player changes from ShotForge are forwarded immediately, without waiting for
  a shot. No synthetic player defaults or successful shot replies are invented.
- A lost connection closes both sockets so VTrack can reconnect. Shots are not
  queued or replayed across disconnects because delivery may be uncertain.

For bridge-only debugging, with the normal connector stopped:

```powershell
python .\shotforge_vtrack_connector\bridge.py --config .\shotforge_vtrack_connector\dist\connector.json
```

## Diagnose a failed connection

```powershell
.\shotforge_vtrack_connector\Diagnose-Connector.ps1
```

This reads process/window information, `netstat`, connector logs and the newest
toolkit log. It does not send shots, change settings or terminate processes.
Review output before sharing because toolkit messages can contain local paths.

1. **Could not start / port conflict:** identify the PID shown for `12485`, then
   check which application owns it. Only one listener can use that address and
   port; resolve the conflict before starting the connector.
2. **Waiting for toolkit:** confirm VTrack uses the built launcher and launched
   its GSPro simulator. Look for `Starting monitor thread` and `GSProJsonClient`
   after the UI wait in the toolkit log. A successful startup closes the launcher
   and leaves the GSPro status window open.
3. **ShotForge disconnected:** confirm ShotForge's listener and destination
   port. Real GSPro's API listener cannot share ShotForge's port.
4. **Connected but no shots:** check VTrackToolKit's sensor connection and ready
   state, then inspect the bridge log for shot and response entries. The
   default `shot_mode: "vtrack"` is required for VTrack versions that flag shots
   as heartbeats. A connection acknowledgement alone does not mean ShotForge
   accepted a shot. The connector does not resolve sensor calibration or
   readiness errors.
5. **Swing cameras work, but impact replay is missing:** enable VTrack's impact
   overlay separately from Swing Replay. Keep `follow_shotforge_window` enabled
   and check `launcher.log` for `Impact replay following ShotForge`. For an
   unsupported Course Play executable name or exclusive fullscreen mode, window
   tracking may need additional compatibility work.

Local `dist/logs/bridge.log` records connections, forwarded shot summaries and
error responses. `launcher.log` records startup and child failures. Runtime
status and logs are ignored by git.

## Development and validation

Synthetic socket tests cover framing, shot-flag correction, measurement preservation,
optional byte passthrough, unsolicited player
updates, errors, disconnects, unavailable destinations and port conflicts.
The Windows smoke test checks actual launcher/GSPro windows on an isolated
desktop, launcher exit with the bridge and owned app still running, and cleanup
after GSPro closes or is forcibly terminated, using temporary ports and a
synthetic server. Dummy app and toolkit processes verify that VTrack exit closes
an app the connector launched, including its helpers, while leaving an already
running app open.
An independent native-window test checks impact-window lookup, client-area
tracking, movement, resizing, minimize/restore, Course Play switching, app
restart, click-through styles, and focus preservation on an isolated desktop.
Build the bundle first to include the Windows launcher smoke tests. These tests
skip while VTrackToolKit, GSPro or the connector is running: the toolkit can
discover test process names even when their windows are on an isolated desktop.
With those applications closed, run:

```powershell
python -m unittest discover -s tests -v
```

Automated tests use synthetic data and do not establish hardware compatibility.
A live VTrack launch and real shot into ShotForge are required to validate an
installation. When reporting a problem, include your VTrackToolKit and ShotForge
versions, the connection stage that fails, and relevant sanitized log excerpts.
