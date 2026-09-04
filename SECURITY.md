# Security Policy

vTrack Shot Tracker is a local Windows companion application that reads simulator data, stores a local shot archive, serves a loopback-only review interface, and can download verified application updates.

## Reporting a vulnerability

Please do **not** publish an exploitable security issue, credential, private archive, or personal simulator data in a public GitHub issue.

For security-sensitive reports, use GitHub's private vulnerability reporting feature when it is enabled for this repository. If private reporting is not available, open a minimal public issue asking for a private contact channel without including exploit details or sensitive data.

When reporting, include:

- the affected vTrack Shot Tracker version;
- Windows version;
- whether the native window or browser mode was used;
- the affected component (launcher, collector, review server, updater, installer, or packaging);
- reproduction steps that do not contain personal archive data or credentials;
- the security impact you observed.

## Security boundaries

The project is designed around these boundaries:

- the review HTTP service binds to loopback only;
- state-changing local HTTP actions enforce localhost/same-origin intent;
- Shot Tracker does not start or stop LAON VTrack as part of its core lifecycle;
- user shot archives are local personal data and are never deleted or replaced automatically as a recovery shortcut;
- update installers are verified against published SHA-256 checksums before launch;
- credentials, API tokens, private signing keys, and user archives must never be committed to the repository.

## Supported versions

This project is in active pre-1.0 development. Security fixes are applied to the current development release line. Older pre-1.0 builds may not receive backports.

## Public-repository hygiene

Contributors should not commit:

- `.env` files or credentials;
- private keys, signing certificates containing private keys, or API tokens;
- SQLite shot archives, logs, screenshots, videos, or exports containing user data;
- local Windows user-profile paths containing personal usernames;
- private LAN addresses or Home Assistant credentials from a real simulator installation.

Use synthetic fixtures in tests and documentation whenever possible.
