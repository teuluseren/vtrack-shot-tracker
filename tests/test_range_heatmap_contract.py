import re
import unittest

from review.shot_review import HTML, ShotStore


class RangeAndHeatmapContractTests(unittest.TestCase):
    def test_positive_lateral_is_rendered_toward_right_bottom(self):
        self.assertIn("py=s=>mid+((s-sideCenter)/sideHalf)*plotH*.47", HTML)
        self.assertIn("topPy=s=>topMid+((s-sideCenter)/sideHalf)*topH*.44", HTML)
        self.assertIn("py=s=>mid+(Math.max(-sideAbs,Math.min(sideAbs,s))/sideAbs)*plotH*.46", HTML)
        self.assertNotIn("py=s=>mid-((s-sideCenter)/sideHalf)*plotH*.47", HTML)
        self.assertNotIn("topPy=s=>topMid-((s-sideCenter)/sideHalf)*topH*.44", HTML)

    def test_range_navigation_matches_positive_down_orientation(self):
        self.assertIn("worldSide=before.sideCenter+(anchor.y-.5)*before.sideHalf*2", HTML)
        self.assertIn("state.rangePanSide=worldSide-(anchor.y-.5)*nextHalf*2", HTML)
        self.assertIn("state.rangePanSide-=svgDy/Math.max(1,(g.bottom-g.top)*g.verticalFraction)*view.sideHalf*2", HTML)

    def test_print_report_places_positive_side_below_negative_side(self):
        rows = [
            {"club": "I7", "side_yards": -10, "gspro_carry_yards": 150, "vtrack_carry_yards": None},
            {"club": "I7", "side_yards": 10, "gspro_carry_yards": 150, "vtrack_carry_yards": None},
        ]
        svg = ShotStore.report_range_svg(None, rows)
        points = re.findall(r'<circle cx="[^"]+" cy="([0-9.]+)" r="4"', svg)
        self.assertGreaterEqual(len(points), 2)
        left_y, right_y = map(float, points[-2:])
        self.assertLess(left_y, right_y)

    def test_heatmap_is_scoped_to_selected_shot_session_and_club(self):
        self.assertIn(
            "raw=state.shots.filter(x=>x.session_id===s.session_id&&club(x.club)===club(s.club)",
            HTML,
        )
        self.assertIn("session strikes", HTML)

    def test_heatmap_refreshes_on_poll_even_when_follow_is_paused(self):
        self.assertIn("renderTree(force);drawRange();drawHeat();renderInsights();setLiveStatus(status)", HTML)

    def test_new_empty_session_clears_old_shot_and_heatmap_context(self):
        self.assertIn("sessionFocus:null", HTML)
        self.assertIn("state.sessionFocus=Number(result.id)||null;state.selected=null;state.detail=null", HTML)
        self.assertIn("state.sessionFocus?shots.find(s=>s.session_id===state.sessionFocus)?.id:null", HTML)
        self.assertIn("state.sessionFocus=state.detail.session_id", HTML)

    def test_selected_impact_marker_is_smaller_with_bolder_outline(self):
        self.assertIn("SELECTED_MARKER_MM=20", HTML)
        self.assertIn("ctx.lineWidth=Math.max(2.4*dpr,ballR*.14)", HTML)
        self.assertIn("ctx.fillStyle='rgba(255,255,255,.025)'", HTML)


if __name__ == "__main__":
    unittest.main()
