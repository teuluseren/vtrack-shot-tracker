# Persona & Chaos QA Audit

This document records a share-readiness audit of **vTrack Shot Tracker** from the perspective of the people who are expected to use, support, or modify it.

It complements `REQUIREMENTS_AND_TENETS.md`: the tenets define what should remain true; this audit asks whether the current product actually behaves that way under normal, confusing, and hostile conditions.

## Personas used

### 1. Everyday golfer / simulator owner

Assumptions:

- understands golf and their own simulator;
- may not know Python, PowerShell, SQLite, HTTP, WebView2, or GitHub internals;
- expects the app to work by opening it and hitting shots;
- is likely to treat silence or an unexplained red status as an app failure.

Primary success path:

1. install;
2. open Shot Tracker;
3. start VTrack/GSPro normally;
4. hit shots;
5. see the newest shot selected;
6. click an older shot;
7. inspect range, replay/strike, and metrics;
8. close the app without affecting VTrack.

### 2. Coach / fitter / serious practice user

Assumptions:

- cares about trustworthy grouping and numbers more than implementation details;
- uses named sessions, multiple clubs, Carry/Total, dispersion, strike pattern, reports, and exports;
- may build a large archive over time;
- expects missing values to be obvious rather than silently excluded or invented.

### 3. Simulator hobbyist / power user

Assumptions:

- comfortable with Windows, Home Assistant, PowerShell, logs, portable software, and backups;
- may start/stop components independently;
- expects CLI behavior to be predictable and automation-safe;
- may run unusual configurations or recover from failed installs.

### 4. Developer / AI coding agent

Assumptions:

- can modify any layer of the application;
- must preserve source provenance, archive compatibility, VTrack lifecycle separation, and beginner usability;
- needs tests that are portable rather than tied to one author's archive.

---

# Automated coverage added during this audit

## Launcher and updater chaos tests

The audit added regression coverage for:

- `update --yes`, which is the path used by the UI updater;
- confirmation and cancellation of a command-line update;
- download/verify → tracker-only shutdown → installer launch ordering;
- update checks when already current;
- normalized release URL output;
- an unrelated service occupying the normal review port;
- stale role files whose PID has been recycled by Windows;
- an old role process attempting to delete a newer role record.

## Collector chaos tests

The audit added tests for:

- live-only log tailing from EOF;
- partial log lines;
- log rotation without replaying old log contents;
- GSPro Player-state snapshotting;
- malformed JSON followed by a valid packet;
- Player-state reset when a new GSPro log starts;
- signed VTrack trajectory values;
- corrupted Bag Mapping JSON;
- manual-session rollover to a new calendar day;
- Bag Mapping while preserving `gspro_club_raw`;
- duplicate shot timestamps;
- unrelated/non-numeric ShotData directories.

## Synthetic real-browser workflow

CI now creates a deterministic test archive and drives the actual Shot Review UI in headless Chrome/Edge. The test is intentionally based on normal user actions rather than source-code string matching.

The synthetic archive includes Driver, 7 Iron, 54° Wedge, and putter shots.

The browser workflow verifies:

- the four primary workspace areas render;
- shot rows are present;
- collector status is evaluated through the real heartbeat contract;
- selecting an older shot works and pauses Follow Live;
- metric tiles populate;
- missing replay media produces a deliberate no-media state;
- multiple dispersion groups render;
- Carry/Total switching works;
- Flight mode works;
- a real pointer click on a plotted shot changes selection;
- Putting mode activates and uses feet;
- Bag Mapping includes loft-specific wedges;
- shot reclassification includes loft wedges and putter;
- session reports load and expose Print / Save PDF;
- Clear range does not delete shots;
- theme switching works;
- workspace resize/collapse/window controls exist;
- no unhandled JavaScript exception is raised during the workflow.

This is deliberately synthetic and portable. It does not replace testing against the actual VTrack hardware/log/camera timing path.

---

# Findings fixed on the QA branch

## Update command mismatch — release blocker

**Persona affected:** everyone who installs an update from the UI.

The UI launched:

```text
VTrackShotTracker.exe update --yes
```

but the launcher did not define `--yes`. The background updater therefore exited at argument parsing instead of installing the update.

The QA branch adds `--yes`, restores optional CLI confirmation, uses the verified installer-launch path, stops Shot Tracker-owned roles only, and fixes the update download directory nesting.

## Stale/recycled PID safety — release blocker

**Persona affected:** every Windows user, especially after crashes/reboots.

A role file contained only a PID and arguments. Windows can recycle PIDs, so a stale role file could theoretically identify an unrelated process and the stop path could terminate that process tree.

The QA branch records process identity metadata and refuses to signal a PID when the live process no longer matches the saved identity. Frozen orphan cleanup also verifies the full executable path.

## Port collision — release blocker

**Persona affected:** users running other localhost services.

The old readiness check could treat an unrelated service on port 8765 as a valid Shot Review server.

The QA branch verifies that the responding page contains the vTrack Shot Tracker product signature before reusing the port.

## Role cleanup race

**Persona affected:** users who restart quickly or encounter a crash during startup/shutdown.

An old process could remove a role file written by a newer process. Role cleanup on the QA branch can require the expected PID before deleting the role record.

---

# Positive persona findings

## Everyday golfer

The basic interaction model is simple once installed:

```text
Follow Live on → hit shots → click a shot → inspect Range / Replay & strike / metrics
```

The synthetic browser run confirmed that:

- shot selection works;
- the UI pauses Follow Live when the golfer intentionally reviews an older shot;
- missing media is represented gracefully;
- Clear range is non-destructive;
- theme switching works;
- Bag Mapping and exact wedge choices are accessible without editing data files.

This is consistent with the beginner-first documentation.

## Coach / fitter

Strong current workflows include:

- multiple visible club groups;
- direct shot selection on the range;
- dispersion envelopes that do not block shot markers;
- Carry/Total switching;
- putting view;
- named sessions;
- exact loft-specific wedges;
- reports and CSV export;
- strike heatmap plus selected impact location.

## Power user

Strong current contracts include:

- a stable tracker-only CLI;
- explicit separation between tracker-only commands and combined VTrack/Home Assistant scripts;
- local archive ownership;
- portable packaging;
- version/checksum-verified updates;
- source-mode development commands.

## Developer / AI agent

Strong current safeguards include:

- Requirements & Tenets;
- Architecture documentation;
- SemVer single source of truth;
- Windows CI;
- updater checksum tests;
- club-normalization tests;
- API/UI contract tests;
- the new chaos suites and portable browser smoke workflow.

---

# Open findings before broad sharing

These findings are confirmed from the current implementation but are not all appropriate to solve in one QA patch.

## 1. Shared-user update distribution while the repository is private

**Severity:** release gate

The updater uses unauthenticated GitHub Release URLs. That is appropriate for public releases, but ordinary users cannot use an unauthenticated updater against a private repository.

Before sharing outside the repository's authorized GitHub users, choose a distribution model:

- make the repository/releases publicly accessible; or
- publish installers and update metadata from a public distribution location; or
- intentionally add an authenticated/private distribution design.

Do not add a GitHub personal access token to the desktop application.

## 2. Manual shot reclassification does not use shared canonical club normalization

**Severity:** high

The viewer currently uppercases the submitted club string instead of routing it through `canonical_club()`.

That means an API/old-client input such as `3w` may become `3W`, while the canonical project code is `W3`, potentially fragmenting club groups.

Normal current dropdown use submits canonical values, so this is mainly an edge/API/compatibility failure. The storage layer should still enforce the invariant.

## 3. Shot navigator silently limits itself to the newest 5,000 shots

**Severity:** high for long-term users

`ShotStore.list_shots()` selects `ORDER BY id DESC LIMIT 5000`, while the session list counts the complete database.

After enough use, an old session can therefore report a shot count while some/all of those shots are absent from the navigator and range. The data is not deleted, but the behavior looks like missing archive history.

A share-ready archive application needs deliberate pagination/lazy session loading or an explicit visible-history scope rather than silent truncation.

## 4. Session report dispersion requires GSPro carry even when VTrack carry exists

**Severity:** medium/high for coaches and fitters

The report's range plot currently reads `gspro_carry_yards` directly. A shot with valid `vtrack_carry_yards` but missing GSPro carry can disappear from the report dispersion graphic.

The normal application already treats VTrack and GSPro as complementary sources. Reports should use the same carry fallback policy as the live UI.

## 5. Media HTTP Range parsing is not defensive

**Severity:** medium

Malformed or unusual `Range` headers can raise conversion errors in the media server instead of returning a controlled HTTP range response.

Harden `serve_file()` to validate ranges, reject unsatisfiable ranges with 416, and correctly support open-ended/suffix ranges used by browsers/media elements.

## 6. Mutation endpoints should validate local same-origin intent

**Severity:** medium security hardening

The review server correctly binds to loopback. However, several POST/PATCH endpoints mutate local state without validating Origin/Host intent.

The update endpoint is stronger because it requires a custom confirmation header. Other mutations should receive equivalent localhost/same-origin protection so a malicious webpage cannot blindly trigger state changes against `127.0.0.1`.

## 7. Open Folder can fail silently in the UI

**Severity:** medium usability

If the selected shot has no archived folder, the UI's Open Folder action can fail without explaining why.

For a beginner, disable the button when unavailable or show a clear message such as “No archived shot folder is available for this shot.”

## 8. Comparison profiles need stronger trust framing

**Severity:** high for coach/fitter credibility

The Woman / Man / Senior / Junior comparison references are implemented with hard-coded reference values/factors. The UI labels the result as a reference comparison, but the calculation methodology and source basis are not exposed.

Before presenting the feature broadly to coaches/fitters, either:

- publish the method and defensible sources;
- make the benchmarks user-configurable; or
- reframe/remove the numeric score so it cannot be mistaken for an authoritative performance standard.

## 9. Collector log-file races

**Severity:** medium/high reliability

Log discovery/stats/open operations can race with VTrack log rotation/deletion. A disappearing file should be treated as “try again next poll,” not as a collector-ending exception.

## 10. GSPro JSON block framing is brace-count based

**Severity:** medium/high reliability

The parser currently counts raw `{` and `}` characters. Braces inside JSON string values can distort the depth, and a truncated unclosed block can make the parser consume subsequent lines indefinitely.

Use JSON-string-aware structural scanning and a bounded recovery strategy when a fresh timestamped top-level packet arrives.

## 11. FFmpeg work is synchronous in the collector

**Severity:** needs hardware stress measurement

The collector can encode impact, Cam 1, and Cam 2 videos before inserting the shot row. Under rapid shot cadence or slow storage this could delay processing and build a correlation backlog.

Do not redesign this blindly. Measure on the simulator PC with a burst test first. If backlog appears, insert the shot before media encoding and move video work to a bounded background worker that updates media paths afterward.

## 12. Corrupt/unwritable archive startup needs a beginner-safe error path

**Severity:** high supportability

If SQLite initialization fails due to corruption, locking, disk error, or permissions, the launcher can fail before presenting a useful recovery screen.

Never overwrite a corrupt archive automatically. Surface the archive path, preserve the original file, and provide a clear recovery/backup message.

## 13. Embedded UI module is too monolithic for safe community contribution

**Severity:** maintainability

`review/shot_review.py` contains the server, API, report generator, HTML, CSS, and a large JavaScript application. There are legacy/duplicate JavaScript declarations whose later definitions override earlier definitions.

That increases the chance that a human or AI contributor edits an inactive function and believes the behavior changed.

Before inviting broad contribution, remove dead duplicate declarations and strongly consider splitting static UI assets/modules while preserving the local/offline packaging model.

---

# Manual simulator/hardware test matrix

These cannot be truthfully certified by GitHub CI because the hosted runner does not have LAON VTrack, GSPro, camera hardware, the real Windows package storage, or the simulator's timing characteristics.

## First-run clean PC

- install the built installer on a supported Windows machine;
- launch Shot Tracker before VTrack;
- verify historical/empty review opens rather than failing;
- start VTrack and GSPro normally;
- hit the first shot;
- verify club, ball data, trajectory, camera folder, replay, and session assignment;
- close Shot Tracker and verify VTrack continues running.

## Rapid-shot stress

Recommended test:

- hit 20–30 shots at the shortest realistic cadence;
- mix Driver, iron, wedge, and putter selections;
- change clubs quickly in GSPro;
- verify no shot is duplicated, skipped, or assigned the previous club;
- compare shot timestamps/log lines/ShotData folder numbers against database rows;
- watch collector CPU/disk use and log backlog;
- verify video encoding does not cause correlation drift.

## VTrack restart / log rotation

- run Shot Tracker continuously;
- close/reopen VTrack/GSPro or otherwise force new log files;
- verify old club state is not inherited;
- verify old log history is not imported;
- hit the first shot in the new log and validate all fields.

## Camera degradation

Test shots with:

- normal camera frames;
- delayed ShotData folder completion;
- missing impact frames;
- missing one raw camera sequence;
- temporarily locked/read-only files if practical.

The shot record must survive even when media does not.

## Archive degradation

Using a backup/test archive only:

- make archive directory read-only;
- fill the disk or simulate insufficient free space if practical;
- hold the SQLite file open/locked;
- provide a deliberately corrupt SQLite copy.

The app must fail safely, preserve original data, and give the user an actionable message.

## Long-history test

Generate or copy a test database containing more than 5,000 shots across many sessions. Confirm every session can still be navigated intentionally after the list-loading design is fixed.

## Update/uninstall test

On an installed test build:

- update from one real packaged version to a newer version;
- verify archive/media/preferences survive;
- cancel an update and verify the current app keeps working;
- interrupt installer launch/download where practical;
- uninstall and verify `Documents\VTrackArchive` remains;
- confirm VTrack is never terminated by tracker-only update/stop/uninstall actions.

---

# Share-readiness gates

Before a broad public/share release, this audit recommends requiring all of the following:

1. Windows unit/contract/chaos CI passes.
2. Synthetic real-browser workflow passes.
3. A packaged installer is tested on a clean simulator PC.
4. At least one real VTrack/GSPro burst session is reconciled against the archive.
5. VTrack restart/log-rotation behavior is tested.
6. Update and uninstall are tested with the packaged executable.
7. Distribution/update access works for a user who is not a repository collaborator.
8. Long-history behavior has an intentional design; no silent 5,000-shot truncation.
9. Comparison-profile methodology is made trustworthy or reframed.
10. All remaining high-severity audit findings are fixed or explicitly deferred with a release note.

A green CI run is necessary, but it is not by itself proof that the hardware integration has been stress-tested.
