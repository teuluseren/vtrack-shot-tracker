# vTrack Shot Tracker

**vTrack Shot Tracker** is a Windows companion for golfers using **LAON VTrack + GSPro**. It automatically saves new shots and gives you one place to review dispersion, ball flight, impact replay, strike pattern, sessions, club comparisons, and reports.

You do **not** need to export GSPro CSV files, copy VTrack folders by hand, or install Python to use the normal Windows app.

> **Project status:** active pre-1.0 development. The app is usable, but installation, compatibility, UI, and reporting are still being refined.
>
> **Independent project:** vTrack Shot Tracker is an independent community project. It is not affiliated with, sponsored by, or endorsed by LAON PEOPLE, VTrack, GSPro, or other simulator/launch-monitor vendors. Product names are used only to describe compatibility and interoperability.

## Which guide should I use?

You do not need to read everything.

| If you are... | Start here |
| --- | --- |
| Installing it for the first time | **[Quick Start](docs/QUICK_START.md)** |
| A golfer who wants to learn the app | **[User Guide](docs/USER_GUIDE.md)** |
| Comfortable with Windows, Home Assistant, portable builds, or troubleshooting | **[Advanced Guide](docs/ADVANCED_GUIDE.md)** |
| Showing the app to someone else | **[Demo Walkthrough](docs/DEMO.md)** |
| Contributing code or using an AI coding agent | **[Requirements & Tenets](docs/REQUIREMENTS_AND_TENETS.md)** |

## What it does

Once vTrack Shot Tracker and VTrack are running, new shots can be saved automatically.

For each shot, the app can combine information from VTrack and GSPro such as:

- carry and total distance;
- ball speed, launch, and spin;
- club speed and delivery data;
- left/right result and apex;
- club-face impact location;
- impact replay video;
- session and club information.

Everything is then organized into a local shot history that you can reopen later.

## The app at a glance

The main screen has four areas:

1. **Sessions & shots** — find and organize your practice sessions and individual shots.
2. **Range** — see dispersion, ball flight, or putting results.
3. **Replay & strike** — watch impact replay and review strike location.
4. **Shot data** — see the numbers for the currently selected shot.

A normal practice session can be as simple as:

1. Start **vTrack Shot Tracker**.
2. Start **VTrack** the way you normally do.
3. Open GSPro and get ready to hit.
4. Hit shots.
5. Let **Follow live** move to each new shot automatically.
6. Review the range, replay, strike pattern, and shot data as you practice.

That is all a casual user needs to know to get started.

## Highlights

- Automatic capture of new VTrack/GSPro shots.
- Daily and named practice sessions.
- Multi-club dispersion with selectable shot dots.
- **Dispersion**, **Flight**, and **Putting** range views.
- **Carry** and **Total** distance views.
- Zoom and pan on the range.
- Impact replay and club-face strike heatmaps.
- Optional swing-camera panels when compatible media exists.
- Light and dark themes.
- Bag Mapping for matching GSPro club names to the clubs you actually carry.
- Loft-specific wedges such as 50°, 54°, 58°, and 60°.
- Manual shot reclassification and session moves.
- Session reports, comparisons, CSV exports, and range images.
- Saved workspace layout, visibility, theme, range view, and replay-window positions.
- Local storage: your shot history stays on the simulator PC.

## Install

For normal use, download the latest Windows installer from the repository's **Releases** page:

```text
VTrackShotTracker-Setup-<version>.exe
```

Install it, then open **vTrack Shot Tracker** from the Windows Start menu.

Python is not required.

For step-by-step help, including Windows SmartScreen and first-shot verification, use the **[Quick Start](docs/QUICK_START.md)**.

## A few golf terms used in the app

If you are new to launch-monitor software:

- **Carry** — how far the ball travels through the air before first landing.
- **Total** — carry plus rollout after landing.
- **Dispersion** — how spread out a group of shots is left/right and long/short.
- **Flight** — the shape and direction of the ball's trajectory.
- **Strike / impact location** — where the ball contacted the club face.
- **Session** — a group of shots from one practice, fitting, lesson, or test.

The app does not automatically decide that an outlying shot is a “bad shot” or mishit. If it is visible, it is part of the displayed group until you choose to hide it.

## Bag Mapping

GSPro may say you hit a generic club such as **SW**, while you think of that club as your **54° wedge**.

Bag Mapping lets you connect the two:

```text
GSPro PW → 46° Wedge
GSPro GW → 50° Wedge
GSPro SW → 54° Wedge
GSPro LW → 58° Wedge
```

This is optional. New shots use the mapped club, while Shot Tracker also keeps the original GSPro club value.

## Follow live and the status light

These are separate ideas:

- **Follow live** means “automatically show me the newest shot.”
- The status light means “is the shot-collection part of the app currently running?”

You can still browse and review old shots even when VTrack is closed or the collector is not running.

## VTrack stays separate

Starting vTrack Shot Tracker does **not** start VTrackToolKit.

Stopping vTrack Shot Tracker does **not** stop VTrackToolKit.

They are separate applications. This makes the tracker safer to use with an existing simulator setup.

Advanced users can optionally use the repository's Home Assistant/PowerShell helper scripts to start or stop both together. See the **[Advanced Guide](docs/ADVANCED_GUIDE.md)**.

## Your data stays local

The important user data is stored under:

```text
%USERPROFILE%\Documents\VTrackArchive\
```

That folder contains the shot database and archived media. Back it up if the shot history matters to you.

The normal application does not require a cloud account or upload your shot archive as part of normal operation.

Upgrading or uninstalling the application is designed to leave the archive in place.

## Security and privacy

Do not post real shot archives, simulator logs, replay videos, credentials, private LAN details, or other personal simulator data in public issues.

Security-sensitive reports should follow **[SECURITY.md](SECURITY.md)**. Contributors should use synthetic fixtures rather than data copied from a real simulator installation.

## Documentation

- **[Quick Start](docs/QUICK_START.md)** — beginner-friendly install and first practice session.
- **[Installation Guide](docs/INSTALLATION.md)** — fuller installation, update, uninstall, and recovery instructions.
- **[User Guide](docs/USER_GUIDE.md)** — plain-language walkthrough of the app.
- **[Advanced Guide](docs/ADVANCED_GUIDE.md)** — Home Assistant, command line, portable builds, troubleshooting, and power-user workflows.
- **[Demo Walkthrough](docs/DEMO.md)** — beginner and advanced demo scripts.
- **[Requirements & Tenets](docs/REQUIREMENTS_AND_TENETS.md)** — product intent and engineering guidance for humans and AI agents.
- **[Architecture](docs/ARCHITECTURE.md)** — implementation-level component overview.
- **[Asset Policy](docs/ASSET_POLICY.md)** — provenance and trademark rules for images and other non-code assets.
- **[Contributing](CONTRIBUTING.md)** — contribution workflow and project expectations.
- **[Contributor License Agreement](CONTRIBUTOR_LICENSE_AGREEMENT.md)** — rights granted by contributors so the project can remain dual-licensed.
- **[Commercial Licensing](COMMERCIAL_LICENSE.md)** — when a separate commercial license may be required.
- **[Changelog](CHANGELOG.md)** — development history.

## For developers and contributors

The project is intentionally friendlier to golfers than to developers at first glance. Developer material lives here rather than in the beginner workflow.

Read **[Requirements & Tenets](docs/REQUIREMENTS_AND_TENETS.md)** and **[Contributing](CONTRIBUTING.md)** before changing application behavior.

Contributions are accepted under the **[Contributor License Agreement](CONTRIBUTOR_LICENSE_AGREEMENT.md)**. Contributors keep copyright in their work while granting the project the rights needed to distribute and relicense accepted contributions.

Run the current source against the normal archive:

```powershell
python .\vtrack_shot_tracker.py dev
```

Run the automated checks:

```powershell
python -m py_compile vtrack_shot_tracker.py vtrack_desktop.py vtrack_version.py vtrack_updater.py collector\vtrack_shot_collector.py review\shot_review.py tools\backfill_vtrack_clubs.py tools\check_ui_js.py
python -m unittest discover -s tests -v
$js = python tools/check_ui_js.py
node --check $js
Remove-Item $js
```

Build a Windows package:

```powershell
python -m pip install --requirement requirements-build.txt
.\packaging\build.ps1
```

The project uses Semantic Versioning. `vtrack_version.py` is the single version source of truth. Pre-1.0 releases remain in the `0.x.y` range until the first stable public release is intentionally approved.

## Repository layout

```text
vtrack_shot_tracker.py       application launcher
vtrack_desktop.py            Windows desktop window
vtrack_version.py            version source of truth
vtrack_updater.py            update checking and installer launch
club_config.py               club normalization and Bag Mapping
collector/                   automatic shot collection/archive logic
review/                      local review server and embedded UI
docs/                        user, advanced, architecture, and agent documentation
packaging/                   Windows build and installer files
tests/                       automated tests
tools/                       development/archive utilities
.github/workflows/           CI and release automation
```

## License

vTrack Shot Tracker is **source-available** under the **PolyForm Shield License 1.0.0**. It is not MIT-licensed and should not be described as OSI open source. See [`LICENSE`](LICENSE) for the project notice and the official PolyForm Shield terms.

PolyForm Shield allows broad use, modification, and redistribution for permitted purposes, but it does not permit providing a product that competes with vTrack Shot Tracker or with products the licensor or its affiliates provide using the software. The official license terms control if there is any difference between this summary and the license.

A separate commercial license may be available for competing, OEM, white-label, bundled, hosted, resale, or proprietary-product uses; see **[Commercial Licensing](COMMERCIAL_LICENSE.md)**.

Packaged releases contain third-party components under their own licenses, including a separate FFmpeg executable; see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Third-party trademarks and product names remain the property of their respective owners; see **[Asset Policy](docs/ASSET_POLICY.md)**.
