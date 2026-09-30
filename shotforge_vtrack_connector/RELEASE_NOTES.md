# ShotForge VTrack Connector 0.1.0-beta.1

First public beta of the standalone VTrack-to-ShotForge connector.

## Download and setup

Download `ShotForgeVTrackConnector-0.1.0-beta.1-windows-x64.zip` and extract the
entire folder. Select its `GSPLauncher.exe` in VTrackToolKit's GSPro simulator
settings. See the included `QUICKSTART.txt`. No Python installation, compiler,
or vTrack Shot Tracker installation is required. Windows x64 with .NET
Framework 4.x, VTrackToolKit, and ShotForge are required.

## Included

- Compatibility launcher, GSPro status window, and GSPconnect bridge host.
- Shot forwarding to ShotForge, with VTrack heartbeat-flag compatibility and
  preservation of measured ball/club values.
- Return forwarding of actual acknowledgements, club selections, and handedness.
- Automatic local ShotForge launch and ownership-aware shutdown.
- VTrack impact-popup positioning that follows ShotForge and Course Play.
- A status window that opens behind VTrack without taking focus.
- Embedded Python runtime, diagnostic tools, setup instructions, and checksums.

## Beta limitations

Live VTrack shot forwarding has been exercised locally. Impact-popup positioning
and the latest status-window ordering have automated native-window coverage;
they still need confirmation across live simulator setups. Impact replay must
be enabled in VTrack separately from Swing Replay. Exclusive fullscreen and
different Course Play executable names may need additional compatibility work.

An unresponsive club selector inside ShotForge is not fixed by this release;
club-change messages have been observed arriving at VTrack through the bridge.
Shots are not queued or replayed after a connection loss. This beta has no
automatic updater or installer, and its compatibility executables are unsigned.

This is an independent community integration, not an official LAON, GSPro, or
ShotForge product. It contains no copied or patched vendor binaries. The archive
app's version and stable release remain independent of this connector beta.
