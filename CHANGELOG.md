# Changelog

All notable public changes follow [Keep a Changelog](https://keepachangelog.com/) and releases use [Semantic Versioning](https://semver.org/).

## [0.7.0] - 2026-09-04

### Added

- Reversible session archiving that hides archived sessions and their shots from normal views.
- Archived-session viewer with names, creation/archive dates, totals, per-club shot counts, and restore actions.
- Permanent archived-session deletion with an irreversible confirmation dialog.

### Changed

- Session deletion removes database records and Shot Tracker-owned media while preserving original VTrack source folders outside the archive.
- New shots never attach to an archived session.

## [0.6.2] - 2026-09-04

### Fixed

- Replaced the command-style Start-menu shortcuts with one `vTrack Shot Tracker` app entry.
- Assigned the installed shortcut and desktop window the same stable Windows app identity.
- Removed obsolete Start, Review, Update, Stop, and Uninstall shortcuts during upgrade so taskbar pins no longer resolve to the Stop command.

## [0.6.1] - 2026-09-04

### Fixed

- Removed the console window from normal Start-menu and taskbar launches.
- Made a taskbar-pinned app relaunch correctly when Windows omits shortcut arguments.
- Added a dedicated console executable for status, cleanup, and other terminal commands.

## [0.6.0] - 2026-09-04

### Added

- Background H.264 conversion for impact replay and both swing-camera frame sequences.
- Animated encoding states that refresh automatically when replay media is ready.
- Dry-run-first `cleanup-storage` command for safely reclaiming existing archives.

### Changed

- New shots are registered immediately while media conversion and verified frame cleanup continue in the background.
- FFmpeg runs without visible console windows on Windows.

