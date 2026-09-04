# Changelog

All notable public changes follow [Keep a Changelog](https://keepachangelog.com/) and releases use [Semantic Versioning](https://semver.org/).

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

