import json
import os
import sqlite3
import tempfile
import time
import unittest
from unittest import mock
from datetime import datetime, timedelta
from pathlib import Path

from collector.vtrack_shot_collector import (
    Database,
    GSProParser,
    ShotPacket,
    TailFile,
    Trajectory,
    TrajectoryParser,
    cleanup_converted_frames,
    discover_numbered_folders,
    process_shot_media,
)


class CollectorChaosTests(unittest.TestCase):
    def test_cleanup_removes_only_frames_with_verified_video(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            replay_frames = [
                root / "+SHO_LIB_Cam1_01.bmp",
                root / "+SHO_LIB_Cam1_02.bmp",
            ]
            cam1_frame = root / "Cam1_01.bmp"
            cam2_frame = root / "Cam2_01.bmp"
            for frame in [*replay_frames, cam1_frame, cam2_frame]:
                frame.write_bytes(b"frame")

            replay = root / "impact_replay.mp4"
            replay.write_bytes(b"video")
            empty_cam1 = root / "cam1_raw.mp4"
            empty_cam1.write_bytes(b"")

            videos = {"replay": replay, "cam1": empty_cam1, "cam2": None}
            expected_bytes = sum(frame.stat().st_size for frame in replay_frames)

            self.assertEqual(
                cleanup_converted_frames(videos, dry_run=True),
                (2, expected_bytes),
            )
            self.assertTrue(all(frame.exists() for frame in replay_frames))

            self.assertEqual(cleanup_converted_frames(videos), (2, expected_bytes))
            self.assertTrue(all(not frame.exists() for frame in replay_frames))
            self.assertTrue(cam1_frame.exists())
            self.assertTrue(cam2_frame.exists())

    def test_background_media_processing_persists_paths_before_cleanup(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            db_path = root / "shots.sqlite3"
            db = Database(db_path)
            cur = db.cx.execute(
                "INSERT INTO shots(shot_time,created_at) VALUES(?,?)",
                ("2026-09-04T12:00:00", "2026-09-04T12:00:00"),
            )
            shot_id = int(cur.lastrowid)
            db.cx.commit()
            db.close()

            videos = {}
            for kind, name in (
                ("replay", "impact_replay.mp4"),
                ("cam1", "cam1_raw.mp4"),
                ("cam2", "cam2_raw.mp4"),
            ):
                path = root / name
                path.write_bytes(b"video")
                videos[kind] = path

            with mock.patch(
                "collector.vtrack_shot_collector.make_shot_videos",
                return_value=videos,
            ), mock.patch(
                "collector.vtrack_shot_collector.cleanup_converted_frames",
                return_value=(3, 300),
            ) as cleanup:
                process_shot_media(db_path, shot_id, "ffmpeg", root, 10.0, True)

            cx = sqlite3.connect(db_path)
            try:
                row = cx.execute(
                    """
                    SELECT replay_video_path,cam1_video_path,cam2_video_path
                    FROM shots WHERE id=?
                    """,
                    (shot_id,),
                ).fetchone()
            finally:
                cx.close()
            self.assertEqual(row, tuple(str(videos[k]) for k in ("replay", "cam1", "cam2")))
            cleanup.assert_called_once_with(videos)

    def test_tail_starts_at_eof_and_handles_partial_lines(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            log = root / "GSProJsonClient_001.log"
            log.write_text("historical line\n", encoding="utf-8")
            tail = TailFile("GSProJsonClient_*.log")

            self.assertEqual(tail.poll(root), [])
            with log.open("a", encoding="utf-8") as handle:
                handle.write("new line\npartial")
            self.assertEqual(tail.poll(root), ["new line"])

            with log.open("a", encoding="utf-8") as handle:
                handle.write(" line\n")
            self.assertEqual(tail.poll(root), ["partial line"])

    def test_tail_rotation_does_not_replay_new_file_history(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            first = root / "GSProJsonClient_001.log"
            first.write_text("old first\n", encoding="utf-8")
            tail = TailFile("GSProJsonClient_*.log")
            self.assertEqual(tail.poll(root), [])

            # Keep the original log unambiguously older. Giving the replacement a
            # future timestamp is unstable because appending resets its mtime to now.
            past = time.time() - 5
            os.utime(first, (past, past))
            second = root / "GSProJsonClient_002.log"
            second.write_text("old second\n", encoding="utf-8")
            self.assertEqual(tail.poll(root), [])

            with second.open("a", encoding="utf-8") as handle:
                handle.write("fresh second\n")
            self.assertEqual(tail.poll(root), ["fresh second"])

    def test_gspro_player_state_is_snapshotted_onto_ball_packet(self):
        parser = GSProParser()
        player = (
            '2026-09-02 12:00:00.000 [RECEIVE] '
            '{"Player":{"Club":"3 Wood","Handed":"RH","DistanceToTarget":210,"Surface":"Fairway"}}'
        )
        shot = (
            '2026-09-02 12:00:01.000 [SEND] '
            '{"ShotDataOptions":{"ContainsBallData":true},'
            '"BallData":{"Speed":137.5,"CarryDistance":221.2},'
            '"ClubData":{"Speed":98.1}}'
        )
        self.assertEqual(parser.feed(player), [])
        packets = parser.feed(shot)
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].player_state["Club"], "3 Wood")
        self.assertEqual(packets[0].player_state["Surface"], "Fairway")
        self.assertEqual(packets[0].payload["BallData"]["Speed"], 137.5)

    def test_malformed_json_is_dropped_without_poisoning_next_packet(self):
        parser = GSProParser()
        broken = '2026-09-02 12:00:00.000 [SEND] {not-json}'
        good = (
            '2026-09-02 12:00:01.000 [SEND] '
            '{"ShotDataOptions":{"ContainsBallData":true},"BallData":{"Speed":100}}'
        )
        self.assertEqual(parser.feed(broken), [])
        packets = parser.feed(good)
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].payload["BallData"]["Speed"], 100)

    def test_player_state_reset_prevents_old_club_leaking_into_new_log(self):
        parser = GSProParser()
        parser.feed(
            '2026-09-02 12:00:00.000 [RECEIVE] {"Player":{"Club":"Driver"}}'
        )
        parser.reset_for_new_log()
        packets = parser.feed(
            '2026-09-02 12:00:01.000 [SEND] '
            '{"ShotDataOptions":{"ContainsBallData":true},"BallData":{"Speed":150}}'
        )
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].player_state, {})

    def test_trajectory_parser_accepts_signed_side_and_attack_values(self):
        parser = TrajectoryParser()
        rows = parser.feed(
            "2026-09-02 12:00:00.100 Trajectory result: "
            "Carry=201.25, TotalDistance=214.75, Apex=31.5, Side=-12.25"
        )
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0].carry_m, 201.25)
        self.assertAlmostEqual(rows[0].side_m, -12.25)

    def test_corrupt_bag_mapping_fails_closed_to_no_mapping(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db = Database(Path(tempdir) / "shots.sqlite3")
            db.cx.execute(
                "INSERT INTO app_settings(key,value) VALUES('club_bag_mapping',?)",
                ("{definitely not json",),
            )
            db.cx.commit()
            self.assertEqual(db.bag_mapping(), {})
            self.assertEqual(db.mapped_club("3 Wood"), "W3")
            db.close()

    def test_active_manual_session_is_used_only_for_same_day(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db = Database(Path(tempdir) / "shots.sqlite3")
            today = datetime(2026, 9, 2, 18, 0, 0)
            cur = db.cx.execute(
                "INSERT INTO sessions(name,session_date,start_time,is_manual,created_at) VALUES(?,?,?,?,?)",
                ("Driver fitting", "2026-09-02", today.isoformat(), 1, today.isoformat()),
            )
            manual = int(cur.lastrowid)
            db.cx.execute(
                "INSERT INTO app_settings(key,value) VALUES('active_session_id',?)",
                (str(manual),),
            )
            db.cx.commit()

            self.assertEqual(db.session_for_shot(today), manual)
            next_day = db.session_for_shot(today + timedelta(days=1))
            self.assertNotEqual(next_day, manual)
            active = db.cx.execute(
                "SELECT value FROM app_settings WHERE key='active_session_id'"
            ).fetchone()
            self.assertIsNone(active)
            db.close()

    def test_insert_preserves_raw_club_and_applies_bag_mapping(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db = Database(Path(tempdir) / "shots.sqlite3")
            db.cx.execute(
                "INSERT INTO app_settings(key,value) VALUES('club_bag_mapping',?)",
                (json.dumps({"SW": "54DEG"}),),
            )
            db.cx.commit()
            ts = datetime(2026, 9, 2, 18, 0, 0, 123000)
            packet = ShotPacket(
                ts=ts,
                payload={
                    "BallData": {"Speed": 95, "CarryDistance": 92},
                    "ClubData": {"Speed": 78},
                },
                raw_json="{}",
                player_state={"Club": "Sand Wedge"},
                player_state_time=ts,
            )
            trajectory = Trajectory(ts, 84.0, 87.0, 20.0, 2.0, "trajectory")
            shot_id = db.insert(packet, trajectory, None, None, {})
            row = db.cx.execute(
                "SELECT club,gspro_club_raw,session_id FROM shots WHERE id=?", (shot_id,)
            ).fetchone()
            self.assertEqual(row[0], "54DEG")
            self.assertEqual(row[1], "Sand Wedge")
            self.assertIsNotNone(row[2])
            db.close()

    def test_duplicate_timestamp_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db = Database(Path(tempdir) / "shots.sqlite3")
            ts = datetime(2026, 9, 2, 18, 0, 0, 123000)
            packet = ShotPacket(
                ts=ts,
                payload={"BallData": {"Speed": 100}},
                raw_json="{}",
                player_state={"Club": "7 Iron"},
                player_state_time=ts,
            )
            first = db.insert(packet, None, None, None, {})
            second = db.insert(packet, None, None, None, {})
            self.assertEqual(first, second)
            count = db.cx.execute("SELECT COUNT(*) FROM shots").fetchone()[0]
            self.assertEqual(count, 1)
            db.close()

    def test_discover_numbered_folders_ignores_noise(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "1").mkdir()
            (root / "002").mkdir()
            (root / "notes").mkdir()
            (root / "3.txt").write_text("x", encoding="utf-8")
            found = discover_numbered_folders(root)
            self.assertEqual(set(found), {1, 2})

    def test_json_braces_inside_strings_do_not_break_packet_framing(self):
        parser = GSProParser()
        packets = parser.feed(
            '2026-09-02 12:00:00.000 [SEND] '
            '{"ShotDataOptions":{"ContainsBallData":true},'
            '"BallData":{"Speed":101},"Player":{"Surface":"rough { edge }"}}'
        )
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].payload["Player"]["Surface"], "rough { edge }")

    def test_truncated_packet_is_abandoned_when_fresh_packet_starts(self):
        parser = GSProParser()
        self.assertEqual(
            parser.feed('2026-09-02 12:00:00.000 [SEND] {"ShotDataOptions":'), []
        )
        packets = parser.feed(
            '2026-09-02 12:00:01.000 [SEND] '
            '{"ShotDataOptions":{"ContainsBallData":true},"BallData":{"Speed":102}}'
        )
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].payload["BallData"]["Speed"], 102)

    def test_log_disappearing_between_selection_and_stat_is_retryable(self):
        class VanishingTail(TailFile):
            def choose_latest(self, root):
                latest = super().choose_latest(root)
                if latest and latest.exists():
                    latest.unlink()
                return latest

        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "GSProJsonClient_001.log").write_text("history\n", encoding="utf-8")
            tail = VanishingTail("GSProJsonClient_*.log")
            self.assertEqual(tail.poll(root), [])
            replacement = root / "GSProJsonClient_002.log"
            replacement.write_text("history\n", encoding="utf-8")
            self.assertEqual(tail.poll(root), [])


if __name__ == "__main__":
    unittest.main()
