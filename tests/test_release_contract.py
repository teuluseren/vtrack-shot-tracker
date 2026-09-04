import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import vtrack_shot_tracker
from vtrack_version import __version__


SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


class ReleaseContractTests(unittest.TestCase):
    def test_version_is_semver(self):
        self.assertRegex(__version__, SEMVER)

    def test_no_argument_launch_defaults_to_start(self):
        with mock.patch.object(
            vtrack_shot_tracker, "command_start", return_value=0
        ) as start:
            self.assertEqual(vtrack_shot_tracker.main([]), 0)
        start.assert_called_once()
        self.assertEqual(start.call_args.args[0].command, "start")

    def test_public_commands_are_available(self):
        parser = vtrack_shot_tracker.create_parser()
        for command in (
            "start",
            "stop",
            "status",
            "cleanup-storage",
            "review",
            "dev",
            "dev-stop",
            "check-update",
            "update",
        ):
            parsed = parser.parse_args([command])
            self.assertTrue(callable(parsed.handler))

    def test_release_files_use_single_version_source(self):
        root = Path(__file__).resolve().parents[1]
        self.assertNotIn("2.8", (root / "README.md").read_text(encoding="utf-8"))
        self.assertIn("vtrack_version", (root / "review" / "shot_review.py").read_text(encoding="utf-8"))

    def test_windows_product_name_excludes_version(self):
        root = Path(__file__).resolve().parents[1]
        installer = (root / "packaging" / "VTrackShotTracker.iss").read_text(encoding="utf-8")
        self.assertIn('#define AppName "vTrack Shot Tracker"', installer)
        self.assertIn("AppVersion={#AppVersion}", installer)
        self.assertIn("AppVerName={#AppName}\n", installer)
        self.assertIn("UninstallDisplayName={#AppName}", installer)
        self.assertNotIn("AppVerName={#AppName} {#AppVersion}", installer)
        self.assertEqual(vtrack_shot_tracker.APP_NAME, "vTrack Shot Tracker")

    def test_installer_publishes_one_windows_app_entry(self):
        root = Path(__file__).resolve().parents[1]
        installer = (root / "packaging" / "VTrackShotTracker.iss").read_text(
            encoding="utf-8"
        )
        icons = installer.split("[Icons]", 1)[1].split("[Run]", 1)[0]
        self.assertEqual(icons.count("Name:"), 1)
        self.assertIn('Name: "{group}\\vTrack Shot Tracker"', icons)
        self.assertIn('AppUserModelID: "{#AppUserModelID}"', icons)
        self.assertNotIn("Parameters:", icons)
        self.assertIn("[InstallDelete]", installer)
        for obsolete in (
            "Start vTrack Shot Tracker.lnk",
            "Shot Review.lnk",
            "Check for Updates.lnk",
            "Stop vTrack Shot Tracker.lnk",
            "Uninstall vTrack Shot Tracker.lnk",
        ):
            self.assertIn(obsolete, installer)

    def test_version_bump_command_uses_human_release_sizes(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / "Bump-Version.ps1").read_text(encoding="utf-8")
        self.assertIn("[ValidateSet('minor', 'feature', 'major')]", script)
        self.assertIn("'minor'", script)
        self.assertIn("$patch++", script)
        self.assertIn("'feature'", script)
        self.assertIn("$minor++", script)
        self.assertIn("'major'", script)
        self.assertIn("$major++", script)
        self.assertIn("vtrack_version.py", script)

    def test_local_build_creates_checksum_manifest(self):
        root = Path(__file__).resolve().parents[1]
        build_script = (root / "packaging" / "build.ps1").read_text(encoding="utf-8")
        self.assertIn("Get-FileHash -Algorithm SHA256", build_script)
        self.assertIn("SHA256SUMS.txt", build_script)

    def test_packaged_app_includes_club_face_assets(self):
        root = Path(__file__).resolve().parents[1]
        spec = (root / "packaging" / "VTrackShotTracker.spec").read_text(encoding="utf-8")
        self.assertIn('project_root / "assets"', spec)
        for name in (
            "club-face-driver.png",
            "club-face-wood.png",
            "club-face-hybrid.png",
            "club-face-iron.png",
            "club-face-putter.png",
        ):
            self.assertTrue((root / "assets" / name).is_file())

    def test_packaged_app_includes_native_desktop_host(self):
        root = Path(__file__).resolve().parents[1]
        spec = (root / "packaging" / "VTrackShotTracker.spec").read_text(encoding="utf-8")
        requirements = (root / "requirements-build.txt").read_text(encoding="utf-8")
        self.assertIn('"vtrack_desktop"', spec)
        self.assertIn('"webview"', spec)
        self.assertIn("pywebview==6.2.1", requirements)
        start = vtrack_shot_tracker.create_parser().parse_args(["start"])
        self.assertFalse(start.no_window)
        self.assertFalse(start.browser)
        browser = vtrack_shot_tracker.create_parser().parse_args(["review", "--browser"])
        self.assertTrue(browser.browser)
        dev = vtrack_shot_tracker.create_parser().parse_args(["dev"])
        self.assertFalse(dev.browser)
        browser_dev = vtrack_shot_tracker.create_parser().parse_args(["dev", "--browser"])
        self.assertTrue(browser_dev.browser)

    def test_packaged_app_has_windowed_launcher_and_console_cli(self):
        root = Path(__file__).resolve().parents[1]
        spec = (root / "packaging" / "VTrackShotTracker.spec").read_text(
            encoding="utf-8"
        )
        self.assertIn('name="VTrackShotTracker"', spec)
        self.assertIn('name="VTrackShotTrackerCLI"', spec)
        self.assertIn("gui_exe", spec)
        self.assertIn("cli_exe", spec)
        self.assertIn("console=False", spec)
        self.assertIn("console=True", spec)
        for relative in (
            "packaging/Start-VTrackShotTracker.ps1",
            "packaging/Stop-VTrackShotTracker.ps1",
            "Start-VTrack.ps1",
            "Stop-VTrack.ps1",
        ):
            self.assertIn(
                "VTrackShotTrackerCLI.exe",
                (root / relative).read_text(encoding="utf-8"),
            )

    def test_frozen_cli_spawns_windowed_desktop_executable(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            cli = root / vtrack_shot_tracker.CLI_EXECUTABLE_NAME
            gui = root / vtrack_shot_tracker.GUI_EXECUTABLE_NAME
            gui.touch()
            with mock.patch.object(sys, "frozen", True, create=True), mock.patch.object(
                sys, "executable", str(cli)
            ):
                self.assertEqual(vtrack_shot_tracker._base_command(), [str(gui.resolve())])

    def test_windows_icon_and_uninstall_shutdown_are_packaged(self):
        root = Path(__file__).resolve().parents[1]
        spec = (root / "packaging" / "VTrackShotTracker.spec").read_text(encoding="utf-8")
        installer = (root / "packaging" / "VTrackShotTracker.iss").read_text(encoding="utf-8")
        icon = root / "assets" / "vtrack-app-icon.ico"
        self.assertTrue(icon.is_file())
        self.assertEqual(icon.read_bytes()[:4], b"\x00\x00\x01\x00")
        self.assertIn('icon=str(project_root / "assets" / "vtrack-app-icon.ico")', spec)
        self.assertIn("SetupIconFile=..\\assets\\vtrack-app-icon.ico", installer)
        self.assertIn("[UninstallRun]", installer)
        self.assertIn('Parameters: "stop"; Flags: runhidden waituntilterminated', installer)
        self.assertIn("procedure StopInstalledTracker;", installer)
        self.assertIn("function PrepareToInstall(var NeedsRestart: Boolean): String;", installer)
        self.assertIn("function InitializeUninstall(): Boolean;", installer)
        self.assertGreaterEqual(installer.count("StopInstalledTracker;"), 3)
        self.assertNotIn("uninsdelete", installer.lower())

    def test_tracker_cli_has_no_vtrack_lifecycle_options(self):
        parser = vtrack_shot_tracker.create_parser()
        for argv in (
            ["start", "--with-vtrack"],
            ["start", "--no-vtrack"],
            ["stop", "--stop-vtrack"],
            ["stop", "--keep-vtrack"],
        ):
            with self.assertRaises(SystemExit):
                parser.parse_args(argv)

    def test_installer_keeps_combined_and_tracker_only_wrappers_distinct(self):
        root = Path(__file__).resolve().parents[1]
        installer = (root / "packaging" / "VTrackShotTracker.iss").read_text(
            encoding="utf-8"
        )
        self.assertIn('Parameters: "start"', installer)
        self.assertIn('Parameters: "stop"', installer)
        for forbidden in (
            "--with-vtrack",
            "--no-vtrack",
            "--stop-vtrack",
            "--keep-vtrack",
        ):
            self.assertNotIn(forbidden, installer)

        start_wrapper = (root / "packaging" / "Start-VTrackShotTracker.ps1").read_text(
            encoding="utf-8"
        )
        stop_wrapper = (root / "packaging" / "Stop-VTrackShotTracker.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("start @args", start_wrapper)
        self.assertIn("stop @args", stop_wrapper)
        self.assertNotIn("vtrack", start_wrapper.lower().replace("vtrackshottracker", ""))
        self.assertNotIn("vtrack", stop_wrapper.lower().replace("vtrackshottracker", ""))
        for script_name in ("Start-VTrack.ps1", "Stop-VTrack.ps1"):
            desktop_script = (root / script_name).read_text(encoding="utf-8")
            for forbidden in ("--with-vtrack", "--no-vtrack", "--stop-vtrack", "--keep-vtrack"):
                self.assertNotIn(forbidden, desktop_script)
        self.assertIn('Source: "..\\Start-VTrack.ps1"', installer)
        self.assertIn('Source: "..\\Stop-VTrack.ps1"', installer)

        combined_start = (root / "Start-VTrack.ps1").read_text(encoding="utf-8")
        combined_stop = (root / "Stop-VTrack.ps1").read_text(encoding="utf-8")
        self.assertIn("Get-StartApps", combined_start)
        self.assertIn("start @args", combined_start)
        self.assertLess(combined_start.index("Get-StartApps"), combined_start.index("start @args"))
        self.assertIn("Get-Process", combined_stop)
        self.assertIn("stop @args", combined_stop)
        self.assertLess(combined_stop.index("stop @args"), combined_stop.index("Get-Process"))

    def test_start_opens_viewer_even_if_collector_spawn_fails(self):
        with tempfile.TemporaryDirectory() as tempdir:
            archive = Path(tempdir)
            args = vtrack_shot_tracker.create_parser().parse_args(
                ["start", "--archive", str(archive), "--no-window"]
            )
            def spawn(role, arguments=None):
                return role != "collector"
            with mock.patch.object(
                vtrack_shot_tracker, "_ensure_viewer", return_value=True
            ), mock.patch.object(
                vtrack_shot_tracker, "_spawn_role", side_effect=spawn
            ):
                self.assertEqual(vtrack_shot_tracker.command_start(args), 0)

    def test_cleanup_storage_is_dry_run_until_apply(self):
        with tempfile.TemporaryDirectory() as tempdir:
            archive = Path(tempdir)
            shot = archive / "shots" / "2026-09-04" / "shot"
            shot.mkdir(parents=True)
            frame = shot / "Cam1_01.bmp"
            frame.write_bytes(b"frame")
            (shot / "cam1_raw.mp4").write_bytes(b"video")

            dry = vtrack_shot_tracker.create_parser().parse_args(
                ["cleanup-storage", "--archive", str(archive)]
            )
            self.assertEqual(vtrack_shot_tracker.command_cleanup_storage(dry), 0)
            self.assertTrue(frame.exists())

            apply = vtrack_shot_tracker.create_parser().parse_args(
                ["cleanup-storage", "--archive", str(archive), "--apply"]
            )
            with mock.patch.object(vtrack_shot_tracker, "command_stop") as stop:
                self.assertEqual(vtrack_shot_tracker.command_cleanup_storage(apply), 0)
            stop.assert_called_once_with(apply)
            self.assertFalse(frame.exists())

    def test_stop_only_terminates_tracker_roles(self):
        args = vtrack_shot_tracker.create_parser().parse_args(["stop"])
        with mock.patch.object(vtrack_shot_tracker, "_terminate_role") as terminate:
            self.assertEqual(vtrack_shot_tracker.command_stop(args), 0)
        self.assertEqual(
            terminate.call_args_list,
            [mock.call("desktop"), mock.call("viewer"), mock.call("collector")],
        )

    def test_closing_desktop_stops_viewer_and_collector(self):
        args = vtrack_shot_tracker.create_parser().parse_args(["__desktop"])
        callback = None

        def run_desktop(runtime, *, debug=False, on_closed=None):
            nonlocal callback
            callback = on_closed
            return 0

        with mock.patch("vtrack_desktop.run_desktop", new=run_desktop), mock.patch.object(
            vtrack_shot_tracker, "_terminate_role"
        ) as terminate, mock.patch.object(vtrack_shot_tracker, "_remove_role"):
            self.assertEqual(vtrack_shot_tracker._internal_desktop(args), 0)
            self.assertTrue(callable(callback))
            callback()
        self.assertEqual(terminate.call_args_list, [mock.call("viewer"), mock.call("collector")])

    def test_closing_development_desktop_keeps_live_collector(self):
        args = vtrack_shot_tracker.create_parser().parse_args(["__desktop", "--debug"])
        callback = None

        def run_desktop(runtime, *, debug=False, on_closed=None):
            nonlocal callback
            callback = on_closed
            return 0

        with mock.patch("vtrack_desktop.run_desktop", new=run_desktop), mock.patch.object(
            vtrack_shot_tracker, "_terminate_role"
        ) as terminate, mock.patch.object(vtrack_shot_tracker, "_remove_role"):
            self.assertEqual(vtrack_shot_tracker._internal_desktop(args), 0)
            callback()
        terminate.assert_called_once_with("viewer")

    def test_running_archive_is_read_from_process_record(self):
        expected = Path("test-archive").resolve()
        actual = vtrack_shot_tracker._archive_from_process(
            {"arguments": ["--archive", str(expected)]}
        )
        self.assertEqual(actual, expected)

    def test_development_command_defaults_to_desktop_and_dev_stop_closes_it(self):
        with tempfile.TemporaryDirectory() as tempdir:
            archive = Path(tempdir)
            (archive / "vtrack_shots.sqlite3").touch()
            args = vtrack_shot_tracker.create_parser().parse_args(
                ["dev", "--archive", str(archive)]
            )
            with mock.patch.object(
                vtrack_shot_tracker, "_terminate_role"
            ) as terminate, mock.patch.object(
                vtrack_shot_tracker, "_spawn_role", return_value=True
            ), mock.patch.object(
                vtrack_shot_tracker, "_viewer_ready", return_value=True
            ), mock.patch.object(
                vtrack_shot_tracker, "_open_desktop", return_value=True
            ) as open_desktop, mock.patch.object(
                vtrack_shot_tracker.webbrowser, "open"
            ) as open_browser:
                self.assertEqual(vtrack_shot_tracker.command_dev(args), 0)
                open_desktop.assert_called_once_with(debug=True)
                open_browser.assert_not_called()

                terminate.reset_mock()
                self.assertEqual(vtrack_shot_tracker.command_dev_stop(args), 0)
                self.assertEqual(
                    terminate.call_args_list,
                    [mock.call("desktop"), mock.call("viewer")],
                )

    def test_corrupt_archive_is_preserved_and_reported_without_starting_viewer(self):
        with tempfile.TemporaryDirectory() as tempdir:
            archive = Path(tempdir)
            db_path = archive / "vtrack_shots.sqlite3"
            original = b"this is not sqlite and must be preserved"
            db_path.write_bytes(original)
            args = vtrack_shot_tracker.create_parser().parse_args(
                ["start", "--archive", str(archive), "--no-window"]
            )
            with mock.patch.object(vtrack_shot_tracker, "_report_archive_error") as report, mock.patch.object(
                vtrack_shot_tracker, "_spawn_role"
            ) as spawn:
                self.assertEqual(vtrack_shot_tracker.command_start(args), 2)
            self.assertEqual(db_path.read_bytes(), original)
            report.assert_called_once()
            spawn.assert_not_called()

    def test_archive_initialization_error_is_actionable(self):
        with tempfile.TemporaryDirectory() as tempdir:
            archive = Path(tempdir)
            with mock.patch.object(
                vtrack_shot_tracker, "Database", side_effect=sqlite3.OperationalError("disk is full")
            ):
                with self.assertRaises(vtrack_shot_tracker.ArchiveInitializationError) as raised:
                    vtrack_shot_tracker._initialize_archive(archive)
            message = str(raised.exception)
            self.assertIn(str(archive.resolve()), message)
            self.assertIn("not deleted or replaced", message)
            self.assertIn("disk space", message)


if __name__ == "__main__":
    unittest.main()
