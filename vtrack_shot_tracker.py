"""VTrack Shot Tracker application launcher.

The Shot Tracker observes VTrack output but deliberately does not start, stop,
or otherwise manage the VTrack application itself.
"""
from __future__ import annotations

import argparse
import csv
import inspect
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timezone
from typing import Optional

from collector.vtrack_shot_collector import Database
from vtrack_version import __version__

APP_NAME = "vTrack Shot Tracker"
DEFAULT_PORT = 8765
DEFAULT_ARCHIVE = Path.home() / "Documents" / "VTrackArchive"
VIEWER_SIGNATURE = b"<title>vTrack Shot Tracker</title>"
ROLE_FILES = {
    "collector": "collector.json",
    "viewer": "viewer.json",
    "desktop": "desktop.json",
}
GUI_EXECUTABLE_NAME = "VTrackShotTracker.exe"
CLI_EXECUTABLE_NAME = "VTrackShotTrackerCLI.exe"

class ArchiveInitializationError(RuntimeError):
    """Raised when the user's archive cannot be opened safely."""


def _report_archive_error(exc: Exception) -> None:
    message = str(exc)
    print(f"ERROR: {message}", file=sys.stderr)
    if os.name == "nt" and getattr(sys, "frozen", False):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, f"{APP_NAME} - Archive problem", 0x10)
        except Exception:
            pass


def _runtime_root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".local" / "share"))
    root = base / "VTrackShotTracker"
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "processes").mkdir(parents=True, exist_ok=True)
    return root


def _role_path(role: str) -> Path:
    return _runtime_root() / "processes" / ROLE_FILES[role]


def _log_path(role: str) -> Path:
    return _runtime_root() / "logs" / f"{role}.log"


def _configure_frozen_streams(argv: list[str]) -> None:
    """Give the windowed build safe log streams without allocating a console."""
    if not getattr(sys, "frozen", False):
        return
    if sys.stdout is not None and sys.stderr is not None:
        return

    role = {
        "__collector": "collector",
        "__viewer": "viewer",
        "__desktop": "desktop",
    }.get(argv[0] if argv else "", "launcher")
    try:
        stream = _log_path(role).open("a", encoding="utf-8", buffering=1)
    except OSError:
        stream = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def _same_executable(left: object, right: object) -> bool:
    if not left or not right:
        return False
    try:
        return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(
            os.path.abspath(str(right))
        )
    except (OSError, TypeError, ValueError):
        return False


def _windows_process_identity(pid: int) -> Optional[dict]:
    """Return stable identity details for a live Windows process.

    PID files alone are unsafe because Windows can recycle process IDs.  The
    creation timestamp lets us distinguish a current tracker child from an
    unrelated process that later inherited the same PID.
    """
    if os.name != "nt" or not pid or pid <= 0:
        return None

    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return None
        if exit_code.value != STILL_ACTIVE:
            return None

        image = ctypes.create_unicode_buffer(32768)
        image_size = wintypes.DWORD(len(image))
        executable = None
        if kernel32.QueryFullProcessImageNameW(
            handle, 0, image, ctypes.byref(image_size)
        ):
            executable = image.value

        created = wintypes.FILETIME()
        exited = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        creation_time = None
        if kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            creation_time = (created.dwHighDateTime << 32) | created.dwLowDateTime

        return {
            "executable": executable,
            "creation_time": creation_time,
        }
    finally:
        kernel32.CloseHandle(handle)


def _process_alive(pid: int) -> bool:
    if not pid or pid <= 0:
        return False

    if os.name == "nt":
        return _windows_process_identity(pid) is not None

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _process_identity(pid: int) -> Optional[dict]:
    if not _process_alive(pid):
        return None
    if os.name == "nt":
        return _windows_process_identity(pid)

    identity: dict[str, object] = {}
    proc = Path("/proc") / str(pid)
    try:
        identity["executable"] = os.readlink(proc / "exe")
    except OSError:
        pass
    try:
        raw = (proc / "stat").read_text(encoding="utf-8")
        tail = raw[raw.rfind(")") + 2 :].split()
        if len(tail) > 19:
            identity["start_ticks"] = int(tail[19])
    except (OSError, ValueError):
        pass
    return identity


def _write_role(role: str, pid: int, arguments: list[str]) -> None:
    payload = {
        "pid": int(pid),
        "arguments": list(arguments),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "process_identity": _process_identity(pid),
    }
    path = _role_path(role)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{pid}.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def _load_role(role: str) -> Optional[dict]:
    try:
        obj = json.loads(_role_path(role).read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def _remove_role(role: str, *, expected_pid: Optional[int] = None) -> None:
    if expected_pid is not None:
        current = _load_role(role)
        try:
            current_pid = int((current or {}).get("pid") or 0)
        except (TypeError, ValueError):
            return
        if current_pid != int(expected_pid):
            return
    try:
        _role_path(role).unlink()
    except OSError:
        # Another tracker process may remove the same record while a desktop
        # close, stop command, or uninstaller is shutting down the process tree.
        pass


def _role_matches_process(record: Optional[dict]) -> bool:
    if not record:
        return False
    try:
        pid = int(record.get("pid") or 0)
    except (TypeError, ValueError):
        return False
    identity = _process_identity(pid)
    if identity is None:
        return False

    saved = record.get("process_identity")
    if isinstance(saved, dict) and saved:
        saved_exe = saved.get("executable")
        live_exe = identity.get("executable")
        if saved_exe and live_exe and not _same_executable(saved_exe, live_exe):
            return False
        for key in ("creation_time", "start_ticks"):
            if saved.get(key) is not None and identity.get(key) is not None:
                if saved.get(key) != identity.get(key):
                    return False
        return True

    # Backward compatibility for role records written by older frozen builds:
    # trust the PID only if it still belongs to this exact installed executable.
    if os.name == "nt" and getattr(sys, "frozen", False):
        return _same_executable(identity.get("executable"), sys.executable)

    # On POSIX this path is used only for source/development mode.  Existing
    # role records from the current process lifetime remain usable, while a
    # Windows source checkout deliberately refuses an unverifiable old PID.
    return os.name != "nt" and _process_alive(pid)


def _windows_tracker_pids() -> list[int]:
    """Return other installed VTrackShotTracker.exe process IDs.

    This is a fallback for stale/missing role files. It is intentionally only
    enabled for the frozen Windows build so a source checkout never sweeps
    unrelated python.exe processes. Matching the full executable path prevents
    a different program with the same image name from being terminated.
    """
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return []

    image_name = Path(sys.executable).name
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        return []

    pids: list[int] = []
    for row in csv.reader(result.stdout.splitlines()):
        if len(row) < 2 or row[0].upper() != image_name.upper():
            continue
        try:
            pid = int(row[1])
        except ValueError:
            continue
        identity = _process_identity(pid)
        if identity and _same_executable(identity.get("executable"), sys.executable):
            pids.append(pid)
    return pids


def _terminate_orphaned_tracker_processes() -> None:
    """Stop frozen tracker children that no longer have usable role files."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return

    current_pid = os.getpid()
    for pid in _windows_tracker_pids():
        if pid == current_pid:
            continue
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            pass


def _base_command() -> list[str]:
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        if executable.name.casefold() == CLI_EXECUTABLE_NAME.casefold():
            gui_executable = executable.with_name(GUI_EXECUTABLE_NAME)
            if gui_executable.is_file():
                executable = gui_executable
        return [str(executable)]
    return [sys.executable, str(Path(__file__).resolve())]


def _spawn_role(role: str, arguments: Optional[list[str]] = None) -> bool:
    arguments = list(arguments or [])
    existing = _load_role(role)
    if _role_matches_process(existing):
        return True
    if existing:
        try:
            _remove_role(role, expected_pid=int(existing.get("pid") or 0))
        except (TypeError, ValueError):
            _remove_role(role)

    internal = {
        "collector": "__collector",
        "viewer": "__viewer",
        "desktop": "__desktop",
    }[role]
    cmd = _base_command() + [internal] + arguments
    log_path = _log_path(role)
    creationflags = 0
    if os.name == "nt":
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] START {' '.join(cmd)}\n")
            log.flush()
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=str(Path(sys.executable).resolve().parent)
                if getattr(sys, "frozen", False)
                else str(Path(__file__).resolve().parent),
                creationflags=creationflags,
                close_fds=True,
            )
        _write_role(role, proc.pid, arguments)
        return True
    except Exception as exc:
        try:
            with log_path.open("a", encoding="utf-8") as log:
                log.write(f"START FAILED: {exc!r}\n")
        except OSError:
            pass
        return False


def _wait_for_exit(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _process_alive(pid):
            return True
        time.sleep(0.05)
    return not _process_alive(pid)


def _terminate_role(role: str) -> None:
    record = _load_role(role)
    if not record:
        return
    try:
        pid = int(record.get("pid") or 0)
    except (TypeError, ValueError):
        _remove_role(role)
        return

    # Never signal a PID just because it appears in a role file. A stale role
    # file can outlive its process, and Windows may recycle the PID.
    if pid > 0 and _role_matches_process(record):
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            else:
                os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        if not _wait_for_exit(pid) and os.name != "nt":
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
            _wait_for_exit(pid, timeout=1.0)
    _remove_role(role, expected_pid=pid)


def _archive_from_process(record: Optional[dict]) -> Optional[Path]:
    if not record:
        return None
    args = record.get("arguments") or []
    for i, value in enumerate(args[:-1]):
        if value == "--archive":
            return Path(args[i + 1]).expanduser().resolve()
    return None


def _initialize_archive(archive: Path) -> Path:
    archive = archive.expanduser().resolve()
    db_path = archive / "vtrack_shots.sqlite3"
    try:
        archive.mkdir(parents=True, exist_ok=True)
        db = Database(db_path)
        db.close()
        return db_path
    except (OSError, sqlite3.Error) as exc:
        raise ArchiveInitializationError(
            f"Shot Tracker could not open the archive at:\n{archive}\n\n"
            "Your existing archive was not deleted or replaced. Check available "
            "disk space and folder permissions. If the database is damaged, keep "
            "the file and restore it from a backup rather than deleting it.\n\n"
            f"Technical detail: {exc}"
        ) from exc


def _viewer_url(port: int = DEFAULT_PORT) -> str:
    return f"http://127.0.0.1:{port}/"


def _viewer_ready(port: int = DEFAULT_PORT, timeout: float = 8.0) -> bool:
    """Return True only when the requested port is serving this application."""
    deadline = time.monotonic() + timeout
    url = _viewer_url(port)
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.75) as response:
                if response.status == 200:
                    sample = response.read(65536)
                    if VIEWER_SIGNATURE in sample:
                        return True
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.15)
    return False


def _open_desktop(debug: bool = False) -> bool:
    args = ["--debug"] if debug else []
    if not _spawn_role("desktop", args):
        return False
    # pywebview.start() blocks for the lifetime of the native window. If the
    # process dies immediately (missing WebView2/runtime failure), use browser.
    time.sleep(1.0)
    record = _load_role("desktop")
    if not _role_matches_process(record):
        if record:
            try:
                _remove_role("desktop", expected_pid=int(record.get("pid") or 0))
            except (TypeError, ValueError):
                _remove_role("desktop")
        return False
    return True


def _open_viewer(browser: bool, no_window: bool, debug: bool, port: int) -> None:
    if no_window:
        return
    url = _viewer_url(port)
    if browser:
        webbrowser.open(url)
        return
    if not _open_desktop(debug=debug):
        webbrowser.open(url)


def _ensure_viewer(archive: Path, port: int, dev: bool = False) -> bool:
    db_path = _initialize_archive(archive)
    if _viewer_ready(port, timeout=0.25):
        return True
    args = ["--db", str(db_path), "--port", str(port), "--no-browser"]
    if dev:
        args.append("--dev")
    if not _spawn_role("viewer", args):
        return False
    return _viewer_ready(port)


def command_start(args: argparse.Namespace) -> int:
    archive = args.archive.expanduser().resolve()
    try:
        ready = _ensure_viewer(archive, args.port)
    except ArchiveInitializationError as exc:
        _report_archive_error(exc)
        return 2
    if not ready:
        print(f"ERROR: Shot Review did not start. See {_log_path('viewer')}", file=sys.stderr)
        return 2

    # Open the UI before attempting the collector. The archive/review UI must
    # remain useful even when VTrack is closed or the collector cannot start.
    _open_viewer(args.browser, args.no_window, False, args.port)

    if not _spawn_role("collector", ["--archive", str(archive)]):
        print(f"WARNING: Collector did not start. See {_log_path('collector')}", file=sys.stderr)
    return 0


def command_stop(args: argparse.Namespace) -> int:
    # This intentionally stops only processes owned by VTrack Shot Tracker.
    # It never starts/stops VTrackToolKit, LPGAgent, VGPconnect, or GSPconnect.
    for role in ("desktop", "viewer", "collector"):
        _terminate_role(role)

    # A crash or an older build can leave a child alive after its role file is
    # removed. In the installed Windows build, sweep only other instances of
    # this exact executable. The current `stop` process is deliberately kept.
    _terminate_orphaned_tracker_processes()

    # Remove stale role records after the sweep so status immediately reflects
    # the stopped state even if an earlier record was corrupt.
    for role in ("desktop", "viewer", "collector"):
        _remove_role(role)
    return 0


def command_status(args: argparse.Namespace) -> int:
    collector = _load_role("collector")
    archive = _archive_from_process(collector) or args.archive.expanduser().resolve()
    print(f"{APP_NAME} {__version__}")
    print(f"Archive: {archive}")
    for role in ("viewer", "desktop", "collector"):
        record = _load_role(role)
        try:
            pid = int((record or {}).get("pid") or 0)
        except (TypeError, ValueError):
            pid = 0
        state = "running" if _role_matches_process(record) else "stopped"
        print(
            f"{role.capitalize():9} {state:7} pid={pid if pid else '-'}  "
            f"log={_log_path(role)}"
        )
    return 0


def _first_existing_file(folder: Path, names: tuple[str, ...]) -> Optional[Path]:
    for name in names:
        candidate = folder / name
        try:
            if candidate.is_file() and candidate.stat().st_size > 0:
                return candidate
        except OSError:
            continue
    return None


def command_cleanup_storage(args: argparse.Namespace) -> int:
    from collector.vtrack_shot_collector import cleanup_converted_frames

    archive = args.archive.expanduser().resolve()
    shots_root = archive / "shots"
    if not shots_root.exists():
        print(f"No archived shot folders were found under {shots_root}")
        return 0

    if args.apply:
        command_stop(args)

    try:
        folders = sorted({frame.parent for frame in shots_root.rglob("*.bmp")})
    except OSError as exc:
        print(f"Could not scan archived shot folders: {exc}", file=sys.stderr)
        return 2

    total_frames = 0
    total_bytes = 0
    for folder in folders:
        videos = {
            "replay": _first_existing_file(folder, ("impact_replay.mp4",)),
            "cam1": _first_existing_file(
                folder, ("cam1_raw.mp4", "swing_cam1.mp4", "swing1.mp4")
            ),
            "cam2": _first_existing_file(
                folder, ("cam2_raw.mp4", "swing_cam2.mp4", "swing2.mp4")
            ),
        }
        removed, reclaimed = cleanup_converted_frames(
            videos, dry_run=not args.apply
        )
        total_frames += removed
        total_bytes += reclaimed

    action = "Removed" if args.apply else "Would remove"
    print(
        f"{action} {total_frames} converted BMP frames "
        f"({total_bytes / (1024 * 1024):.1f} MiB)."
    )
    if not args.apply and total_frames:
        print("Run cleanup-storage --apply to perform this cleanup.")
    return 0


def command_review(args: argparse.Namespace) -> int:
    archive = args.archive.expanduser().resolve()
    try:
        ready = _ensure_viewer(archive, args.port)
    except ArchiveInitializationError as exc:
        _report_archive_error(exc)
        return 2
    if not ready:
        print(f"ERROR: Shot Review did not start. See {_log_path('viewer')}", file=sys.stderr)
        return 2
    _open_viewer(args.browser, args.no_window, False, args.port)
    return 0


def command_dev(args: argparse.Namespace) -> int:
    archive = args.archive.expanduser().resolve()
    _terminate_role("desktop")
    _terminate_role("viewer")
    try:
        ready = _ensure_viewer(archive, args.port, dev=True)
    except ArchiveInitializationError as exc:
        _report_archive_error(exc)
        return 2
    if not ready:
        print(f"ERROR: Development viewer did not start. See {_log_path('viewer')}", file=sys.stderr)
        return 2
    _open_viewer(args.browser, args.no_window, True, args.port)
    return 0


def command_dev_stop(args: argparse.Namespace) -> int:
    _terminate_role("desktop")
    _terminate_role("viewer")
    return 0


def command_check_update(args: argparse.Namespace) -> int:
    try:
        from vtrack_updater import check_for_update

        result = check_for_update(__version__)
    except Exception as exc:
        print(f"Update check failed: {exc}", file=sys.stderr)
        return 2
    if result.get("update_available"):
        print(f"Update available: {result.get('latest_version')}")
        print(result.get("release_url") or "")
    else:
        print(f"{APP_NAME} {__version__} is up to date.")
    return 0


def _confirm_update(version: object) -> bool:
    try:
        answer = input(f"Install vTrack Shot Tracker {version}? [y/N] ")
    except (EOFError, KeyboardInterrupt):
        return False
    return answer.strip().lower() in {"y", "yes"}


def command_update(args: argparse.Namespace) -> int:
    try:
        from vtrack_updater import check_for_update, download_update, launch_installer

        result = check_for_update(__version__)
        if not result.get("update_available"):
            print(f"{APP_NAME} {__version__} is up to date.")
            return 0
        if not getattr(args, "yes", False) and not _confirm_update(
            result.get("latest_version")
        ):
            print("Update cancelled.")
            return 1

        # download_update creates its own updates/<version> subdirectory.
        installer = download_update(result, _runtime_root())
        print(f"Downloaded and verified {installer}")

        # Shut down only application-owned roles. The updater process itself is
        # not a tracked role and the orphan sweep deliberately excludes its PID.
        command_stop(args)
        launch_installer(installer)
        return 0
    except Exception as exc:
        print(f"Update failed: {exc}", file=sys.stderr)
        return 2


def _internal_viewer(args: argparse.Namespace) -> int:
    from review.shot_review import main as viewer_main

    forwarded = ["--db", str(args.db), "--port", str(args.port), "--no-browser"]
    if args.dev:
        forwarded.append("--dev")
    try:
        return int(viewer_main(forwarded) or 0)
    finally:
        _remove_role("viewer", expected_pid=os.getpid())


def _internal_collector(args: argparse.Namespace) -> int:
    from collector.vtrack_shot_collector import main as collector_main

    try:
        return int(collector_main(["--archive", str(args.archive)]) or 0)
    finally:
        _remove_role("collector", expected_pid=os.getpid())


def _internal_desktop(args: argparse.Namespace) -> int:
    def stop_owned_services() -> None:
        # Closing the one visible application window means Exit. Keep VTrack
        # itself untouched, but do not leave hidden collector/server processes.
        # A debug window belongs to `dev`, whose documented contract keeps an
        # already-running production collector alive for live-data testing.
        roles = ("viewer",) if args.debug else ("viewer", "collector")
        for role in roles:
            _terminate_role(role)

    try:
        from vtrack_desktop import run_desktop

        parameters = inspect.signature(run_desktop).parameters
        kwargs = {}
        if "debug" in parameters:
            kwargs["debug"] = args.debug
        if "on_closed" in parameters:
            kwargs["on_closed"] = stop_owned_services
        return int(run_desktop(_runtime_root(), **kwargs) or 0)
    finally:
        _remove_role("desktop", expected_pid=os.getpid())


def _add_common(parser: argparse.ArgumentParser, *, no_window: bool = True) -> None:
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    if no_window:
        parser.add_argument(
            "--browser",
            action="store_true",
            help="Open in the default browser instead of the native window.",
        )
        parser.add_argument(
            "--no-window",
            action="store_true",
            help="Start the server without opening any UI window.",
        )


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="VTrackShotTracker", description=APP_NAME)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subs = parser.add_subparsers(dest="command", required=True)

    start = subs.add_parser("start", help="Start Shot Tracker services and UI.")
    _add_common(start)
    start.set_defaults(handler=command_start)

    stop = subs.add_parser("stop", help="Stop Shot Tracker services and UI.")
    _add_common(stop, no_window=False)
    stop.set_defaults(handler=command_stop)

    status = subs.add_parser("status", help="Show Shot Tracker process status.")
    _add_common(status, no_window=False)
    status.set_defaults(handler=command_status)

    cleanup = subs.add_parser(
        "cleanup-storage",
        help="Remove BMP frames that already have playable MP4 replacements.",
    )
    cleanup.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    cleanup.add_argument(
        "--apply",
        action="store_true",
        help="Perform cleanup. Without this flag, only report recoverable space.",
    )
    cleanup.set_defaults(handler=command_cleanup_storage)

    review = subs.add_parser("review", help="Open Shot Review without starting the collector.")
    _add_common(review)
    review.set_defaults(handler=command_review)

    dev = subs.add_parser("dev", help="Start the review UI in development mode.")
    _add_common(dev)
    dev.set_defaults(handler=command_dev)

    dev_stop = subs.add_parser("dev-stop", help="Stop development viewer processes.")
    _add_common(dev_stop, no_window=False)
    dev_stop.set_defaults(handler=command_dev_stop)

    check_update = subs.add_parser("check-update", help="Check GitHub Releases for an update.")
    check_update.set_defaults(handler=command_check_update)

    update = subs.add_parser("update", help="Download and launch the latest installer.")
    update.add_argument(
        "--yes",
        action="store_true",
        help="Skip the command-line confirmation prompt.",
    )
    update.set_defaults(handler=command_update)

    viewer = subs.add_parser("__viewer", help=argparse.SUPPRESS)
    viewer.add_argument("--db", type=Path, required=True)
    viewer.add_argument("--port", type=int, default=DEFAULT_PORT)
    viewer.add_argument("--no-browser", action="store_true")
    viewer.add_argument("--dev", action="store_true")
    viewer.set_defaults(handler=_internal_viewer)

    collector = subs.add_parser("__collector", help=argparse.SUPPRESS)
    collector.add_argument("--archive", type=Path, required=True)
    collector.set_defaults(handler=_internal_collector)

    desktop = subs.add_parser("__desktop", help=argparse.SUPPRESS)
    desktop.add_argument("--debug", action="store_true")
    desktop.set_defaults(handler=_internal_desktop)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if not effective_argv:
        # Taskbar pins relaunch the executable without shortcut arguments.
        effective_argv = ["start"]
    _configure_frozen_streams(effective_argv)
    args = create_parser().parse_args(effective_argv)
    return int(args.handler(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
