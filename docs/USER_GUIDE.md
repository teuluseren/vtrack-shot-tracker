# User Guide

This guide explains vTrack Shot Tracker in normal golf-simulator language.

You do **not** need to learn every feature before using the app.

If this is your first time, read **Part 1: Beginner workflow** and start hitting shots. Come back to the later sections when you want more control.

If you have not installed the app yet, start with the **[Quick Start](QUICK_START.md)**.

# Part 1 — Beginner workflow

## What Shot Tracker is doing for you

When VTrack, GSPro, and Shot Tracker are all running, Shot Tracker watches for each new shot and saves it to your local archive.

You can then use the app like a permanent practice notebook:

- see where your shots finished;
- compare groups of shots;
- replay impact;
- review strike location;
- see the numbers for one shot;
- come back to the session later.

You do not need to export a CSV from GSPro after every practice session.

## The four areas of the screen

The app is easiest to understand as four areas.

### 1. Sessions & shots — left side

This is your shot history.

It is organized like folders:

```text
Session
  → Club
      → Shot
```

A **session** is simply a group of shots from one practice, fitting, lesson, or test.

### 2. Range — middle

This is where you see the group visually.

For your first sessions, use:

- **Dispersion**
- **Carry**

That gives you a simple top-down view of where the shots carried.

### 3. Replay & strike — right side

This is where you can watch impact replay and see club-face strike information when those files/data are available.

### 4. Shot data — bottom

These tiles show the numbers for the shot you currently have selected.

Examples include carry, total, ball speed, spin, club speed, launch, and club delivery.

## Your first practice session

A good first session is intentionally simple.

1. Start Shot Tracker.
2. Start VTrack and GSPro normally.
3. Make sure **Follow live** is on.
4. Hit 5–10 shots with one club.
5. Watch the shot dots build on the Range.
6. Click one shot to inspect it.
7. Watch Impact Replay if available.
8. Look at the shot numbers across the bottom.
9. Turn **Follow live** back on before hitting again if you paused it.

That is enough to get value from the app.

## A few terms used on the screen

### Carry

How far the ball travels through the air before first landing.

### Total

Carry plus rollout after landing.

### Dispersion

How spread out a group of shots is.

A tighter group generally means the results are more consistent. A wider group means the shots finished farther apart.

Shot Tracker does not automatically decide that an outlier is a “bad shot.” If you leave it visible, it is part of the group.

### Flight

The direction and height of the ball's trajectory.

### Strike / impact location

Where the ball contacted the club face.

### Follow live

“Show me the newest shot automatically.”

It does not mean the same thing as the collector status light.

# Part 2 — Everyday controls

## Top toolbar

The top row contains the controls you are most likely to use during a normal practice session.

### Clear range

**Clear range** hides the currently plotted shot groups.

It does **not** delete anything.

Your sessions, shots, videos, and database records remain saved.

Use the visibility controls in **Sessions & shots** to show a session or club again.

### Light / Dark

Switches the app between light and dark appearance.

Your choice is remembered.

### Bag

Opens **Bag Mapping**.

You only need this when the club name coming from GSPro is different from the club you want Shot Tracker to use.

Example:

```text
GSPro says: SW
Your club:  54° Wedge
```

You can tell Shot Tracker:

```text
SW → 54° Wedge
```

This mapping applies to new shots.

You can leave Bag Mapping alone if GSPro's club names already work for you.

### Follow live

When **Follow live** is on, each new archived shot becomes the selected shot automatically.

This is useful while you are hitting balls because the replay, range marker, and shot data all move to the newest shot.

If you click an older shot, Follow live pauses so the app does not pull you away from what you are reviewing.

Select **Follow live** again when you want to return to automatic new-shot selection.

### Version / Update

Shows the installed Shot Tracker version.

Select it to check for a newer release.

### Collector status

The status at the upper-right tells you whether the part of Shot Tracker that watches for new shots is currently alive.

In simple terms:

- **live/green** — ready to capture new shots;
- **stopped/red** — the app can still show old shots, but it is not currently capturing new ones.

If this status is stopped while VTrack is working, see **[Installation & Troubleshooting](INSTALLATION.md)**.

# Part 3 — Sessions & shots

## Automatic sessions

Shot Tracker can create a session for the day automatically.

That means you can simply start hitting without naming anything first.

## Named sessions

Use **+ New session** when you want a meaningful practice label.

Examples:

```text
Driver practice
Driver fitting - Ventus Blue
7 Iron gapping
Wedge matrix
New ball test
Lesson with coach
```

New shots are then grouped under the active named session.

## Expanding and collapsing

Select the arrows/controls beside sessions and clubs to open or close them.

This only changes what you can see in the list. It does not change your data.

The entire Sessions panel can also be resized or collapsed.

## Visibility controls

The eye/visibility controls decide what appears on the Range.

You can hide:

- a whole session;
- one club;
- one individual shot.

This is useful when comparing clubs or temporarily removing a result from the visual group.

Hiding is non-destructive.

## Selecting a shot

Click a shot row to make that shot active.

The app then updates:

- the selected marker on the Range;
- Replay & strike;
- the data tiles at the bottom.

Clicking an older shot pauses Follow live.

## Moving or reclassifying a shot

Use the shot-row action menu when a shot was assigned to the wrong club or session.

You can:

- choose a different club;
- move the shot to another session.

The club list includes woods, hybrids, irons, named wedges, loft-specific wedges, and putter.

Available loft-specific wedges include:

```text
46°, 48°, 50°, 52°, 54°, 56°, 58°, 60°, 62°, 64°
```

This is especially useful when GSPro used a generic wedge name but you want your history grouped by actual loft.

# Part 4 — Range

The Range has three modes.

You can use only Dispersion forever if that is all you need.

## Dispersion

This is the normal top-down practice-range view.

Each visible shot is plotted where it finished according to the selected distance mode.

Shots for each club use a consistent color.

The colored outline around a group is the **dispersion envelope**. It helps show the size and direction of the group.

The envelope is only a visual summary. It does not decide which shots are good or bad.

## Carry vs Total

Choose:

- **Carry** to compare first landing distance;
- **Total** to include rollout where that information is available.

Carry is often the cleaner choice for gapping and launch-monitor practice because rollout can change with simulated ground conditions.

Total can be useful when you care about final distance.

## Clicking shots on the Range

Shot dots are selectable.

Click one to review that exact shot.

The app uses a larger invisible click area than the visible dot, so you do not need to hit the tiny center perfectly.

Dispersion envelopes are visual only and should not block shot selection.

## Zoom

Use the floating controls:

- **+** — zoom in;
- **−** — zoom out;
- **Reset** — return to the normal view.

You can also use the mouse wheel, a supported touchpad pinch, or keyboard `+` / `-` while the Range is focused.

## Pan

Click and drag the Range when you want to move the visible area.

Select **Reset** to return to the normal centered view.

## All axis values

Turn on **All axis values** if you want more grid labels.

Leave it off for a cleaner range.

## Session and club pills

The pills below the Range identify the visible groups.

A pill can show things such as:

- session name;
- club name;
- shot count;
- average distance.

Select a pill to open a comparison summary.

## Flight

**Flight** adds trajectory-oriented views.

Use it when you want to look beyond the landing pattern and inspect how shots traveled.

It includes a top-down direction view and a side-on height/flight view.

The same club colors, visibility choices, shot selection, zoom, and pan ideas still apply.

## Putting

**Putting** changes the display from a driving range to a top-down green.

Putting uses **feet** rather than yards.

Depending on available data, it can show:

- starting point;
- target hole/flag;
- roll paths;
- finish positions;
- putting dispersion.

Selecting a putter group may switch the app to this mode automatically.

# Part 5 — Replay & strike

## Impact Replay

When VTrack provides compatible replay media, the selected shot can play in **Impact Replay**.

The replay loops automatically so you can watch impact repeatedly.

If one shot has no replay, that does not mean the entire session failed to save.

## Shot Heatmap

The heatmap helps answer two different questions:

1. **Where did this selected shot strike the face?**
2. **Where do I tend to strike this club over many shots?**

The crosshair shows the selected shot's impact point.

The colored heat pattern shows the broader historical strike pattern for that club.

The heat is constrained to the calibrated club-face region.

## Swing Cam 1 / Swing Cam 2

These are optional media windows.

They only contain useful video when compatible media has been archived.

If no file exists, the app should show a clear unavailable-media message rather than breaking the workspace.

## Windows menu

Use **Windows** to choose which Replay & strike panels you want visible:

- Impact Replay;
- Swing Cam 1;
- Swing Cam 2;
- Shot Heatmap.

## Moving and resizing panels

Replay/strike panels can be moved and resized.

The app remembers the layout.

Use **Snap grid** when you want to tidy the panels without throwing away their saved sizes.

## Export

Use **Export** in Replay & strike to choose one or more available panels to save.

Video exports use MP4 where available. Strike/heatmap exports are images.

# Part 6 — Shot data at the bottom

The bottom data rail shows the currently selected shot.

Depending on what VTrack and GSPro provided, you may see:

- carry;
- total distance;
- ball speed;
- spin;
- launch angle/direction;
- club speed;
- attack angle;
- club path;
- face-to-target;
- loft;
- strike location;
- VTrack trajectory values.

Not every shot has every number.

Shot Tracker should show a missing value as unavailable rather than guessing one.

## Export shot

Downloads the selected shot as a CSV file.

## Open folder

Opens the archived folder for that shot when one exists.

Most golfers will never need to use **Open folder**; it is mainly useful for troubleshooting or inspecting the underlying media.

# Part 7 — Comparisons and reports

## Club/session comparison

Select one of the session or club pills below the Range to open a comparison.

The comparison can use Woman, Man, Senior, or Junior reference profiles.

A score of **100%** means the displayed results match that selected reference according to the app's comparison model. Values can exceed 100%.

Treat this as a practice/fitting reference, not an official handicap or universal player rating.

## Session reports

A session report is useful for:

- lessons;
- club fitting;
- practice review;
- saving a snapshot of a session;
- sharing results with someone else.

The report can include:

- session name/details;
- club summaries;
- a landscape dispersion graphic;
- putting graphic when applicable;
- shot-by-shot data.

Use the report window's print function to print it or save it as PDF.

## Other exports

Depending on where you are in the app, exports can include:

- Range image;
- selected-shot CSV;
- session CSV;
- session report;
- comparison HTML;
- replay/strike media.

# Part 8 — Making the workspace comfortable

## Resizing the three main columns

Drag the dividers between:

- Sessions & shots;
- Range;
- Replay & strike.

The app remembers your layout.

Widening Sessions & shots gives the shot list more room and allows its information to be easier to read.

## Collapsing columns

You can collapse a column when you want to give more room to the others.

- Collapsing **Replay & strike** sends it toward the right edge and gives more space to Sessions/Range.
- Collapsing **Range** leaves a narrow center rail while the left and right sections expand inward.

Double-clicking a divider restores the default proportions.

## Saved preferences

Shot Tracker remembers much of your local workspace, including:

- light/dark mode;
- Follow live;
- visible/hidden groups;
- opened sessions/clubs;
- Range mode;
- Carry/Total;
- zoom/pan;
- panel sizes;
- Replay & strike layout;
- comparison profile.

You should not need to rebuild your preferred workspace every time you open the app.

# Part 9 — What is safe and what changes data?

## Viewing actions — safe/non-destructive

These do not delete your stored shots:

- Clear range;
- hide/show shot;
- hide/show club;
- hide/show session;
- collapse/expand;
- zoom/pan;
- switch Carry/Total;
- switch range modes;
- change theme;
- move/resize panels.

## Organizational changes

These change how saved shots are organized:

- reassigning a club;
- moving a shot to another session;
- creating/naming sessions;
- changing Bag Mapping for future shots.

The app should make these actions explicit.

# Part 10 — Where your data lives

Your main archive is normally:

```text
Documents\VTrackArchive\
```

It contains the SQLite database and archived shot media.

Back up this folder if your practice history matters to you.

Normal upgrades and uninstalls are designed to leave it in place.

# Want more control?

You can stop here if you are a normal practice user.

For command-line controls, Home Assistant, portable builds, logs, SQLite, source-mode testing, and other technical workflows, see the **[Advanced Guide](ADVANCED_GUIDE.md)**.
