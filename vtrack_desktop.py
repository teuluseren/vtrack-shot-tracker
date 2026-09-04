"""Dedicated Windows desktop host for the local Shot Review web application."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse


APP_TITLE = "vTrack Shot Tracker"
DEFAULT_URL = "http://127.0.0.1:8765/"
WINDOW_STATE_FILE = "desktop-window.json"
WEBVIEW_STORAGE_DIR = "webview-profile"
WEBVIEW2_CLIENT_ID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_DOWNLOAD_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"
DEFAULT_WINDOW_STATE = {
    "width": 1600,
    "height": 950,
    "x": None,
    "y": None,
    "maximized": True,
}


def load_window_state(runtime_dir: Path) -> dict[str, object]:
    state = dict(DEFAULT_WINDOW_STATE)
    try:
        saved = json.loads((runtime_dir / WINDOW_STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return state
    if not isinstance(saved, dict):
        return state
    try:
        state["width"] = max(1100, min(7680, int(saved.get("width", state["width"]))))
        state["height"] = max(700, min(4320, int(saved.get("height", state["height"]))))
    except (TypeError, ValueError):
        pass
    for axis in ("x", "y"):
        value = saved.get(axis)
        if isinstance(value, int) and -10000 <= value <= 10000:
            state[axis] = value
    state["maximized"] = bool(saved.get("maximized", state["maximized"]))
    return state


def save_window_state(runtime_dir: Path, state: dict[str, object]) -> None:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    target = runtime_dir / WINDOW_STATE_FILE
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temporary.replace(target)


def is_local_app_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost"}
            and parsed.port == 8765
        )
    except (TypeError, ValueError):
        return False


def webview2_runtime_version() -> Optional[str]:
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None
    locations = (
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_ID}"),
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_ID}"),
        (winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_ID}"),
    )
    for hive, key_name in locations:
        try:
            with winreg.OpenKey(hive, key_name) as key:
                version = str(winreg.QueryValueEx(key, "pv")[0]).strip()
        except OSError:
            continue
        if version and version != "0.0.0.0":
            return version
    return None


class WindowStateRecorder:
    def __init__(self, runtime_dir: Path, initial: dict[str, object]) -> None:
        self.runtime_dir = runtime_dir
        self.state = dict(initial)
        self.lock = threading.Lock()

    def _save(self) -> None:
        with self.lock:
            save_window_state(self.runtime_dir, self.state)

    def resized(self, width: int, height: int) -> None:
        if not self.state["maximized"]:
            self.state.update(width=int(width), height=int(height))
            self._save()

    def moved(self, x: int, y: int) -> None:
        if not self.state["maximized"]:
            self.state.update(x=int(x), y=int(y))
            self._save()

    def maximized(self) -> None:
        self.state["maximized"] = True
        self._save()

    def restored(self) -> None:
        self.state["maximized"] = False
        self._save()

    def closed(self) -> None:
        self._save()


class DesktopApi:
    """Small, validated bridge for opening local reports in native child windows."""

    def open_window(self, url: str, title: str = "VTrack Report") -> bool:
        if not is_local_app_url(url):
            return False
        import webview

        webview.create_window(
            str(title or "VTrack Report")[:120],
            url,
            width=1300,
            height=900,
            min_size=(900, 600),
            background_color="#090d12",
            text_select=True,
        )
        return True


def run_desktop(
    runtime_dir: Path,
    url: str = DEFAULT_URL,
    *,
    debug: bool = False,
    on_closed: Optional[Callable[[], None]] = None,
) -> int:
    if os.name != "nt":
        raise RuntimeError("The VTrack desktop window requires Windows.")
    runtime_version = webview2_runtime_version()
    if not runtime_version:
        raise RuntimeError(
            "Microsoft Edge WebView2 Runtime is not installed. "
            f"Install it from {WEBVIEW2_DOWNLOAD_URL}"
        )

    import webview

    runtime_dir.mkdir(parents=True, exist_ok=True)
    state = load_window_state(runtime_dir)
    recorder = WindowStateRecorder(runtime_dir, state)
    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = bool(debug)

    options: dict[str, object] = {
        "width": state["width"],
        "height": state["height"],
        "min_size": (1100, 700),
        "maximized": state["maximized"],
        "background_color": "#090d12",
        "text_select": True,
        "zoomable": False,
        "js_api": DesktopApi(),
    }
    if state["x"] is not None and state["y"] is not None:
        options.update(x=state["x"], y=state["y"])
    window = webview.create_window(APP_TITLE, url, **options)
    window.events.resized += recorder.resized
    window.events.moved += recorder.moved
    window.events.maximized += recorder.maximized
    window.events.restored += recorder.restored

    main_closed = threading.Event()

    def close_application_windows() -> None:
        """Treat closing the main window as exiting the whole desktop app."""
        if main_closed.is_set():
            return
        main_closed.set()
        recorder.closed()
        try:
            remaining = tuple(webview.windows)
        except Exception:
            remaining = ()
        for other in remaining:
            if other is window:
                continue
            try:
                other.destroy()
            except Exception:
                pass

    window.events.closed += close_application_windows

    def reveal_main_window() -> None:
        """Reveal the native host after WebView2 finishes GUI initialization."""
        window.show()

    webview.start(
        reveal_main_window,
        gui="edgechromium",
        debug=debug,
        private_mode=False,
        storage_path=str(runtime_dir / WEBVIEW_STORAGE_DIR),
    )
    if main_closed.is_set() and on_closed:
        on_closed()
    return 0
