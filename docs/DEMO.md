# Demo Walkthrough

This page gives you two ways to show vTrack Shot Tracker to someone else.

Use the **Beginner demo** for most golfers.

Use the **Advanced demo** for simulator owners who immediately ask about automation, detailed comparison, exports, or how the app works under the hood.

# Beginner demo — 5 minutes

## Goal

Show the value of the app without turning the demo into a software lesson.

The person watching should leave understanding:

- shots are saved automatically;
- sessions and clubs stay organized;
- dispersion is easy to see;
- any shot can be clicked and replayed;
- strike and shot data stay attached to the shot;
- everything is saved locally for later.

Do **not** start by talking about SQLite, WebView2, process roles, log files, or PowerShell.

## Before the demo

Have this ready:

- Shot Tracker installed;
- VTrack and GSPro working normally;
- one existing session with several shots;
- ideally Driver plus one iron/wedge group;
- at least one shot with Impact Replay;
- strike data if available.

## 1. Open the app

Open **vTrack Shot Tracker**.

Say something simple like:

> “This keeps a history of the shots VTrack and GSPro already produce, so I can review them without exporting files after every session.”

Start VTrack/GSPro normally if they are not already running.

## 2. Point out the four areas

Keep this quick:

1. **Left — Sessions & shots:** your history.
2. **Middle — Range:** where the shots went.
3. **Right — Replay & strike:** impact video and face contact.
4. **Bottom — Shot data:** the numbers for the selected shot.

Do not demonstrate every resize/collapse option yet.

## 3. Hit one live shot

Make sure **Follow live** is on.

Hit a shot.

As it appears, point out that the app automatically:

- saves it;
- knows the current club;
- adds it to the current session;
- plots it;
- selects it;
- loads its replay/strike information when available;
- shows the numbers at the bottom.

Say:

> “There was no CSV export or manual save step.”

## 4. Show a group of shots

Open an existing club group with several shots.

Show the **Dispersion** range.

Explain in golf terms:

> “Each dot is a real shot. The outline just helps show how wide the group is.”

Show two clubs together if it looks clean.

Switch **Carry** and **Total** once.

Explain:

- Carry = first landing distance.
- Total = carry plus rollout.

## 5. Click one shot

Click a shot dot on the Range.

Show that the selected shot updates the replay and data tiles.

If Impact Replay is available, let it loop once or twice.

If strike data is available, point to the crosshair:

> “That is where this shot hit the face. The colored pattern shows the broader strike pattern for this club.”

## 6. Show the saved history

Click an older session or older shot.

Explain:

> “I can come back to this later. It is not just a live-screen display.”

Mention that selecting an older shot pauses **Follow live** so the app does not keep jumping away while you are reviewing it.

## 7. Show one report

Open a session report.

Point out:

- the landscape dispersion graphic;
- club summaries;
- shot-by-shot details.

Say:

> “I can print this or save it as a PDF for a lesson, fitting, or practice record.”

## 8. End with the value proposition

Finish with something like:

> “VTrack and GSPro still do the shot measurement. Shot Tracker is the archive and review layer: it saves the history automatically, lets me compare sessions and clubs, and keeps the replays and strike data with the shot.”

That is enough for most people.

# Beginner demo — 60 seconds

If you only have a minute:

1. Open an existing multi-club session.
2. Show the dispersion range.
3. Click one shot.
4. Show Impact Replay and strike location.
5. Point to the bottom shot-data tiles.
6. Open the session report.
7. Say:

> “New VTrack/GSPro shots are saved automatically, I can review every shot later, and the whole archive stays local on the simulator PC.”

# Advanced demo — 10 to 15 minutes

Use this only when the viewer wants deeper simulator features.

## 1. Start with the same simple overview

Do the first two minutes of the Beginner demo first.

Even technical users understand the architecture better after they understand the product.

## 2. Show session and shot control

Demonstrate:

- named sessions;
- expanding/collapsing clubs;
- hiding/showing a shot;
- hiding/showing a club;
- hiding/showing a session;
- **Clear range** and restoring a group.

Emphasize that these visibility actions are non-destructive.

## 3. Show manual correction

Open the action menu on a shot.

Show that you can:

- reassign the club;
- move the shot to another session.

Show the loft-specific wedge options such as 50°, 54°, 58°, and 60°.

Cancel unless you intend to change the data.

## 4. Show Bag Mapping

Open **Bag**.

Explain:

```text
GSPro club: SW
Your real club: 54° Wedge
```

Then explain that Bag Mapping changes how **new** shots are grouped while the original GSPro club value is still preserved.

## 5. Show deeper range controls

In **Dispersion**:

- show multiple clubs;
- select several shot dots;
- switch Carry/Total;
- zoom;
- pan;
- reset;
- optionally enable **All axis values**.

Then switch to **Flight** and show the trajectory views.

If putting data exists, switch to **Putting** and explain that it uses feet and shows roll/finish patterns on a green.

## 6. Show comparisons

Select a club/session pill under the Range.

Show the comparison panel and the Woman/Man/Senior/Junior profile choices.

Explain clearly:

> “This is a practice reference inside Shot Tracker, not an official handicap or universal player rating.”

## 7. Show Replay & strike workspace controls

Open **Windows** and show:

- Impact Replay;
- Swing Cam 1;
- Swing Cam 2;
- Shot Heatmap.

Move and resize a panel, then use **Snap grid**.

Explain that missing optional camera media shows an unavailable state instead of breaking the layout.

## 8. Show exports

Demonstrate a few of these:

- Range image;
- selected-shot CSV;
- session CSV;
- session report/PDF;
- comparison HTML;
- replay MP4;
- strike/heatmap image.

You do not need to demonstrate every export every time.

## 9. Show saved workspace behavior

Resize a main column, change the theme, or move a replay panel.

Explain that Shot Tracker remembers much of the workspace between launches.

## 10. Explain VTrack separation

Only now, if the person cares about automation, explain:

- Shot Tracker itself does not start/stop VTrackToolKit;
- the two applications remain separate;
- optional Home Assistant/PowerShell helper scripts can deliberately control both for a simulator automation workflow.

This distinction is important for people with an existing startup/shutdown system.

## 11. Explain local data ownership

Show or describe:

```text
Documents\VTrackArchive\
```

Explain that the shot database and archived media live there, outside the installed application folder.

Upgrading or uninstalling the app is designed to leave this archive alone.

# Demo tips by audience

## Casual golfer

Focus on:

- automatic saving;
- dispersion;
- replay;
- strike pattern;
- reports.

Avoid technical implementation details unless asked.

## Club fitter or coach

Focus on:

- named sessions;
- multi-club dispersion;
- Carry vs Total;
- comparisons;
- strike pattern;
- session reports/PDF.

## Simulator hobbyist

Add:

- Bag Mapping;
- workspace customization;
- exports;
- optional automation.

## Home Assistant / automation user

Add:

- Shot Tracker and VTrack lifecycle separation;
- combined helper scripts;
- command-line `start`, `stop`, and `status`.

## Developer or AI agent

Do not use this demo as the architecture specification.

Use:

- [Requirements & Tenets](REQUIREMENTS_AND_TENETS.md)
- [Architecture](ARCHITECTURE.md)
