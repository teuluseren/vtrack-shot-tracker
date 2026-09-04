import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import vtrack_desktop
from vtrack_desktop import (
    DesktopApi,
    WindowStateRecorder,
    is_local_app_url,
    load_window_state,
    run_desktop,
)


class Event:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self


class DesktopTests(unittest.TestCase):
    def test_window_title_is_version_free_product_name(self):
        self.assertEqual(vtrack_desktop.APP_TITLE, "vTrack Shot Tracker")

    def test_windows_app_identity_is_registered(self):
        with mock.patch.object(vtrack_desktop.os, "name", "nt"), mock.patch(
            "ctypes.windll", create=True
        ) as windll:
            vtrack_desktop.set_windows_app_user_model_id()
        windll.shell32.SetCurrentProcessExplicitAppUserModelID.assert_called_once_with(
            vtrack_desktop.APP_USER_MODEL_ID
        )

    def test_window_state_round_trip_and_bounds(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / vtrack_desktop.WINDOW_STATE_FILE).write_text(
                json.dumps(
                    {
                        "width": 200,
                        "height": 9000,
                        "x": 125,
                        "y": -80,
                        "maximized": False,
                    }
                ),
                encoding="utf-8",
            )
            state = load_window_state(root)
            self.assertEqual(state["width"], 1100)
            self.assertEqual(state["height"], 4320)
            self.assertEqual((state["x"], state["y"]), (125, -80))
            self.assertFalse(state["maximized"])

            recorder = WindowStateRecorder(root, state)
            recorder.resized(1500, 850)
            recorder.moved(40, 60)
            saved = json.loads(
                (root / vtrack_desktop.WINDOW_STATE_FILE).read_text(encoding="utf-8")
            )
            self.assertEqual((saved["width"], saved["height"]), (1500, 850))
            self.assertEqual((saved["x"], saved["y"]), (40, 60))

    def test_desktop_api_accepts_only_the_local_review_origin(self):
        self.assertTrue(is_local_app_url("http://127.0.0.1:8765/report/session/1"))
        self.assertTrue(is_local_app_url("http://localhost:8765/"))
        self.assertFalse(is_local_app_url("https://127.0.0.1:8765/"))
        self.assertFalse(is_local_app_url("http://127.0.0.1:9999/"))
        self.assertFalse(is_local_app_url("https://example.com/"))

        fake = SimpleNamespace(create_window=mock.Mock())
        with mock.patch.dict(sys.modules, {"webview": fake}):
            self.assertFalse(DesktopApi().open_window("https://example.com/"))
            self.assertTrue(
                DesktopApi().open_window(
                    "http://127.0.0.1:8765/report/session/3", "Session report"
                )
            )
        fake.create_window.assert_called_once()

    def test_run_desktop_uses_edgechromium_and_persistent_storage(self):
        events = SimpleNamespace(
            resized=Event(),
            moved=Event(),
            maximized=Event(),
            restored=Event(),
            closed=Event(),
        )
        window = SimpleNamespace(events=events, show=mock.Mock())
        fake = SimpleNamespace(
            settings={},
            create_window=mock.Mock(return_value=window),
            start=mock.Mock(side_effect=lambda func=None, **_kwargs: func() if func else None),
        )
        with tempfile.TemporaryDirectory() as tempdir, mock.patch.object(
            vtrack_desktop.os, "name", "nt"
        ), mock.patch.object(
            vtrack_desktop, "webview2_runtime_version", return_value="152.0.0.0"
        ), mock.patch.dict(
            sys.modules, {"webview": fake}
        ):
            self.assertEqual(run_desktop(Path(tempdir)), 0)

        self.assertTrue(fake.settings["ALLOW_DOWNLOADS"])
        fake.create_window.assert_called_once()
        fake.start.assert_called_once()
        window.show.assert_called_once_with()
        kwargs = fake.start.call_args.kwargs
        self.assertEqual(kwargs["gui"], "edgechromium")
        self.assertFalse(kwargs["private_mode"])
        self.assertTrue(kwargs["storage_path"].endswith("webview-profile"))

    def test_closing_main_window_destroys_report_windows_and_runs_shutdown(self):
        events = SimpleNamespace(
            resized=Event(),
            moved=Event(),
            maximized=Event(),
            restored=Event(),
            closed=Event(),
        )
        window = SimpleNamespace(events=events, show=mock.Mock())
        report = SimpleNamespace(destroy=mock.Mock())
        fake = SimpleNamespace(settings={}, windows=[window, report])
        fake.create_window = mock.Mock(return_value=window)

        def start(func=None, **_kwargs):
            if func:
                func()
            for handler in list(events.closed.handlers):
                handler()

        fake.start = mock.Mock(side_effect=start)
        shutdown = mock.Mock()
        with tempfile.TemporaryDirectory() as tempdir, mock.patch.object(
            vtrack_desktop.os, "name", "nt"
        ), mock.patch.object(
            vtrack_desktop, "webview2_runtime_version", return_value="152.0.0.0"
        ), mock.patch.dict(
            sys.modules, {"webview": fake}
        ):
            self.assertEqual(run_desktop(Path(tempdir), on_closed=shutdown), 0)

        report.destroy.assert_called_once_with()
        shutdown.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
