#!/usr/bin/env python3
r"""
VTrack Shot Collector
---------------------
Watches LAON VTrackToolKit's readable logs plus LPGDLL\ShotData and archives
each new shot into SQLite while copying the shot-camera folder.

No .plog decoding is used.

Sources:
  - GSProJsonClient_*.log: ball + club data plus GSPro Player/club state
  - VTrackToolKit_*.log: VTrack trajectory Carry/TotalDistance/Apex/Side
  - LPGDLL\ShotData\<number>\: camera BMPs and original shot artifacts

Designed for Windows and uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from club_config import map_gspro_club, normalize_bag_mapping

PACKAGE_NAME = "02ce737d-b4f8-4bbb-92b2-1355681ff1e8_qbntr2denpnae"

TS_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")
TRAJ_RE = re.compile(
    r"Trajectory result:\s*"
    r"Carry=(?P<carry>[-+]?\d+(?:\.\d+)?),\s*"
    r"TotalDistance=(?P<total>[-+]?\d+(?:\.\d+)?),\s*"
    r"Apex=(?P<apex>[-+]?\d+(?:\.\d+)?),\s*"
    r"Side=(?P<side>[-+]?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

M_TO_YD = 1.0936132983377078


def dt_from_log(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f")


def dt_iso(dt: datetime) -> str:
    return dt.isoformat(timespec="milliseconds")


@dataclass
class ShotPacket:
    ts: datetime
    payload: dict[str, Any]
    raw_json: str
    player_state: dict[str, Any]
    player_state_time: Optional[datetime]


@dataclass
class Trajectory:
    ts: datetime
    carry_m: float
    total_m: float
    apex_m: float
    side_m: float
    raw_line: str


@dataclass
class FolderEvent:
    number: int
    path: Path
    ts: datetime
    last_signature: tuple[int, int]
    stable_since: float


class TailFile:
    """Poll-oriented tail reader that follows the currently-active log file."""

    def __init__(self, pattern: str):
        self.pattern = pattern
        self.path: Optional[Path] = None
        self.offset = 0
        self.partial = ""

    def choose_latest(self, root: Path) -> Optional[Path]:
        if not root.exists():
            return None
        latest: Optional[Path] = None
        latest_mtime = float("-inf")
        try:
            matches = root.rglob(self.pattern)
            for candidate in matches:
                try:
                    mtime = candidate.stat().st_mtime
                except OSError:
                    # Log rotation can remove a file between enumeration and stat.
                    continue
                if mtime > latest_mtime:
                    latest = candidate
                    latest_mtime = mtime
        except OSError:
            return None
        return latest

    def poll(self, root: Path) -> list[str]:
        latest = self.choose_latest(root)
        if latest is None:
            return []

        try:
            if self.path != latest:
                # Live collector: on a newly-selected session/log, begin at EOF.
                size = latest.stat().st_size
                self.path = latest
                self.offset = size
                self.partial = ""
                print(f"[log] following {latest}")
                return []

            size = latest.stat().st_size
            if size < self.offset:  # truncated
                self.offset = 0
                self.partial = ""

            if size == self.offset:
                return []

            with latest.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(self.offset)
                chunk = f.read()
                self.offset = f.tell()
        except OSError:
            # Treat rotation/deletion/sharing races as a normal retry condition.
            # Resetting the selected path means a replacement log will again be
            # baselined at EOF rather than replaying historical contents.
            self.path = None
            self.offset = 0
            self.partial = ""
            return []

        text = self.partial + chunk
        lines = text.splitlines(keepends=True)
        out: list[str] = []
        self.partial = ""
        for line in lines:
            if line.endswith("\n") or line.endswith("\r"):
                out.append(line.rstrip("\r\n"))
            else:
                self.partial = line
        return out


class GSProParser:
    """Parse GSPro JSON log blocks and retain the latest Player state.

    Framing deliberately delegates JSON structure to ``json.loads`` rather
    than counting raw braces.  Braces inside quoted strings are therefore safe,
    and a fresh timestamped packet header abandons any truncated prior packet.
    """

    MAX_PACKET_CHARS = 2 * 1024 * 1024

    def __init__(self):
        self.collecting = False
        self.ts: Optional[datetime] = None
        self.buf: list[str] = []
        self.player_state: dict[str, Any] = {}
        self.player_state_time: Optional[datetime] = None
        self.last_player_change: Optional[dict[str, Any]] = None

    @staticmethod
    def _packet_start(line: str) -> Optional[tuple[datetime, str]]:
        m = TS_RE.match(line)
        if not m or ("[SEND]" not in line and "[RECEIVE]" not in line) or "{" not in line:
            return None
        return dt_from_log(m.group("ts")), line[line.find("{") :]

    def feed(self, line: str) -> list[ShotPacket]:
        start = self._packet_start(line)
        if start is not None:
            # A fresh top-level packet is authoritative.  If the previous JSON
            # was truncated/malformed, discard it instead of poisoning later data.
            self.collecting = True
            self.ts, first = start
            self.buf = [first]
        elif self.collecting:
            self.buf.append(line)
        else:
            return []

        raw = "\n".join(self.buf).strip()
        if len(raw) > self.MAX_PACKET_CHARS:
            self._reset_packet()
            return []
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            # The packet may simply be incomplete.  A later line can complete
            # it; a later timestamped packet header will reset it safely.
            return []
        return self._finish(obj, raw)

    def _reset_packet(self) -> None:
        self.collecting = False
        self.ts = None
        self.buf = []

    def take_player_change(self) -> Optional[dict[str, Any]]:
        change = self.last_player_change
        self.last_player_change = None
        return change

    def reset_for_new_log(self) -> None:
        self._reset_packet()
        self.player_state = {}
        self.player_state_time = None
        self.last_player_change = None

    def _finish(self, obj: dict[str, Any], raw: str) -> list[ShotPacket]:
        ts = self.ts
        self._reset_packet()
        if ts is None or not isinstance(obj, dict):
            return []

        player = obj.get("Player")
        if isinstance(player, dict):
            changed = False
            for key in ("Club", "Handed", "DistanceToTarget", "Surface"):
                if key in player and player[key] is not None:
                    if self.player_state.get(key) != player[key]:
                        changed = True
                    self.player_state[key] = player[key]
            if changed:
                self.player_state_time = ts
                self.last_player_change = dict(self.player_state)

        opts = obj.get("ShotDataOptions") or {}
        if opts.get("ContainsBallData") is True and obj.get("BallData"):
            return [
                ShotPacket(
                    ts=ts,
                    payload=obj,
                    raw_json=raw,
                    player_state=dict(self.player_state),
                    player_state_time=self.player_state_time,
                )
            ]
        return []


class TrajectoryParser:
    def feed(self, line: str) -> list[Trajectory]:
        if "Trajectory result:" not in line:
            return []
        tsm = TS_RE.match(line)
        m = TRAJ_RE.search(line)
        if not tsm or not m:
            return []
        return [
            Trajectory(
                ts=dt_from_log(tsm.group("ts")),
                carry_m=float(m.group("carry")),
                total_m=float(m.group("total")),
                apex_m=float(m.group("apex")),
                side_m=float(m.group("side")),
                raw_line=line,
            )
        ]


def find_ffmpeg() -> Optional[str]:
    """Return an ffmpeg executable if one is available."""
    if getattr(sys, "frozen", False):
        bundled = Path(sys.executable).resolve().parent / "ffmpeg.exe"
        if bundled.is_file():
            return str(bundled)

    found = shutil.which("ffmpeg")
    if found:
        return found

    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
        Path(os.environ.get("ProgramFiles", "")) / "ffmpeg" / "bin" / "ffmpeg.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Gyan" / "ffmpeg" / "bin" / "ffmpeg.exe",
        Path("C:/ffmpeg/bin/ffmpeg.exe"),
    ]
    for p in candidates:
        if p and p.exists():
            return str(p)
    return None


def make_mp4(
    ffmpeg: str,
    folder: Path,
    input_pattern: str,
    output_name: str,
    fps: float,
) -> Optional[Path]:
    """
    Convert a numbered BMP sequence in `folder` to H.264 MP4.
    Returns the output path on success, None if the sequence is absent/fails.
    """
    # Verify the sequence exists before invoking ffmpeg.
    glob_pattern = input_pattern.replace("%02d", "*")
    if not list(folder.glob(glob_pattern)):
        return None

    out = folder / output_name
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-framerate", str(fps),
        "-start_number", "1",
        "-i", str(folder / input_pattern),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(out),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if out.exists() and out.stat().st_size > 0:
            return out
    except (subprocess.CalledProcessError, OSError):
        return None
    return None


def make_shot_videos(
    ffmpeg: Optional[str],
    archive_path: Optional[Path],
    fps: float,
) -> dict[str, Optional[Path]]:
    """
    Create:
      impact_replay.mp4  from +SHO_LIB_Cam1_*.bmp (VTrack's processed/overlay sequence)
      cam1_raw.mp4       from Cam1_*.bmp
      cam2_raw.mp4       from Cam2_*.bmp
    """
    result: dict[str, Optional[Path]] = {
        "replay": None,
        "cam1": None,
        "cam2": None,
    }
    if not ffmpeg or not archive_path or not archive_path.exists():
        return result

    result["replay"] = make_mp4(
        ffmpeg, archive_path, "+SHO_LIB_Cam1_%02d.bmp", "impact_replay.mp4", fps
    )
    result["cam1"] = make_mp4(
        ffmpeg, archive_path, "Cam1_%02d.bmp", "cam1_raw.mp4", fps
    )
    result["cam2"] = make_mp4(
        ffmpeg, archive_path, "Cam2_%02d.bmp", "cam2_raw.mp4", fps
    )
    return result


FRAME_VIDEO_PAIRS = {
    "replay": "+SHO_LIB_Cam1_*.bmp",
    "cam1": "Cam1_*.bmp",
    "cam2": "Cam2_*.bmp",
}


def cleanup_converted_frames(
    videos: dict[str, Optional[Path]], *, dry_run: bool = False
) -> tuple[int, int]:
    """Remove BMP sources only for video outputs that exist and are non-empty."""
    candidates: dict[Path, int] = {}
    for kind, pattern in FRAME_VIDEO_PAIRS.items():
        video = videos.get(kind)
        if not video:
            continue
        try:
            if not video.is_file() or video.stat().st_size <= 0:
                continue
        except OSError:
            continue
        for frame in video.parent.glob(pattern):
            try:
                if frame.is_file():
                    candidates[frame] = frame.stat().st_size
            except OSError:
                continue

    removed = 0
    reclaimed = 0
    for frame, size in candidates.items():
        if not dry_run:
            try:
                frame.unlink()
            except OSError:
                continue
        removed += 1
        reclaimed += size
    return removed, reclaimed


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.cx = sqlite3.connect(path)
        try:
            self.cx.execute("PRAGMA journal_mode=WAL")
            self.cx.execute(
                """
                CREATE TABLE IF NOT EXISTS shots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shot_time TEXT NOT NULL,
                    trajectory_time TEXT,
                    device_id TEXT,
                    units TEXT,
                    api_version TEXT,

                    ball_speed REAL,
                    spin_axis REAL,
                    total_spin REAL,
                    back_spin REAL,
                    side_spin REAL,
                    hla REAL,
                    vla REAL,
                    gspro_carry_yards REAL,

                    club_speed REAL,
                    angle_of_attack REAL,
                    face_to_target REAL,
                    loft REAL,
                    club_path REAL,
                    vertical_face_impact REAL,
                    horizontal_face_impact REAL,

                    vtrack_carry_m REAL,
                    vtrack_carry_yards REAL,
                    total_distance_m REAL,
                    total_distance_yards REAL,
                    apex_m REAL,
                    apex_yards REAL,
                    side_m REAL,
                    side_yards REAL,

                    club TEXT,
                    gspro_club_raw TEXT,
                    player_handed TEXT,
                    distance_to_target REAL,
                    surface TEXT,
                    player_state_time TEXT,
                    session_id INTEGER,

                    shot_folder_number INTEGER,
                    source_shot_folder TEXT,
                    archive_path TEXT,
                    cam1_frames INTEGER DEFAULT 0,
                    cam2_frames INTEGER DEFAULT 0,
                    replay_video_path TEXT,
                    cam1_video_path TEXT,
                    cam2_video_path TEXT,

                    gspro_json TEXT,
                    trajectory_line TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            self.cx.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_shots_shot_time ON shots(shot_time)"
            )
            self.cx.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    session_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    is_manual INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            self.cx.execute("CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(session_date)")
            self.cx.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Migrate databases made by earlier collector versions.
            existing_cols = {
                row[1] for row in self.cx.execute("PRAGMA table_info(shots)").fetchall()
            }
            migration_columns = {
                "replay_video_path": "TEXT",
                "cam1_video_path": "TEXT",
                "cam2_video_path": "TEXT",
                "club": "TEXT",
                "gspro_club_raw": "TEXT",
                "player_handed": "TEXT",
                "distance_to_target": "REAL",
                "surface": "TEXT",
                "player_state_time": "TEXT",
                "session_id": "INTEGER",
            }
            for col, sql_type in migration_columns.items():
                if col not in existing_cols:
                    self.cx.execute(f"ALTER TABLE shots ADD COLUMN {col} {sql_type}")

            self.cx.commit()
        except Exception:
            self.cx.close()
            raise

    def close(self) -> None:
        self.cx.close()

    def bag_mapping(self) -> dict[str, str]:
        row = self.cx.execute("SELECT value FROM app_settings WHERE key='club_bag_mapping'").fetchone()
        return normalize_bag_mapping(row[0] if row else None)

    def mapped_club(self, raw_club: Any) -> Optional[str]:
        return map_gspro_club(raw_club, self.bag_mapping())

    def session_for_shot(self, shot_ts: datetime) -> int:
        day = shot_ts.strftime("%Y-%m-%d")
        active = self.cx.execute("SELECT value FROM app_settings WHERE key='active_session_id'").fetchone()
        if active and active[0]:
            row = self.cx.execute("SELECT id, session_date FROM sessions WHERE id=?", (active[0],)).fetchone()
            if row and row[1] == day:
                return int(row[0])
            self.cx.execute("DELETE FROM app_settings WHERE key='active_session_id'")
        row = self.cx.execute("SELECT id FROM sessions WHERE session_date=? AND is_manual=0 ORDER BY id LIMIT 1", (day,)).fetchone()
        if row:
            return int(row[0])
        cur = self.cx.execute("INSERT INTO sessions(name,session_date,start_time,is_manual,created_at) VALUES(?,?,?,?,?)",
                              (day, day, dt_iso(shot_ts), 0, datetime.now().isoformat(timespec='seconds')))
        self.cx.commit()
        return int(cur.lastrowid)

    def insert(
        self,
        packet: ShotPacket,
        traj: Optional[Trajectory],
        folder: Optional[FolderEvent],
        archive_path: Optional[Path],
        videos: Optional[dict[str, Optional[Path]]] = None,
    ) -> int:
        p = packet.payload
        ball = p.get("BallData") or {}
        club = p.get("ClubData") or {}

        def v(d: dict[str, Any], key: str) -> Any:
            x = d.get(key)
            return x if x is not None else None

        cam1 = cam2 = 0
        if archive_path and archive_path.exists():
            cam1 = len(list(archive_path.glob("Cam1_*.bmp")))
            cam2 = len(list(archive_path.glob("Cam2_*.bmp")))

        row = {
            "shot_time": dt_iso(packet.ts),
            "trajectory_time": dt_iso(traj.ts) if traj else None,
            "device_id": p.get("DeviceID"),
            "units": p.get("Units"),
            "api_version": p.get("APIVersion"),
            "ball_speed": v(ball, "Speed"),
            "spin_axis": v(ball, "SpinAxis"),
            "total_spin": v(ball, "TotalSpin"),
            "back_spin": v(ball, "BackSpin"),
            "side_spin": v(ball, "SideSpin"),
            "hla": v(ball, "HLA"),
            "vla": v(ball, "VLA"),
            "gspro_carry_yards": v(ball, "CarryDistance"),
            "club_speed": v(club, "Speed"),
            "angle_of_attack": v(club, "AngleOfAttack"),
            "face_to_target": v(club, "FaceToTarget"),
            "loft": v(club, "Loft"),
            "club_path": v(club, "Path"),
            "vertical_face_impact": v(club, "VerticalFaceImpact"),
            "horizontal_face_impact": v(club, "HorizontalFaceImpact"),
            "vtrack_carry_m": traj.carry_m if traj else None,
            "vtrack_carry_yards": traj.carry_m * M_TO_YD if traj else None,
            "total_distance_m": traj.total_m if traj else None,
            "total_distance_yards": traj.total_m * M_TO_YD if traj else None,
            "apex_m": traj.apex_m if traj else None,
            "apex_yards": traj.apex_m * M_TO_YD if traj else None,
            "side_m": traj.side_m if traj else None,
            "side_yards": traj.side_m * M_TO_YD if traj else None,
            "club": self.mapped_club(packet.player_state.get("Club")),
            "gspro_club_raw": packet.player_state.get("Club"),
            "player_handed": packet.player_state.get("Handed"),
            "distance_to_target": packet.player_state.get("DistanceToTarget"),
            "surface": packet.player_state.get("Surface"),
            "player_state_time": dt_iso(packet.player_state_time) if packet.player_state_time else None,
            "session_id": self.session_for_shot(packet.ts),
            "shot_folder_number": folder.number if folder else None,
            "source_shot_folder": str(folder.path) if folder else None,
            "archive_path": str(archive_path) if archive_path else None,
            "cam1_frames": cam1,
            "cam2_frames": cam2,
            "replay_video_path": str(videos.get("replay")) if videos and videos.get("replay") else None,
            "cam1_video_path": str(videos.get("cam1")) if videos and videos.get("cam1") else None,
            "cam2_video_path": str(videos.get("cam2")) if videos and videos.get("cam2") else None,
            "gspro_json": packet.raw_json,
            "trajectory_line": traj.raw_line if traj else None,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

        cols = ", ".join(row)
        qs = ", ".join("?" for _ in row)
        try:
            cur = self.cx.execute(
                f"INSERT INTO shots ({cols}) VALUES ({qs})", tuple(row.values())
            )
            self.cx.commit()
            return int(cur.lastrowid)
        except sqlite3.IntegrityError:
            # Duplicate shot timestamp, e.g. collector restarted while same event was buffered.
            cur = self.cx.execute(
                "SELECT id FROM shots WHERE shot_time=?", (row["shot_time"],)
            )
            existing = cur.fetchone()
            return int(existing[0]) if existing else -1


def folder_signature(path: Path) -> tuple[int, int]:
    files = [p for p in path.iterdir() if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    return (len(files), total)


def folder_event(path: Path) -> FolderEvent:
    # st_ctime is creation time on Windows. Use latest file mtime as the shot-folder
    # event time when available because the camera frame write completes near the shot.
    file_times = [p.stat().st_mtime for p in path.iterdir() if p.is_file()]
    ts_epoch = max(file_times) if file_times else path.stat().st_ctime
    return FolderEvent(
        number=int(path.name),
        path=path,
        ts=datetime.fromtimestamp(ts_epoch),
        last_signature=folder_signature(path),
        stable_since=time.monotonic(),
    )


def copy_shot_folder(src: Path, archive_root: Path, folder_num: int, shot_ts: datetime) -> Path:
    day = shot_ts.strftime("%Y-%m-%d")
    dest = archive_root / "shots" / day / f"{shot_ts.strftime('%H%M%S_%f')[:-3]}_folder_{folder_num}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, dirs_exist_ok=True)
    return dest


def seconds(a: datetime, b: datetime) -> float:
    return abs((a - b).total_seconds())


def discover_numbered_folders(root: Path) -> dict[int, Path]:
    out: dict[int, Path] = {}
    if not root.exists():
        return out
    for p in root.iterdir():
        if p.is_dir() and p.name.isdigit():
            out[int(p.name)] = p
    return out


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Archive new LAON VTrack shots automatically.")
    parser.add_argument(
        "--archive",
        type=Path,
        default=Path.home() / "Documents" / "VTrackArchive",
        help="Archive root (default: ~/Documents/VTrackArchive)",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=0.5,
        help="Polling interval in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--match-window",
        type=float,
        default=20.0,
        help="Max seconds between log shot and camera folder event (default: 20)",
    )
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Do not copy ShotData camera folders; store original paths only.",
    )
    parser.add_argument(
        "--video-fps",
        type=float,
        default=10.0,
        help="Playback frame rate for camera videos (default: 10 fps).",
    )
    parser.add_argument(
        "--keep-source-frames",
        action="store_true",
        default=os.environ.get("VTRACK_KEEP_SOURCE_FRAMES", "").strip().lower()
        in {"1", "true", "yes", "on"},
        help=(
            "Keep archived BMP frame sequences after MP4 conversion. "
            "Defaults to removing frames whose video was created successfully."
        ),
    )
    args = parser.parse_args(argv)

    local = os.environ.get("LOCALAPPDATA")
    if not local:
        print("ERROR: LOCALAPPDATA is not set. This collector is intended for Windows.", file=sys.stderr)
        return 2

    package_root = Path(local) / "Packages" / PACKAGE_NAME
    local_state = package_root / "LocalState" / "LAON PEOPLE"
    logs_root = local_state / "VTrackToolKit" / "AppLogs"
    shotdata_root = local_state / "LPGDLL" / "ShotData"

    if not package_root.exists():
        print(f"ERROR: VTrack package not found:\n  {package_root}", file=sys.stderr)
        return 2

    archive_root = args.archive.expanduser().resolve()
    archive_root.mkdir(parents=True, exist_ok=True)
    heartbeat_path = archive_root / "collector_heartbeat.json"
    def write_heartbeat(state="running"):
        tmp = heartbeat_path.with_suffix('.tmp')
        payload = {"pid": os.getpid(), "epoch": time.time(), "state": state, "updated_at": datetime.now().isoformat(timespec='seconds')}
        try:
            tmp.write_text(json.dumps(payload), encoding='utf-8')
            tmp.replace(heartbeat_path)
        except OSError:
            pass
    write_heartbeat()
    db = Database(archive_root / "vtrack_shots.sqlite3")
    ffmpeg = find_ffmpeg()

    gs_tail = TailFile("GSProJsonClient_*.log")
    vt_tail = TailFile("VTrackToolKit_*.log")
    gs_parser = GSProParser()
    vt_parser = TrajectoryParser()

    # Establish log tails at EOF and baseline current folder signatures.
    # VTrack may create a new numbered folder OR update/reuse an existing one,
    # so watch for both kinds of change.
    gs_tail.poll(logs_root)
    vt_tail.poll(logs_root)

    known_folder_signatures: dict[int, tuple[int, int]] = {}
    known_folder_mtime: dict[int, float] = {}
    for num, p in discover_numbered_folders(shotdata_root).items():
        try:
            known_folder_signatures[num] = folder_signature(p)
            file_times = [x.stat().st_mtime for x in p.iterdir() if x.is_file()]
            known_folder_mtime[num] = max(file_times) if file_times else p.stat().st_mtime
        except OSError:
            pass

    packets: list[ShotPacket] = []
    trajectories: list[Trajectory] = []
    folders: list[FolderEvent] = []
    consumed_traj: set[int] = set()

    print()
    print("VTrack Shot Collector is running.")
    print(f"  Database : {db.path}")
    print(f"  Archive  : {archive_root}")
    print(f"  ShotData : {shotdata_root}")
    print("  Mode     : NEW shots only")
    if ffmpeg:
        print(f"  Video    : enabled ({args.video_fps:g} fps)")
    else:
        print("  Video    : disabled - ffmpeg not found")
        print("             Install with: winget install Gyan.FFmpeg")
    print("Press Ctrl+C to stop.")
    print()

    try:
        while True:
            # 1) Read new log lines. Reset cached GSPro Player state if VTrack
            # starts a new GSPro log/session, so the first shot cannot inherit a
            # club from an older session.
            previous_gs_log = gs_tail.path
            gs_lines = gs_tail.poll(logs_root)
            if previous_gs_log is not None and gs_tail.path != previous_gs_log:
                gs_parser.reset_for_new_log()
                print("[player] new GSPro log - waiting for fresh club state")
            for line in gs_lines:
                new_packets = gs_parser.feed(line)
                player_change = gs_parser.take_player_change()
                if player_change:
                    print(
                        f"[player] club={player_change.get('Club','?')} "
                        f"handed={player_change.get('Handed','?')} "
                        f"target={player_change.get('DistanceToTarget','?')}"
                    )
                for pkt in new_packets:
                    packets.append(pkt)
                    b = pkt.payload.get("BallData") or {}
                    c = pkt.payload.get("ClubData") or {}
                    print(
                        f"[shot] {dt_iso(pkt.ts)} "
                        f"club={pkt.player_state.get('Club','?')} "
                        f"ball={b.get('Speed')} {pkt.payload.get('Units','')} "
                        f"clubSpeed={c.get('Speed')}"
                    )

            for line in vt_tail.poll(logs_root):
                for tr in vt_parser.feed(line):
                    trajectories.append(tr)
                    print(
                        f"[trajectory] {dt_iso(tr.ts)} "
                        f"carry={tr.carry_m*M_TO_YD:.2f} yd "
                        f"total={tr.total_m*M_TO_YD:.2f} yd"
                    )

            # 2) Detect newly-created OR modified/reused numbered ShotData folders.
            current = discover_numbered_folders(shotdata_root)
            now_mono = time.monotonic()

            for num, p in sorted(current.items()):
                try:
                    sig = folder_signature(p)
                    file_times = [x.stat().st_mtime for x in p.iterdir() if x.is_file()]
                    newest_mtime = max(file_times) if file_times else p.stat().st_mtime
                except OSError:
                    continue

                old_sig = known_folder_signatures.get(num)
                old_mtime = known_folder_mtime.get(num)
                changed = (
                    old_sig is None
                    or sig != old_sig
                    or old_mtime is None
                    or newest_mtime > old_mtime + 0.001
                )

                if changed:
                    folders = [f for f in folders if f.number != num]
                    folders.append(
                        FolderEvent(
                            number=num,
                            path=p,
                            ts=datetime.fromtimestamp(newest_mtime),
                            last_signature=sig,
                            stable_since=now_mono,
                        )
                    )
                    action = "new" if old_sig is None else "updated"
                    print(f"[camera] {action} ShotData\\{num}")

                known_folder_signatures[num] = sig
                known_folder_mtime[num] = newest_mtime

            # Update stability/timestamp for pending folders while VTrack is still writing.
            for f in folders:
                if not f.path.exists():
                    continue
                try:
                    sig = folder_signature(f.path)
                    file_times = [p.stat().st_mtime for p in f.path.iterdir() if p.is_file()]
                    newest_mtime = max(file_times) if file_times else f.path.stat().st_mtime
                except OSError:
                    continue

                if sig != f.last_signature or newest_mtime > f.ts.timestamp() + 0.001:
                    f.last_signature = sig
                    f.stable_since = now_mono
                    f.ts = datetime.fromtimestamp(newest_mtime)
                    known_folder_signatures[f.number] = sig
                    known_folder_mtime[f.number] = newest_mtime

            # 3) Match complete events. A trajectory normally precedes the SEND JSON by milliseconds.
            remaining_packets: list[ShotPacket] = []
            for pkt in packets:
                # Closest unused trajectory within 2 seconds.
                candidates = [
                    (i, tr) for i, tr in enumerate(trajectories)
                    if i not in consumed_traj and seconds(pkt.ts, tr.ts) <= 2.0
                ]
                tr_idx = None
                tr = None
                if candidates:
                    tr_idx, tr = min(candidates, key=lambda it: seconds(pkt.ts, it[1].ts))

                # Only use a camera folder once it has been stable for >=1.25 sec.
                ready_folders = [
                    f for f in folders
                    if now_mono - f.stable_since >= 1.25 and seconds(pkt.ts, f.ts) <= args.match_window
                ]
                folder = min(ready_folders, key=lambda f: seconds(pkt.ts, f.ts)) if ready_folders else None

                age = (datetime.now() - pkt.ts).total_seconds()

                # Wait briefly for trajectory and camera folder to arrive.
                if (tr is None or folder is None) and age < 12.0:
                    remaining_packets.append(pkt)
                    continue

                if tr_idx is not None:
                    consumed_traj.add(tr_idx)

                archive_path = None
                if folder is not None:
                    if not args.no_copy:
                        try:
                            archive_path = copy_shot_folder(
                                folder.path, archive_root, folder.number, pkt.ts
                            )
                        except Exception as e:
                            print(f"[warning] camera archive copy failed: {e}")
                    if archive_path is None:
                        archive_path = folder.path
                    folders.remove(folder)

                videos = make_shot_videos(ffmpeg, archive_path, args.video_fps)
                if videos.get("replay"):
                    print(f"[video] {videos['replay'].name}")
                if videos.get("cam1"):
                    print(f"[video] {videos['cam1'].name}")
                if videos.get("cam2"):
                    print(f"[video] {videos['cam2'].name}")

                shot_id = db.insert(pkt, tr, folder, archive_path, videos)

                if not args.no_copy and not args.keep_source_frames:
                    removed, reclaimed = cleanup_converted_frames(videos)
                    if removed:
                        print(
                            f"[storage] removed {removed} converted BMP frames "
                            f"({reclaimed / (1024 * 1024):.1f} MiB reclaimed)"
                        )

                ball = pkt.payload.get("BallData") or {}
                total_yd = tr.total_m * M_TO_YD if tr else None
                msg = (
                    f"[saved] shot #{shot_id}"
                    f"  club={pkt.player_state.get('Club','?')}"
                    f"  carry={ball.get('CarryDistance')}"
                    f"  total={f'{total_yd:.2f}' if total_yd is not None else 'n/a'}"
                )
                if folder:
                    msg += f"  camera-folder={folder.number}"
                else:
                    msg += "  camera-folder=NOT MATCHED"
                print(msg)

            packets = remaining_packets

            # Trim old trajectory records after one minute.
            cutoff = datetime.now().timestamp() - 60
            new_traj = []
            new_consumed = set()
            for i, tr in enumerate(trajectories):
                if tr.ts.timestamp() >= cutoff:
                    new_i = len(new_traj)
                    new_traj.append(tr)
                    if i in consumed_traj:
                        new_consumed.add(new_i)
            trajectories = new_traj
            consumed_traj = new_consumed

            write_heartbeat()
            time.sleep(args.poll)

    except KeyboardInterrupt:
        write_heartbeat('stopped')
        print("\nStopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
