# Quick Start

This is the shortest path from **“I downloaded it”** to **“I can see my shots.”**

You do not need to know Python, PowerShell, databases, or GitHub to use the normal Windows app.

## Before you start

You need:

- a Windows 10 or Windows 11 simulator PC;
- LAON VTrack already installed and working;
- GSPro already working with VTrack;
- permission to install a Windows program.

If you can already hit a shot in VTrack/GSPro, you are ready for Shot Tracker.

## Step 1 — Download the installer

Open the project's **Releases** page and download the newest file named like:

```text
VTrackShotTracker-Setup-<version>.exe
```

Do not download the source-code ZIP unless you are a developer.

## Step 2 — Install it

Double-click the installer.

If Windows shows **Windows protected your PC**, this is usually because early builds are not code-signed yet.

Only continue if you downloaded the installer from this project's GitHub Release.

Choose:

1. **More info**
2. **Run anyway**

Keep the normal install location:

```text
C:\Program Files\VTrack Shot Tracker\
```

Finish the installer.

## Step 3 — Open Shot Tracker

Open the Windows Start menu and choose:

**Start vTrack Shot Tracker**

The Shot Tracker window should appear.

Shot Tracker does **not** start VTrack for you. That is intentional.

## Step 4 — Start your simulator normally

Start:

1. VTrack
2. GSPro

Use the same process you normally use before hitting balls.

## Step 5 — Check the status

Look at the upper-right corner of Shot Tracker.

You want the collector status to show that it is running/live.

Think of this as:

> “Shot Tracker is ready to notice my next shot.”

If the app itself opens but the collector is stopped, you can still review old shots. See [Installation & Troubleshooting](INSTALLATION.md) if new shots are not being captured.

## Step 6 — Hit one test shot

Hit a normal shot.

After VTrack and GSPro finish processing it, the shot should appear in **Sessions & shots** on the left side.

If **Follow live** is on, Shot Tracker should automatically select the new shot.

You should then see some combination of:

- the shot plotted on the Range;
- shot numbers across the bottom;
- Impact Replay, if VTrack produced replay media;
- strike location, if face-impact data was available.

Not every shot contains every type of data. A missing value does not automatically mean something is broken.

## Step 7 — Learn the four parts of the screen

You only need to remember these four areas:

### 1. Sessions & shots — left

This is your shot history.

Think of it like folders:

```text
Practice session
  → Club
      → Individual shot
```

Click a shot to review it.

### 2. Range — middle

This shows where your shots finished or how they flew.

Start with **Dispersion** and **Carry**.

- **Carry** = distance through the air before first landing.
- **Total** = carry plus rollout.
- **Dispersion** = how spread out your group of shots is.

### 3. Replay & strike — right

This is where you can see the impact replay and strike pattern when that data is available.

### 4. Shot data — bottom

These are the numbers for the shot you currently have selected.

## Step 8 — Your first useful practice session

For your first real use, keep it simple:

1. Make sure **Follow live** is on.
2. Hit 5–10 shots with one club.
3. Watch the shot group build on the Range.
4. Click an individual shot to replay it.
5. Look at the strike pattern if available.
6. Switch from **Carry** to **Total** and see how the group changes.

You do not need to change any other settings yet.

## Optional — name your practice session

Select **+ New session** and enter a simple name such as:

```text
Driver practice
7 Iron gapping
Wedge practice
New ball test
```

New shots will be grouped under that named session.

## Optional — set up your wedges

If GSPro says **SW** but your actual club is a **54° wedge**, open **Bag** and map it:

```text
SW → 54° Wedge
```

You can do the same for PW, GW, LW, woods, hybrids, and other clubs.

You can skip Bag Mapping completely if GSPro's club names already work for you.

## What is safe to click?

These actions do **not** delete your shots:

- hiding a shot or club from the Range;
- **Clear range**;
- collapsing a panel;
- changing Carry/Total;
- changing Dispersion/Flight/Putting;
- zooming or panning;
- switching light/dark mode.

Shot Tracker is designed so normal viewing controls are non-destructive.

## Where are my shots saved?

Your archive is normally here:

```text
Documents\VTrackArchive\
```

That folder is your shot history and archived media.

Installing an update or uninstalling Shot Tracker is designed not to erase it.

## What should I read next?

If everything is working, go to the **[User Guide](USER_GUIDE.md)**.

It explains each part of the app in normal golf-simulator language.

If something is not working, go to **[Installation & Troubleshooting](INSTALLATION.md)**.

If you are comfortable with command-line tools, Home Assistant, portable installs, or development features, use the **[Advanced Guide](ADVANCED_GUIDE.md)**.
