#!/usr/bin/env python3
"""Create a small deterministic archive for UI smoke/chaos testing."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collector.vtrack_shot_collector import Database


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    archive = args.archive.resolve()
    archive.mkdir(parents=True, exist_ok=True)
    db = Database(archive / "vtrack_shots.sqlite3")

    base = datetime(2026, 9, 2, 18, 0, 0)
    session_id = db.cx.execute(
        "INSERT INTO sessions(name,session_date,start_time,is_manual,created_at) VALUES(?,?,?,?,?)",
        (
            "Share readiness smoke session",
            "2026-09-02",
            base.isoformat(timespec="seconds"),
            1,
            base.isoformat(timespec="seconds"),
        ),
    ).lastrowid

    shots = [
        ("D", 151, 103, 248, 267, -12, 96, 1.5, 6.0, -2.0, 11.5, 2350, -3.0, 2.0, 3.0),
        ("D", 149, 101, 242, 260, 8, 91, -2.0, 5.0, 1.0, 12.0, 2450, -1.0, -3.0, 1.0),
        ("I7", 118, 84, 158, 164, -4, 78, 0.5, 4.0, -4.0, 18.0, 5700, 0.5, 1.0, 4.0),
        ("I7", 116, 82, 154, 160, 5, 74, -1.0, 3.0, -3.0, 17.5, 5900, -0.5, -2.0, 2.0),
        ("54DEG", 88, 73, 94, 98, -3, 58, 1.0, 2.0, -6.0, 29.0, 8200, 0.5, 2.5, -1.0),
        ("54DEG", 86, 71, 90, 95, 4, 55, -1.5, 2.5, -5.0, 30.0, 8400, -0.5, -1.5, 2.0),
    ]
    for index, (
        club,
        ball_speed,
        club_speed,
        carry,
        total,
        side,
        apex,
        hla,
        vla,
        attack,
        loft,
        spin,
        face,
        impact_x,
        impact_y,
    ) in enumerate(shots):
        shot_time = base + timedelta(seconds=index * 20)
        db.cx.execute(
            """
            INSERT INTO shots(
                shot_time, trajectory_time, ball_speed, club_speed,
                gspro_carry_yards, vtrack_carry_yards, total_distance_yards,
                side_yards, apex_yards, hla, vla, back_spin, angle_of_attack,
                face_to_target, loft, club_path, horizontal_face_impact,
                vertical_face_impact, club, gspro_club_raw, session_id, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                shot_time.isoformat(timespec="milliseconds"),
                shot_time.isoformat(timespec="milliseconds"),
                ball_speed,
                club_speed,
                carry,
                carry - 1.0,
                total,
                side,
                apex / 3.0,
                hla,
                vla,
                spin,
                attack,
                face,
                loft,
                face - 0.5,
                impact_x,
                impact_y,
                club,
                club,
                session_id,
                shot_time.isoformat(timespec="seconds"),
            ),
        )

    # Putting values are stored in yards by the collector/viewer and displayed
    # in feet in putting mode.
    for index, (finish_ft, side_ft) in enumerate(((8.5, -0.4), (10.2, 0.3), (12.0, 0.8))):
        shot_time = base + timedelta(minutes=5, seconds=index * 20)
        yards = finish_ft / 3.0
        db.cx.execute(
            """
            INSERT INTO shots(
                shot_time, ball_speed, club_speed, gspro_carry_yards,
                total_distance_yards, side_yards, club, gspro_club_raw,
                distance_to_target, session_id, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                shot_time.isoformat(timespec="milliseconds"),
                5.0,
                4.0,
                yards,
                yards,
                side_ft / 3.0,
                "PT",
                "Putter",
                10.0 / 3.0,
                session_id,
                shot_time.isoformat(timespec="seconds"),
            ),
        )

    db.cx.commit()
    db.close()
    heartbeat = {
        "pid": 12345,
        "epoch": time.time(),
        "state": "running",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    (archive / "collector_heartbeat.json").write_text(
        json.dumps(heartbeat), encoding="utf-8"
    )
    print(archive / "vtrack_shots.sqlite3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
