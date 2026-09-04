import io
import unittest
from pathlib import Path
from unittest import mock

import vtrack_shot_tracker


class _Response:
    def __init__(self, content: bytes, status: int = 200):
        self.content = content
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, limit=-1):
        return self.content if limit < 0 else self.content[:limit]


class LauncherChaosTests(unittest.TestCase):
    def test_update_yes_is_a_valid_cli_path(self):
        args = vtrack_shot_tracker.create_parser().parse_args(["update", "--yes"])
        self.assertTrue(args.yes)
        self.assertIs(args.handler, vtrack_shot_tracker.command_update)

    def test_update_downloads_then_stops_then_launches_verified_installer(self):
        args = vtrack_shot_tracker.create_parser().parse_args(["update", "--yes"])
        release = {
            "update_available": True,
            "latest_version": "9.9.9",
            "release_url": "https://example.invalid/release",
        }
        runtime = Path("runtime-root").resolve()
        installer = runtime / "updates" / "9.9.9" / "VTrackShotTracker-Setup-9.9.9.exe"
        events = []

        def download(value, destination):
            self.assertIs(value, release)
            self.assertEqual(destination, runtime)
            events.append("download")
            return installer

        def stop(value):
            self.assertIs(value, args)
            events.append("stop")
            return 0

        def launch(value):
            self.assertEqual(value, installer)
            events.append("launch")

        with mock.patch("vtrack_updater.check_for_update", return_value=release), mock.patch(
            "vtrack_updater.download_update", side_effect=download
        ), mock.patch("vtrack_updater.launch_installer", side_effect=launch), mock.patch.object(
            vtrack_shot_tracker, "_runtime_root", return_value=runtime
        ), mock.patch.object(vtrack_shot_tracker, "command_stop", side_effect=stop):
            self.assertEqual(vtrack_shot_tracker.command_update(args), 0)

        self.assertEqual(events, ["download", "stop", "launch"])

    def test_update_without_yes_can_be_cancelled_before_download(self):
        args = vtrack_shot_tracker.create_parser().parse_args(["update"])
        release = {"update_available": True, "latest_version": "9.9.9"}
        with mock.patch("vtrack_updater.check_for_update", return_value=release), mock.patch(
            "builtins.input", return_value="no"
        ), mock.patch("vtrack_updater.download_update") as download:
            self.assertEqual(vtrack_shot_tracker.command_update(args), 1)
        download.assert_not_called()

    def test_update_when_current_does_not_stop_anything(self):
        args = vtrack_shot_tracker.create_parser().parse_args(["update", "--yes"])
        with mock.patch(
            "vtrack_updater.check_for_update", return_value={"update_available": False}
        ), mock.patch.object(vtrack_shot_tracker, "command_stop") as stop, mock.patch(
            "vtrack_updater.download_update"
        ) as download:
            self.assertEqual(vtrack_shot_tracker.command_update(args), 0)
        stop.assert_not_called()
        download.assert_not_called()

    def test_check_update_prints_normalized_release_url(self):
        args = vtrack_shot_tracker.create_parser().parse_args(["check-update"])
        release_url = "https://github.com/example/project/releases/tag/v9.9.9"
        result = {
            "update_available": True,
            "latest_version": "9.9.9",
            "release_url": release_url,
        }
        output = io.StringIO()
        with mock.patch("vtrack_updater.check_for_update", return_value=result), mock.patch(
            "sys.stdout", output
        ):
            self.assertEqual(vtrack_shot_tracker.command_check_update(args), 0)
        self.assertIn(release_url, output.getvalue())

    def test_viewer_ready_requires_vtrack_signature(self):
        good = _Response(b"<html><head><title>vTrack Shot Tracker</title></head></html>")
        with mock.patch.object(vtrack_shot_tracker.urllib.request, "urlopen", return_value=good):
            self.assertTrue(vtrack_shot_tracker._viewer_ready(8765, timeout=0.1))

        wrong = _Response(b"<html><head><title>Another local service</title></head></html>")
        with mock.patch.object(
            vtrack_shot_tracker.urllib.request, "urlopen", return_value=wrong
        ) as open_url, mock.patch.object(
            vtrack_shot_tracker.time, "monotonic", side_effect=[0.0, 0.0, 1.0]
        ), mock.patch.object(vtrack_shot_tracker.time, "sleep"):
            self.assertFalse(vtrack_shot_tracker._viewer_ready(8765, timeout=0.5))
        open_url.assert_called_once()

    def test_role_identity_rejects_recycled_pid(self):
        record = {
            "pid": 4321,
            "process_identity": {
                "executable": str(Path("VTrackShotTracker.exe").resolve()),
                "creation_time": 111,
            },
        }
        live = {
            "executable": str(Path("VTrackShotTracker.exe").resolve()),
            "creation_time": 222,
        }
        with mock.patch.object(vtrack_shot_tracker, "_process_identity", return_value=live):
            self.assertFalse(vtrack_shot_tracker._role_matches_process(record))

    def test_role_identity_accepts_same_process(self):
        identity = {
            "executable": str(Path("VTrackShotTracker.exe").resolve()),
            "creation_time": 111,
        }
        record = {"pid": 4321, "process_identity": dict(identity)}
        with mock.patch.object(vtrack_shot_tracker, "_process_identity", return_value=identity):
            self.assertTrue(vtrack_shot_tracker._role_matches_process(record))

    def test_stale_role_file_never_signals_recycled_pid(self):
        record = {"pid": 4321, "process_identity": {"creation_time": 111}}
        with mock.patch.object(vtrack_shot_tracker, "_load_role", return_value=record), mock.patch.object(
            vtrack_shot_tracker, "_role_matches_process", return_value=False
        ), mock.patch.object(vtrack_shot_tracker, "_remove_role") as remove, mock.patch.object(
            vtrack_shot_tracker.subprocess, "run"
        ) as run, mock.patch.object(vtrack_shot_tracker.os, "kill") as kill:
            vtrack_shot_tracker._terminate_role("viewer")
        run.assert_not_called()
        kill.assert_not_called()
        remove.assert_called_once_with("viewer", expected_pid=4321)

    def test_old_process_cannot_remove_new_role_record(self):
        current = {"pid": 2222}
        with mock.patch.object(vtrack_shot_tracker, "_load_role", return_value=current), mock.patch.object(
            vtrack_shot_tracker, "_role_path"
        ) as role_path:
            vtrack_shot_tracker._remove_role("viewer", expected_pid=1111)
        role_path.assert_not_called()


if __name__ == "__main__":
    unittest.main()
