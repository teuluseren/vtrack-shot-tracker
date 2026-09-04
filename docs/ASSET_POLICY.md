# Asset Policy

This repository is intended to be safe to publish and redistribute. Visual assets therefore need the same provenance discipline as source code.

## Current asset set

The `assets/` directory contains the UI artwork required by vTrack Shot Tracker:

- generic, unbranded club-face illustrations for driver, fairway wood, hybrid, iron, and putter strike views;
- generic golfer/persona illustrations used by the reference-benchmark UI;
- the vTrack Shot Tracker application icon.

These files are intentionally product-neutral: they should not contain manufacturer logos, third-party product photography, player likenesses, or other branding that implies endorsement.

During the public-readiness audit, an unused root-level `proteevx.png` file was removed because the application did not reference it and its redistribution provenance was not necessary to the project.

## Rule for new assets

Do not add a third-party image, logo, screenshot, product photo, font, audio file, or video simply because it is available on the web.

Before committing a new non-code asset, ensure at least one of the following is true:

1. it was created specifically for this project and the project has permission to redistribute it;
2. its license explicitly allows the intended redistribution and that license/attribution is recorded in `THIRD_PARTY_NOTICES.md`;
3. it is replaced with an original, generic project asset instead.

When provenance is uncertain, leave the asset out of the repository until it can be established.

## Trademarks

LAON, VTrack, GSPro, ProTee, TrackMan, and other third-party product/company names that may appear in documentation or compatibility descriptions are trademarks or product names of their respective owners. Use such names only to describe interoperability or compatibility. Do not use third-party logos or trade dress as project branding.

vTrack Shot Tracker is an independent community project and does not claim affiliation with or endorsement by LAON PEOPLE, GSPro, or other simulator/launch-monitor vendors.
