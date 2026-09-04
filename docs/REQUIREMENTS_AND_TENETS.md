# Requirements & Tenets

This document is the primary orientation guide for humans and AI coding agents working on **vTrack Shot Tracker**. Read it before making architectural, data-model, UI, packaging, documentation, or release changes.

It describes what the application is trying to accomplish, the users it is trying to serve, the constraints that shape it, and the principles that should remain true as implementation details evolve.

## Product purpose

vTrack Shot Tracker is a local Windows companion application for golfers using **LAON VTrack** with **GSPro**.

Its job is to automatically preserve every new shot, combine the useful data exposed by VTrack and GSPro, archive associated camera artifacts, and make the resulting history useful for practice, fitting, coaching, and later review.

The intended user should not need to:

- export a GSPro CSV after every session;
- manually copy VTrack shot folders;
- run Python;
- understand SQLite;
- understand VTrack log formats;
- understand how the desktop host, local server, and collector are implemented.

At a high level the product does four things:

1. **Observe** VTrack and GSPro output without modifying either application.
2. **Archive** each new shot into durable local storage.
3. **Review and analyze** shots in a purpose-built launch-monitor-style workspace.
4. **Package and update** as a normal Windows application.

## User personas

Design and documentation decisions should work across several user types. Do not assume that everyone using a golf simulator is also a software engineer.

### Persona 1 — golfer / simulator user

This is the default user persona.

They may be very knowledgeable about golf but only moderately comfortable with Windows.

They want to:

- install an app;
- open it;
- hit shots;
- see dispersion and shot numbers;
- replay impact;
- review strike location;
- come back to old sessions;
- save or share a report.

They should not need to know words such as `SQLite`, `loopback`, `heartbeat`, `WebView2`, `PID`, `CLI`, `PyInstaller`, or `ShotData` during normal use.

When a technical concept must surface, explain what it means in user terms first.

Example:

> “Collector live means Shot Tracker is ready to notice new shots.”

is better beginner documentation than:

> “The collector heartbeat is current.”

The latter is appropriate in advanced/troubleshooting documentation.

### Persona 2 — coach / club fitter / serious practice user

This user cares about analysis more than implementation.

They are likely to use:

- named sessions;
- multi-club dispersion;
- Carry vs Total;
- strike patterns;
- comparison views;
- shot reclassification;
- reports/PDFs;
- CSV/image exports.

Documentation for this persona should use familiar golf and launch-monitor language and explain what a visualization means before explaining how it is computed.

### Persona 3 — simulator hobbyist / power user

This user is comfortable with Windows configuration and may use:

- Bag Mapping;
- Home Assistant;
- PowerShell;
- portable builds;
- command-line modes;
- logs;
- custom startup/shutdown workflows;
- SQLite or exported data.

Technical detail is appropriate here, but it should live in an **Advanced Guide** rather than being required reading for Persona 1.

### Persona 4 — developer / AI coding agent

This persona needs implementation detail, source fidelity, architectural boundaries, tests, packaging rules, and migration constraints.

This document and `docs/ARCHITECTURE.md` are the primary references for that audience.

Developer documentation must not become the normal user manual by accident.

## Documentation hierarchy is a product requirement

User documentation should be layered by need rather than organized around source-code components.

The intended hierarchy is:

1. **README** — what the product is, why a golfer might want it, and where to go next.
2. **Quick Start** — install, open, hit one shot, understand the four parts of the screen.
3. **User Guide** — normal practice workflows in golf-simulator language.
4. **Advanced Guide** — Home Assistant, command line, portable builds, logs, troubleshooting, and power-user concepts.
5. **Requirements & Tenets / Architecture** — contributors and AI agents.

Tenets for user-facing documentation:

- Put the shortest successful path first.
- Do not make optional features sound mandatory.
- Define launch-monitor terms when a recreational golfer may not know them.
- Prefer the button/label the user sees on screen over an internal class/function name.
- Explain the consequence of a control before the implementation detail.
- Clearly identify destructive vs non-destructive actions.
- Keep troubleshooting ordered from easiest/commonest to most technical.
- Hide command-line instructions behind an advanced heading unless the normal GUI cannot complete the task.
- Do not make a beginner read Home Assistant or developer instructions to install the app.
- Keep general docs version-agnostic where possible so a normal SemVer bump does not make them stale.
- When a visible workflow changes, update the beginner path as well as the technical reference.

A technically correct guide that intimidates normal golfers is not considered complete.

## Non-goals

The application is not intended to:

- replace VTrack or GSPro;
- inject into, patch, hook, or automate the internals of VTrack;
- decode proprietary `.plog` data;
- infer or silently correct shot results that the source applications did not provide;
- upload a golfer's archive to a cloud service as part of normal operation;
- require a Python installation for ordinary users;
- require command-line tools for normal use;
- own the lifecycle of VTrackToolKit from the core Shot Tracker executable.

Optional external PowerShell automation may deliberately start or stop both applications for a simulator/Home Assistant workflow, but that composition must remain outside the Shot Tracker core.

## Core user requirements

### Automatic collection

Once Shot Tracker is running, every **new** VTrack/GSPro shot should be captured automatically.

The collector currently uses three readable sources:

- `GSProJsonClient_*.log` for GSPro ball data, club data, and Player state;
- `VTrackToolKit_*.log` for VTrack trajectory results such as carry, total distance, apex, and side;
- `LPGDLL\ShotData\<number>\` for VTrack shot-camera frames and related artifacts.

Collection is deliberately **live-only**. When the collector starts or switches to a newly created log file, it begins at EOF instead of importing historical log contents. Existing ShotData folders are baselined so they are not mistaken for new shots.

Normal user documentation should describe this as “Shot Tracker captures new shots while it is running.” The EOF/log-tail detail belongs in advanced/developer material.

### Shot correlation

A saved shot is a correlation of independent events rather than one monolithic record.

The collector must:

- parse GSPro shot packets containing ball data;
- cache the latest GSPro Player state so the club, handedness, target distance, and surface can be attached to the shot;
- match the closest VTrack trajectory result within a small time window;
- detect newly created **or reused/modified** VTrack ShotData folders;
- wait until a camera folder is stable before copying it;
- tolerate a missing trajectory or camera folder rather than losing the entire shot.

Do not tighten matching rules without testing against real VTrack timing behavior.

### Data preservation

The archive is user data and must outlive installation changes.

Default locations are intentionally separated:

```text
C:\Program Files\VTrack Shot Tracker\       installed application
%USERPROFILE%\Documents\VTrackArchive\      database and archived shot media
%LOCALAPPDATA%\VTrackShotTracker\           logs, process state, WebView profile, window state
```

Installer upgrades and uninstalls must **not** delete `Documents\VTrackArchive`.

SQLite schema changes must be conservative, additive migrations whenever practical. Existing shot history is more important than implementation convenience.

### Source fidelity

Store useful source values without destroying their provenance.

Examples:

- VTrack trajectory values are kept in their source metric form and converted to yards for the UI.
- GSPro's original club selection is retained in `gspro_club_raw` even when Bag Mapping converts it to the user's actual club in `club`.
- The raw GSPro JSON and VTrack trajectory line are stored with the shot.

A manual UI correction may change the normalized club/session assignment, but should not erase the original source evidence.

## Application architecture

### Unified launcher

`vtrack_shot_tracker.py` is the source-mode and packaged entry point.

Public commands include:

```text
start
stop
status
review
check-update
update
```

The packaged executable launches separate application-owned roles for the collector, review server, and desktop host and records their state under `%LOCALAPPDATA%\VTrackShotTracker`.

### Collector

`collector/vtrack_shot_collector.py` owns collection, correlation, archive copy, video creation, and SQLite insertion.

It should remain robust when VTrack is not currently producing data. A collector problem must not make historical Shot Review unusable.

The collector writes `collector_heartbeat.json` into the archive so the UI can distinguish a live collector from a merely reachable review server.

### Review server and UI

`review/shot_review.py` contains the local HTTP server, API endpoints, reports, and embedded HTML/CSS/JavaScript workspace.

The server binds to loopback (`127.0.0.1`) rather than exposing the archive to the LAN.

The UI is intentionally a dense desktop launch-monitor workspace, not a mobile-first public website. It should nevertheless remain usable at smaller supported window sizes and in both light and dark themes.

### Desktop host

`vtrack_desktop.py` hosts the local review URL in a dedicated pywebview/WebView2 window.

If WebView2 is unavailable or the native host cannot initialize, the launcher should fall back to the default browser rather than leaving the user with no visible UI.

Closing the main Shot Tracker window may stop the Shot Tracker roles. It must **not** close VTrackToolKit.

## VTrack lifecycle boundary

This is a hard architectural tenet.

### Core application

`VTrackShotTracker.exe start` starts Shot Tracker components only.

`VTrackShotTracker.exe stop` stops Shot Tracker components only.

The core executable must not start, stop, kill, or restart:

- VTrackToolKit;
- LPGAgent;
- VGPconnect;
- GSPconnect;
- other VTrack-owned processes.

Do not reintroduce `--with-vtrack`, `--stop-vtrack`, or equivalent lifecycle flags into the core launcher.

### Optional combined automation

The repository also contains `Start-VTrack.ps1` and `Stop-VTrack.ps1` for an existing simulator/Home Assistant workflow.

Those scripts are intentionally **external composition**: they may manage VTrack and then call the installed Shot Tracker executable.

Do not confuse those scripts with the tracker-only wrappers under `packaging/`.

In beginner documentation, simply say that VTrack and Shot Tracker are separate applications. Move combined automation details to the Advanced Guide.

## Sessions and club identity

Every shot belongs to a session.

- A calendar date receives an automatic session when needed.
- The UI can create a named manual session and mark it active for new shots on that date.
- Existing shots can be moved between sessions.

Club values are normalized through `club_config.py` so aliases do not fragment the UI into duplicate groups.

Bag Mapping is optional. It converts a generic GSPro source club to the club the golfer actually carries.

Examples:

```text
PW -> 46DEG
GW -> 50DEG
SW -> 54DEG
LW -> 58DEG
```

Mappings apply to **new shots**. Preserve `gspro_club_raw` for auditability.

Named wedges and loft-specific wedges are distinct valid clubs. Never assume every `SW` is 54 degrees or every `LW` is 60 degrees without an explicit user mapping.

User-facing copy should display friendly names such as `54° Wedge`; canonical storage codes such as `54DEG` belong in technical documentation.

## Review workspace requirements

The primary workspace is organized around three areas plus a selected-shot metric rail.

### Sessions & shots

The left side organizes:

```text
Session
  -> Club
      -> Shot
```

Requirements:

- sessions and clubs can be expanded/collapsed;
- session, club, and individual shot visibility can be controlled without deleting data;
- the selected shot is visually unambiguous;
- typography should adapt to available panel width instead of remaining artificially tiny;
- users can reassign a shot's club or session;
- multiple clubs and sessions can be displayed together.

### Range

The Range is an analytical canvas, not decoration.

Supported modes include:

- **Dispersion** — top-down landing/total positions and dispersion envelopes;
- **Flight** — top-down direction plus side-on flight-height views;
- **Putting** — top-down green, hole, roll paths, and finish dispersion measured in feet.

The user can switch Carry/Total where applicable, zoom, pan, reset the viewport, and export the range.

All dispersion envelopes must render **behind** shot markers and must not intercept shot selection. Shot points need practical hit targets even when their visible dots are small.

A dispersion ellipse is descriptive of the visible sample. It should enclose the visible shots with a small margin rather than hide or classify shots as mishits.

Beginner documentation should first explain dispersion as “how spread out this visible group of shots is.” Statistical/geometry detail is secondary.

### Replay & strike

Replay/strike panels can include:

- Impact Replay;
- Swing Cam 1 when media exists;
- Swing Cam 2 when media exists;
- Shot Heatmap.

Panels may be shown/hidden, moved, resized, snapped, and exported. Missing optional media should produce a clear no-media state rather than a broken panel.

The strike crosshair identifies the selected impact point. Heat density represents the historical impact pattern. Do not let decorative heat extend obviously beyond the calibrated club-face region.

### Selected-shot metrics

The bottom metric rail should surface the most useful ball, distance, spin, direction, club-delivery, and impact numbers without requiring another dialog.

It should remain readable in both themes and use restrained color to improve scanning rather than turning the UI into a novelty dashboard.

Do not assume every user understands every launch-monitor metric. Tooltips or documentation should explain unfamiliar terms where practical.

## Follow Live and collector status

These concepts must remain separate.

### Follow Live

Follow Live controls selection behavior only.

When enabled, a newly archived shot should become the selected shot and its group should become visible/expanded as appropriate.

When the user intentionally selects an older shot, Follow Live should pause so the UI does not yank the selection away. The user can explicitly resume it.

Beginner explanation: **“Follow live automatically shows the newest shot.”**

### Collector status

The status indicator is based on the collector heartbeat, not merely on the review HTTP server being reachable.

A stale/missing heartbeat must not show a green live-collector state.

Beginner explanation: **“Live/green means Shot Tracker is ready to capture new shots.”**

Advanced/developer documentation may explain the heartbeat implementation.

## Reports and exports

The product should make captured data portable without requiring the original database.

Supported/exported artifacts include, as applicable:

- selected shot CSV;
- session CSV;
- printable coaching/session report;
- landscape dispersion/putting graphic within the report;
- range image/SVG;
- impact/swing MP4 files;
- strike/heatmap image;
- self-contained comparison HTML.

Reports should use human-readable club names and remain useful when printed or saved as PDF.

## UI and interaction tenets

### Professional over decorative

The visual target is a serious launch-monitor/practice application.

Prefer:

- strong hierarchy;
- readable typography;
- consistent spacing;
- restrained, meaningful club/metric colors;
- flat or lightly layered surfaces;
- useful data density.

Avoid oversized ornament, visual noise, gimmicky perspective ranges, and controls that consume more space than the data they operate on.

### Both themes are first-class

Dark mode and light mode must be intentionally designed.

Never add an icon, foreground color, fill, border, hover state, chart annotation, or media overlay that is only legible in one theme.

### Responsive desktop layout

The three major columns are resizable and collapsible.

- Collapsing Replay should collapse toward the right edge and allow Sessions and Range to expand.
- Collapsing Range should leave a narrow center rail while Sessions and Replay expand inward.
- Restoring or resizing columns should not destroy the user's saved workspace unnecessarily.

### Preserve direct manipulation

Shot markers, visibility controls, range pan/zoom, window dragging/resizing, and other direct interactions should have reliable hit targets and should not be blocked by purely visual SVG layers.

### Progressive disclosure

Common actions should be obvious without exposing every advanced option at once.

A casual golfer should be able to use:

- sessions;
- Follow live;
- dispersion;
- shot selection;
- replay;
- metrics;

without first configuring Bag Mapping, exports, comparison profiles, camera-window layout, command-line settings, or Home Assistant.

Advanced functionality should remain discoverable without dominating the beginner workflow.

## Workspace persistence

Workspace state is part of the product experience.

Preferences currently include items such as:

- theme;
- Follow Live;
- visible range groups and hidden shots;
- session/club expansion;
- Range mode, distance mode, zoom, and pan;
- column collapse/ratios;
- replay window visibility and geometry;
- comparison profile.

Browser-local storage can provide responsive persistence, but a durable copy in SQLite should survive a WebView profile reset or application reinstall.

Do not store the user's shot archive inside `%LOCALAPPDATA%` or Program Files.

## Packaging requirements

Ordinary users should install a Windows setup executable and should not need Python.

The normal user should not need to run PowerShell to complete installation or first launch.

The packaging pipeline uses:

- PyInstaller one-folder output;
- bundled FFmpeg;
- Inno Setup;
- GitHub Actions for CI and tagged releases.

The desktop app depends on Microsoft Edge WebView2 Runtime. Missing WebView2 should degrade to browser mode.

The installer and portable artifacts derive their version from `vtrack_version.py`, which is the single version source of truth.

## Versioning and releases

The project uses Semantic Versioning.

While the product is still in initial development, `0.x.y` releases are expected. Do not declare `1.0.0` until the first stable public release is intentionally approved.

Typical intent:

- patch: compatible bug fix;
- minor: compatible feature release;
- major: breaking change or intentional first stable release.

A release tag must exactly match the source version, for example `v0.5.0` for `__version__ = "0.5.0"`.

Avoid hard-coding the current version in general beginner documentation unless the exact version is materially necessary.

## Update and uninstall safety

The updater may download a newer GitHub Release installer after validating version and checksums.

Updates should stop only Shot Tracker-owned processes before opening the installer.

Uninstall must not remove the archive. The user's database and shot media are personal data.

User-facing uninstall instructions should explicitly distinguish “remove the program” from “delete my shot history.”

## Security and privacy tenets

- Bind the review service to loopback only unless a deliberate future design changes the threat model.
- Treat archive file paths and report-opening URLs as untrusted input and validate them.
- Do not expose arbitrary local file browsing through the WebView bridge.
- Do not send shot data to remote services implicitly.
- Update downloads must be versioned and integrity-checked.
- Avoid adding dependencies when the standard library or existing stack is adequate.

## Testing expectations

Before merging application changes, maintain at least these checks:

```powershell
python -m py_compile vtrack_shot_tracker.py vtrack_desktop.py vtrack_version.py vtrack_updater.py collector\vtrack_shot_collector.py review\shot_review.py tools\backfill_vtrack_clubs.py tools\check_ui_js.py
python -m unittest discover -s tests -v
$js = python tools/check_ui_js.py
node --check $js
Remove-Item $js
```

Changes that touch collection should be tested against realistic log/ShotData timing where possible.

Changes that touch the embedded UI should be checked in both light and dark mode and with more than one club/session visible.

Changes that touch lifecycle management must verify that stopping Shot Tracker does not stop VTrackToolKit.

Changes that alter normal user workflows should include a documentation review from at least these perspectives:

- first-time golfer;
- regular practice user;
- advanced simulator owner.

Ask: “Can the first-time user succeed without reading the Advanced Guide?”

## Guidance for AI coding agents

When asked to modify this repository:

1. Read this file, `README.md`, and `docs/ARCHITECTURE.md` first.
2. Inspect the current implementation before assuming prior conversation context still matches the repository.
3. Treat the repository's current default branch as the source of truth for version and behavior.
4. Identify which user persona the change primarily affects.
5. Prefer targeted, backward-compatible changes over large rewrites.
6. Preserve the archive schema and user data unless the task explicitly requires a migration.
7. Never reintroduce VTrack process ownership into the core launcher.
8. Keep collector failure independent from historical viewer availability.
9. Preserve original source values when adding normalization or user-facing mappings.
10. Do not hard-code the current release number in general documentation when `<version>` or “latest release” is sufficient.
11. Update the appropriate layer of documentation whenever a visible workflow changes: Quick Start for first-run changes, User Guide for normal-use changes, Advanced Guide for technical workflows.
12. Keep internal terminology out of beginner instructions unless the user must act on it.
13. Update tests when a contract intentionally changes; do not delete tests simply to make CI pass.
14. Run or reason through the existing CI checks before presenting work as complete.

When a requested change conflicts with one of these tenets, call out the conflict explicitly rather than silently implementing it.
