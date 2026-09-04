"""Static contracts for shot-list header geometry.

The browser smoke test separately verifies the rendered left/right pixel edges against a real shot row.
"""

from pathlib import Path
import unittest


class ShotHeaderAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("review/shot_review.py").read_text(encoding="utf-8")

    def test_header_reuses_exact_shot_row_layout_classes(self):
        self.assertIn(
            '<div class="shotColumns"><span></span><div class="shotSelect shotHeaderSelect">',
            self.source,
        )
        self.assertIn(
            '<span class="shotIdentity"><b>Shot</b><small>time</small></span>',
            self.source,
        )
        self.assertIn(
            '<span class="shotMetric carry"><b>${distanceTitle}</b><small>${unit}</small></span>',
            self.source,
        )
        self.assertIn(
            '<span class="shotMetric ball"><b>Ball</b><small>mph</small></span>',
            self.source,
        )
        self.assertIn(
            '<span class="shotMetric side"><b>Side</b><small>${unit}</small></span>',
            self.source,
        )

    def test_header_does_not_maintain_a_duplicate_metric_grid(self):
        self.assertNotIn("shotColumnsMain", self.source)

    def test_header_fills_the_same_data_column_as_shot_values(self):
        self.assertIn(
            ".shotHeaderSelect{width:100%;pointer-events:none;cursor:default}",
            self.source,
        )

    def test_header_outer_grid_matches_shot_row_gutters(self):
        outer_grid = "grid-template-columns:22px minmax(0,1fr) 24px!important"
        self.assertIn(f".shotColumns{{{outer_grid}", self.source)
        self.assertIn(
            ".shot,.shot:nth-child(odd),.shot:nth-child(even){" + outer_grid,
            self.source,
        )

    def test_row_grid_remains_single_source_of_truth(self):
        grid = (
            "grid-template-columns:minmax(54px,1.18fr) "
            "repeat(3,minmax(39px,.82fr));gap:4px;align-items:center"
        )
        self.assertIn(f".shotSelect{{min-width:0;display:grid;{grid}", self.source)


if __name__ == "__main__":
    unittest.main()
