# Contributing to vTrack Shot Tracker

Thanks for considering a contribution.

Before changing application behavior, read [`docs/REQUIREMENTS_AND_TENETS.md`](docs/REQUIREMENTS_AND_TENETS.md). The project is deliberately optimized for golfers first, with advanced and developer complexity disclosed progressively.

## Licensing of contributions

vTrack Shot Tracker is source-available under the **PolyForm Shield License 1.0.0** and may also be offered under separate commercial licenses.

To keep that dual-licensing model workable, contributions are accepted only under the [`Contributor License Agreement`](CONTRIBUTOR_LICENSE_AGREEMENT.md).

You keep copyright in your contribution. The CLA grants the project the rights needed to distribute, sublicense, and relicense accepted contributions, including under commercial terms.

By submitting a pull request and confirming the CLA checkbox in the pull-request template, you agree to the CLA for the contribution in that pull request.

If you cannot agree to the CLA, please open a discussion or issue before doing substantial implementation work so expectations are clear.

## Before opening a pull request

- Keep LAON VTrack lifecycle separate from Shot Tracker core lifecycle.
- Do not include real simulator archives, personal logs, replay videos, credentials, private LAN details, or customer/user data.
- Use synthetic fixtures for tests and examples.
- Follow [`docs/ASSET_POLICY.md`](docs/ASSET_POLICY.md) for images, fonts, audio, video, logos, screenshots, and other non-code assets.
- Preserve the original GSPro/VTrack source data when changing normalization or mapping behavior.
- Add or update automated tests for behavior changes.
- Keep normal-user UI and documentation in golf/simulator language rather than implementation jargon.

## Checks

Run the standard checks before submitting:

```powershell
python -m py_compile vtrack_shot_tracker.py vtrack_desktop.py vtrack_version.py vtrack_updater.py club_config.py collector\vtrack_shot_collector.py review\shot_review.py tools\backfill_vtrack_clubs.py tools\check_ui_js.py tools\create_ui_smoke_archive.py
python -m unittest discover -s tests -v
$js = python tools/check_ui_js.py
node --check $js
Remove-Item $js
```

GitHub Actions also runs the Windows/browser smoke workflow on pull requests.

## Pull requests

A pull request should explain:

- the user-visible problem or goal;
- what changed;
- how it was tested;
- any migration, archive, packaging, or compatibility consequence;
- whether new third-party code or assets were introduced.

Small, focused changes are easier to review and safer to release than unrelated bundles of changes.

## Security issues

Do not publish exploitable security details or private simulator/user data in an issue. Follow [`SECURITY.md`](SECURITY.md).
