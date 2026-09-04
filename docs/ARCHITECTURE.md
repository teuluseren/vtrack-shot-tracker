# Architecture

## Application launcher

`vtrack_shot_tracker.py` is the source and packaged entry point. The installed executable exposes `start`, `stop`, `status`, `review`, `check-update`, and `update`; background collector, viewer, and desktop-host modes are internal commands of the same executable. Process identity records, logs, native window state, the persistent WebView profile, and verified update downloads live under `%LOCALAPPDATA%\VTrackShotTracker`.

`vtrack_updater.py` queries the latest stable GitHub Release, compares versions using SemVer precedence, requires the exact versioned installer and checksum assets, and verifies the installer with SHA-256 before it can launch. The browser UI starts the same packaged `update --yes` command, which stops only the tracker processes before opening the in-place Inno Setup upgrade.

The archive remains under `Documents\VTrackArchive`, outside both the source tree and install directory, so installer upgrades and uninstalls do not modify user data.

## Collector

`collector/vtrack_shot_collector.py` tails VTrack/GSPro logs, tracks the current GSPro player/club state, correlates VTrack trajectory results with GSPro shot packets, detects new/updated VTrack ShotData folders, archives the shot folder, and writes a normalized row to SQLite.

The collector also ensures the session tables/columns exist. A calendar day gets an automatic session unless the UI has set a named active session for that day.

## Viewer

`review/shot_review.py` is a standard-library HTTP server bound to `127.0.0.1:8765`. It serves one self-contained browser UI plus JSON/media/report endpoints.

Important routes include:

- `/api/shots`
- `/api/shot/<id>`
- `PATCH /api/shots/<id>` (club reclassification and session move)
- `/api/sessions`
- `/media/<id>/impact`
- `/report/session/<id>`
- `/export/session/<id>.csv`

The browser polls for new shots but avoids re-rendering the selected shot unless the selected shot actually changes, so looping replay does not force the user's scroll/selection state to jump. Club groups start collapsed; an incoming shot expands its session and normalized club group only while Follow Live is active. Versioned workspace preferences restore column/tree expansion, visibility, replay window geometry, Follow Live, range controls/zoom, theme, and golfer profile. They are cached in browser-local storage for responsive updates and mirrored to `app_settings.ui_preferences_v1` in the archive database for reinstall/profile-reset durability.

## Windows desktop host

`vtrack_desktop.py` hosts the unchanged local Shot Review URL in a pywebview WinForms window backed explicitly by Microsoft Edge WebView2. The desktop process is separately tracked, and closing the main window is treated as exiting the application: its callback stops the app-owned viewer and collector while leaving VTrackToolKit untouched. Window geometry and WebView storage persist under `%LOCALAPPDATA%\VTrackShotTracker`; a second durable copy of workspace preferences and bag mappings lives in the archive database. Only validated `127.0.0.1:8765` report URLs may cross the JavaScript bridge into native child windows. Downloads are enabled and external links remain delegated to the system browser. If WebView2 is missing, the launcher falls back to the browser while keeping collection available.

## Sessions

Sessions are stored in SQLite. Existing data is migrated conservatively by creating one automatic session for each shot date. `New session` creates a named session and stores its id in `app_settings.active_session_id`.

## Range groups

Range selection is keyed by `session_id + club`. This allows several clubs and/or the same club from several sessions to be displayed simultaneously.

The browser separates putter codes (`PT`, `PUTT`, and `PUTTER`) from long-game clubs. Long-game dispersion and flight stay on the fixed yard-scale range; putters use an automatically scaled top-down green, capped at 90 feet, with a target hole, roll paths, and finish envelopes. Selecting a putter automatically opens that view. Printable mixed-session reports render the two plots separately.

## Strike heatmap

The strike heatmap uses all archived shots for the selected club that contain both horizontal and vertical face-impact values. A kernel-density field is calculated client-side and composited through a softly feathered mask for the calibrated face region of the front-facing driver, wood, hybrid, iron, or putter reference image. The fixed center reference and selected-shot marker are drawn sharply above that heat layer.

## Packaging and releases

PyInstaller creates a one-folder application containing the Python runtime and the separate FFmpeg executable. Inno Setup installs that directory under Program Files and creates Start menu commands. `vtrack_version.py` is the single SemVer source used by the application, artifact names, installer metadata, and release-tag validation.
