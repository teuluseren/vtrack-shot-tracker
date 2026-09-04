import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from club_config import canonical_club, display_club, map_gspro_club, normalize_bag_mapping
from collector.vtrack_shot_collector import Database, ShotPacket


class ClubConfigTests(unittest.TestCase):
    def test_gspro_display_names_normalize_to_bag_codes(self):
        aliases = {
            "Driver": "D",
            "3 Wood": "W3",
            "Fairway Wood 5": "W5",
            "7-iron": "I7",
            "Iron 4": "I4",
            "3 Hybrid": "H3",
            "Hybrid 5": "H5",
            "Pitching Wedge": "PW",
            "56° Wedge": "56DEG",
            "Putter": "PT",
        }
        for raw, expected in aliases.items():
            with self.subTest(raw=raw):
                self.assertEqual(canonical_club(raw), expected)

    def test_mapping_accepts_readable_names_and_ignores_invalid_values(self):
        self.assertEqual(
            normalize_bag_mapping({"3 Wood": "5 Wood", "7 Iron": "I7", "D": "spaceship"}),
            {"W3": "W5"},
        )
        self.assertEqual(map_gspro_club("3 Wood", {"W3": "W5"}), "W5")
        self.assertEqual(display_club("56DEG"), "56° Wedge")

    def test_collector_applies_saved_mapping_and_preserves_raw_gspro_club(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db_path = Path(tempdir) / "shots.sqlite3"
            db = Database(db_path)
            try:
                db.cx.execute(
                    "INSERT INTO app_settings(key,value) VALUES('club_bag_mapping',?)",
                    ('{"W3":"W5"}',),
                )
                db.cx.commit()
                packet = ShotPacket(
                    ts=datetime(2026, 9, 2, 10, 30),
                    payload={"BallData": {}, "ClubData": {}},
                    raw_json="{}",
                    player_state={"Club": "3 Wood"},
                    player_state_time=None,
                )
                shot_id = db.insert(packet, None, None, None)
            finally:
                db.close()
            connection = sqlite3.connect(db_path)
            try:
                row = connection.execute(
                    "SELECT club,gspro_club_raw FROM shots WHERE id=?", (shot_id,)
                ).fetchone()
            finally:
                connection.close()
            self.assertEqual(row, ("W5", "3 Wood"))


if __name__ == "__main__":
    unittest.main()
