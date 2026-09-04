import sqlite3
import tempfile
import json
import re
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import review.shot_review as shot_review
from review.shot_review import CLUB_FACE_ASSETS, HTML, ShotStore, _page_html, make_handler


class ShotReviewTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Path(self.tempdir.name) / "shots.sqlite3"
        cx = sqlite3.connect(self.db)
        try:
            cx.execute(
                "CREATE TABLE shots(id INTEGER PRIMARY KEY, shot_time TEXT, club TEXT)"
            )
            cx.commit()
        finally:
            cx.close()
        self.store = ShotStore(self.db)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_generated_raw_camera_video_paths_are_resolved(self):
        self.assertIn("media_processing", self.store.columns())
        root = Path(self.tempdir.name)
        cam1 = root / "cam1_raw.mp4"
        cam2 = root / "cam2_raw.mp4"
        cam1.write_bytes(b"video-1")
        cam2.write_bytes(b"video-2")

        self.assertEqual(
            ShotStore.resolve_media_path({"cam1_video_path": str(cam1)}, "swing1"),
            cam1.resolve(),
        )
        self.assertEqual(
            ShotStore.resolve_media_path({"archive_path": str(root)}, "swing2"),
            cam2.resolve(),
        )

    def test_session_can_be_renamed(self):
        session_id = self.store.create_session("Original")
        self.assertTrue(self.store.rename_session(session_id, "Driver fitting"))
        sessions = self.store.sessions()
        renamed = next(item for item in sessions if item["id"] == session_id)
        self.assertEqual(renamed["name"], "Driver fitting")

    def test_bag_mapping_and_preferences_persist_in_archive(self):
        self.assertEqual(self.store.save_bag_mapping({"3 Wood": "5 Wood"}), {"W3": "W5"})
        self.assertEqual(self.store.bag_mapping(), {"W3": "W5"})
        saved = self.store.save_ui_preferences(
            {
                "theme": "light",
                "rangeDistanceMax": 200,
                "rangePanDistance": 75,
                "rangePanSide": -12.5,
                "unknown": "discarded",
            }
        )
        self.assertEqual(
            saved,
            {
                "theme": "light",
                "rangeDistanceMax": 200,
                "rangePanDistance": 75,
                "rangePanSide": -12.5,
            },
        )
        self.assertEqual(self.store.ui_preferences(), saved)
        page = _page_html(False, saved)
        self.assertIn('"rangeDistanceMax":200', page)
        self.assertIn('"rangePanDistance":75', page)
        self.assertIn('"rangePanSide":-12.5', page)
        self.assertNotIn("__VTRACK_USER_PREFERENCES__", page)

    def test_bag_mapping_and_preferences_http_api(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.store))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for path, payload in (
                ("bag-mapping", {"mapping": {"3 Wood": "5 Wood"}}),
                ("preferences", {"theme": "light", "rangeDistanceMax": 250}),
            ):
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/api/{path}",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=2) as response:
                    self.assertEqual(response.status, 200)
            self.assertEqual(self.store.bag_mapping(), {"W3": "W5"})
            self.assertEqual(self.store.ui_preferences()["rangeDistanceMax"], 250)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_empty_session_name_is_rejected(self):
        session_id = self.store.create_session("Original")
        self.assertFalse(self.store.rename_session(session_id, "   "))

    def test_shot_can_be_reclassified_and_moved_to_another_session(self):
        original = self.store.create_session("Original")
        destination = self.store.create_session("Destination")
        with self.store.connect() as connection:
            shot_id = connection.execute(
                "INSERT INTO shots(shot_time,club,session_id) VALUES(?,?,?)",
                ("2026-08-31T10:00:00", "I7", original),
            ).lastrowid
            connection.commit()
        changed, error = self.store.update_shot(shot_id, "3w", destination)
        self.assertTrue(changed)
        self.assertIsNone(error)
        shot = self.store.get_shot(shot_id)
        self.assertEqual(shot["club"], "W3")
        self.assertEqual(shot["session_id"], destination)

    def test_session_rename_api(self):
        session_id = self.store.create_session("Original")
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.store))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/sessions/{session_id}",
                data=json.dumps({"name": "API renamed"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="PATCH",
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                self.assertEqual(response.status, 200)
            renamed = next(
                item for item in self.store.sessions() if item["id"] == session_id
            )
            self.assertEqual(renamed["name"], "API renamed")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_development_page_includes_live_reload(self):
        page = _page_html(True)
        self.assertIn("/api/dev-revision", page)
        self.assertIn("location.reload()", page)
        self.assertEqual(page.count("/api/dev-revision"), 1)
        self.assertLess(page.index("function exportSummary"), page.index("const loaded="))

    def test_development_revision_api(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.store, True))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/api/dev-revision", timeout=2
            ) as response:
                payload = json.loads(response.read())
            self.assertRegex(payload["revision"], r"^[0-9a-f]{64}$")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_local_club_face_assets_are_served(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.store))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for name in CLUB_FACE_ASSETS:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{server.server_port}/assets/{name}", timeout=2
                ) as response:
                    self.assertEqual(response.headers.get_content_type(), "image/png")
                    self.assertEqual(response.read()[:8], b"\x89PNG\r\n\x1a\n")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_development_html_is_reread_after_save(self):
        source = Path(self.tempdir.name) / "dev_ui.py"
        original_cache = list(shot_review._DEV_HTML_CACHE)
        try:
            with mock.patch.object(shot_review, "__file__", str(source)):
                source.write_text("HTML = 'first'\n", encoding="utf-8")
                shot_review._DEV_HTML_CACHE[:] = [None, HTML, "initial"]
                first, first_revision = shot_review._development_html()
                source.write_text("HTML = 'second'\n", encoding="utf-8")
                second, second_revision = shot_review._development_html()
            self.assertEqual(first, "first")
            self.assertEqual(second, "second")
            self.assertNotEqual(first_revision, second_revision)
        finally:
            shot_review._DEV_HTML_CACHE[:] = original_cache

    def test_ui_contract_contains_requested_controls(self):
        self.assertIn('viewBox="0 0 960 760"', HTML)
        self.assertIn("data-club-toggle", HTML)
        self.assertIn("data-rename", HTML)
        self.assertIn("fairway wood", HTML)
        self.assertIn("hybrid", HTML)
        self.assertIn("drawFaceCenter", HTML)
        self.assertIn(".faceStage:before{display:none}", HTML)
        self.assertIn("data-range-view", HTML)
        self.assertIn("data-distance-mode", HTML)
        self.assertIn("data-eye-session", HTML)
        self.assertIn("data-eye-club", HTML)
        self.assertIn("data-eye-shot", HTML)
        self.assertIn("function eyeIcon", HTML)
        self.assertIn("function drawFlight", HTML)
        self.assertIn("function drawPutting", HTML)
        self.assertIn('data-range-view="putting"', HTML)
        self.assertIn("repeat(10,minmax(0,1fr))", HTML)
        self.assertIn("coverageScale=Math.max(1,farthest)*1.06", HTML)
        self.assertIn("LATERAL (YD)", HTML)
        self.assertIn("function validImpact", HTML)
        self.assertIn("invalid reading", HTML)
        self.assertIn("grid-template-columns:minmax(0,1fr) auto", HTML)
        self.assertEqual(HTML.count("function renderTree("), 1)
        self.assertEqual(HTML.count("function drawRange("), 1)
        self.assertIn('id="updateButton"', HTML)
        self.assertIn('<title>vTrack Shot Tracker</title>', HTML)
        self.assertIn('data-version="__VTRACK_VERSION__"', HTML)
        self.assertIn('>ⓘ v__VTRACK_VERSION__</button>', HTML)
        self.assertIn("`ⓘ v${x.current_version}`", HTML)
        self.assertIn("X-VTrack-Update", HTML)
        self.assertIn("function refreshSelectedMedia", HTML)
        self.assertIn("await refreshSelectedMedia()", HTML)
        self.assertIn("media_processing", HTML)
        self.assertIn("mediaSpinner", HTML)
        self.assertIn("mediaSpin", HTML)
        self.assertIn("ENCODING", HTML)
        self.assertIn("Video encoding is running in the background", HTML)

    def test_latest_navigation_and_export_contract(self):
        self.assertIn('class="body sessionListBody"', HTML)
        self.assertIn('class="btn primary sessionNew"', HTML)
        self.assertIn("clubsInitialized:false", HTML)
        self.assertIn("state.closedClubs.delete(key(state.detail))", HTML)
        self.assertIn("function clubName", HTML)
        self.assertIn('data-edit-shot="${s.id}"', HTML)
        self.assertIn('id="shotModal"', HTML)
        self.assertIn("/api/shots/${id}", HTML)
        self.assertIn('id="summaryModal"', HTML)
        self.assertIn("scratchReference", HTML)
        self.assertIn('id="exportRange"', HTML)
        self.assertIn('id="exportReplay"', HTML)
        self.assertIn('id="exportShot"', HTML)
        self.assertIn('id="snapCameras"', HTML)
        self.assertIn("vtrackCameraLayout", HTML)
        self.assertIn("writing-mode:vertical-rl", HTML)
        self.assertIn("flex-direction:column!important", HTML)
        self.assertIn("border-top:3px solid", HTML)

    def test_workspace_preferences_comparison_and_panel_export_contract(self):
        self.assertIn("vtrackWorkspacePreferencesV1", HTML)
        self.assertIn("collapsedColumns", HTML)
        self.assertIn("openClubs", HTML)
        self.assertIn("hiddenShots", HTML)
        self.assertIn("golferProfile", HTML)
        self.assertIn('id="panelExportModal"', HTML)
        self.assertIn('name="panel"', HTML)
        self.assertIn("exportStrikePanel", HTML)
        self.assertIn('id="exportSummary"', HTML)
        self.assertIn("Carry distance", HTML)
        self.assertIn("Total distance", HTML)
        self.assertIn("function golferSvg", HTML)
        self.assertIn("PERSONA_ART", HTML)
        self.assertIn("/assets/persona-woman.png", HTML)
        self.assertIn("/assets/persona-man.png", HTML)
        self.assertIn("/assets/persona-senior.png", HTML)
        self.assertIn("/assets/persona-junior.png", HTML)
        self.assertNotIn("Sources & calculation method", HTML)
        self.assertNotIn("TrackMan", HTML)
        self.assertIn("100% matches the app-defined", HTML)
        self.assertIn("stronger results can score higher", HTML)
        self.assertIn("Woman", HTML)
        self.assertIn("Man", HTML)
        self.assertIn("Senior", HTML)
        self.assertIn("Junior", HTML)
        self.assertIn("personaLabel", HTML)
        self.assertIn("function performanceRatio", HTML)
        self.assertIn("actual/target", HTML)
        self.assertIn("score>100?'aboveReference'", HTML)
        self.assertNotIn("function closeness", HTML)
        self.assertIn("cameraWindows", HTML)
        self.assertIn('data-camera-window="impact"', HTML)
        self.assertIn("mediaUnavailable", HTML)
        self.assertIn("revealShotInTree", HTML)
        self.assertIn("scrollIntoView", HTML)
        self.assertIn("No sessions or shots are deleted", HTML)
        self.assertNotIn("c.style.width=w+'px'", HTML)
        self.assertNotIn("c.style.height=h+'px'", HTML)
        self.assertIn("grid-template-rows:repeat(2,minmax(0,1fr))", HTML)
        self.assertIn("text-align:center!important", HTML)

    def test_new_tree_interaction_contract(self):
        self.assertIn('data-session-head="${sess.id}"', HTML)
        self.assertIn('data-club-head="${esc(k)}"', HTML)
        self.assertGreaterEqual(HTML.count("addEventListener('dblclick'"), 2)
        self.assertIn("if(e.target.closest('button,a,input'))return", HTML)
        self.assertIn("clubSwatch", HTML)
        self.assertIn(".clubHead>.visibility{grid-column:5}", HTML)
        self.assertIn(".clubHead>.clubToggle{grid-column:6}", HTML)
        self.assertIn(".clubHead>*{align-self:center!important}", HTML)
        self.assertIn(".clubHead>.clubSwatch{grid-column:4;width:14px", HTML)
        self.assertIn("grid-template-columns:minmax(0,max-content) 22px minmax(4px,1fr) 16px 26px 26px", HTML)
        self.assertIn(".clubHead>b{font-size:14px!important}", HTML)
        self.assertIn(".treeToggle{width:32px;height:32px", HTML)
        self.assertIn(".clubToggle{width:30px!important;height:30px!important", HTML)
        self.assertIn("data-session-clubs", HTML)
        self.assertIn("all club groups", HTML)
        self.assertIn("keys.every(k=>state.closedClubs.has(k))", HTML)
        self.assertIn(".clubHead>.clubToggle{grid-column:6}", HTML)
        self.assertIn(".tree{scrollbar-gutter:stable}", HTML)
        self.assertIn("function bulkTreeIcon", HTML)
        self.assertIn('data-bulk-icon="expand-all"', HTML)
        self.assertIn('data-bulk-icon="collapse-all"', HTML)
        self.assertIn(".sessionClubs svg{display:block;width:16px;height:16px", HTML)
        self.assertIn(".sessionClubs:before,.sessionClubs:after{content:none!important}", HTML)
        self.assertIn(".sessionRename{width:32px;height:32px", HTML)
        self.assertIn(".sessionExport{height:32px", HTML)

    def test_shot_rows_share_one_grid_and_centered_action(self):
        self.assertIn(
            ".shot,.shot:nth-child(odd),.shot:nth-child(even){grid-template-columns:22px minmax(0,1fr) 24px!important}",
            HTML,
        )
        self.assertIn(
            ".shotColumns{grid-template-columns:22px minmax(0,1fr) 24px!important}",
            HTML,
        )
        self.assertIn(
            ".shotSelect{grid-template-columns:minmax(0,1.18fr) repeat(3,minmax(0,.82fr))!important}",
            HTML,
        )
        self.assertIn(".shotAction{display:grid;place-items:center", HTML)
        self.assertIn("box-shadow:-5px 0 currentColor,5px 0 currentColor", HTML)

    def test_primary_sections_are_resizable_and_persistent(self):
        self.assertIn("className='workspaceResizer'", HTML)
        self.assertIn("role','separator'", HTML)
        self.assertIn("Resize Sessions and Range", HTML)
        self.assertIn("Resize Range and Replay", HTML)
        self.assertIn("addEventListener('pointerdown'", HTML)
        self.assertIn("addEventListener('keydown'", HTML)
        self.assertIn("addEventListener('dblclick'", HTML)
        self.assertIn("vtrackWorkspaceSectionRatiosV1", HTML)
        self.assertIn("persistWorkspaceRatios", HTML)
        self.assertIn("visibility:hidden;pointer-events:none", HTML)
        self.assertIn("minmax(270px", HTML)
        self.assertIn("minmax(350px", HTML)
        self.assertIn("minmax(430px", HTML)
        self.assertIn("writing-mode:vertical-rl", HTML)
        self.assertIn("inset:46px 0 8px", HTML)
        self.assertIn("font-size:12px!important", HTML)

    def test_zoomable_range_and_axis_detail_contract(self):
        checkbox = re.search(r'<input id="axisDetails"[^>]*>', HTML)
        self.assertIsNotNone(checkbox)
        self.assertIn('type="checkbox"', checkbox.group(0))
        self.assertNotIn("checked", checkbox.group(0))
        self.assertIn("axisDetails:Boolean(prefs.axisDetails)", HTML)
        self.assertIn("RANGE_SCALES=[100,150,200,250,325,400,500]", HTML)
        self.assertIn('id="rangeZoomOut"', HTML)
        self.assertIn('id="rangeZoomIn"', HTML)
        self.assertIn('id="rangeZoomReset"', HTML)
        self.assertIn('class="rangeResetText">Reset</span>', HTML)
        self.assertIn('class="rangeZoomOverlay"', HTML)
        self.assertIn(".rangeZoomOverlay{position:absolute", HTML)
        self.assertIn("rangeDistanceMax:state.rangeDistanceMax", HTML)
        self.assertIn("rangePanDistance:+state.rangePanDistance.toFixed(2)", HTML)
        self.assertIn("rangePanSide:+state.rangePanSide.toFixed(2)", HTML)
        self.assertIn("RANGE_SIDE_MAX=90", HTML)
        self.assertIn("const distanceStep=state.axisDetails?10:25", HTML)
        self.assertIn("const lateralStep=state.axisDetails?5:10", HTML)
        self.assertIn("function rangeSize(svg)", HTML)
        self.assertIn("function rangeViewport()", HTML)
        self.assertIn("function rangePlotGeometry()", HTML)
        self.assertIn("function rangeSvgPoint", HTML)
        self.assertIn("getScreenCTM()", HTML)
        self.assertIn("function initRangeNavigation()", HTML)
        self.assertIn("function initRangeShotSelection()", HTML)
        self.assertIn("initRangeNavigation();initRangeShotSelection();", HTML)
        self.assertIn("function panRangeByPixels", HTML)
        self.assertIn("addEventListener('wheel'", HTML)
        self.assertIn("addEventListener('keydown'", HTML)
        self.assertIn("addEventListener('pointermove'", HTML)
        self.assertIn("touch-action:none;cursor:grab", HTML)
        self.assertIn('class="shotLayer" clip-path="url(#rangeClip)"', HTML)
        self.assertIn('class="dispersionLayer" pointer-events="none" clip-path="url(#rangeClip)"', HTML)
        self.assertIn('class="rangeWorldShape"', HTML)
        self.assertIn("px(RANGE_WORLD_DISTANCE_MAX*.55)", HTML)
        self.assertIn('class="shotLayer" clip-path="url(#puttingClip)"', HTML)
        self.assertIn("function clipFlightShots", HTML)
        self.assertIn("node.setAttribute('clip-path','url(#flightClip)')", HTML)
        self.assertIn('tabindex="0" role="application"', HTML)
        self.assertIn(".col.collapsed .rangeControls{display:none}", HTML)
        self.assertIn("TEE", HTML)
        self.assertIn("0 YD", HTML)
        self.assertIn("RANGE END", HTML)
        self.assertIn("${Math.round(distanceEnd)} YD", HTML)
        self.assertNotIn("Front range bunker", HTML)
        self.assertNotIn("Back range bunker", HTML)
        self.assertNotIn('id="rangeCount"', HTML)
        self.assertNotIn("$('rangeCount')", HTML)
        self.assertIn('class="distanceTick ${major?', HTML)
        self.assertIn('class="lateralTick ${important?', HTML)
        self.assertIn('font-size="${major?15:12}"', HTML)
        self.assertIn('font-size="${important?13:10}"', HTML)
        self.assertIn('class="rangeBoundaryLabel"', HTML)
        self.assertIn("function emptyRangeMessage", HTML)
        self.assertIn('class="emptyRangeMessage"', HTML)
        self.assertIn('fill-opacity=".88"', HTML)

    def test_all_visible_shots_and_clear_legend_contract(self):
        self.assertIn("function visibleRows()", HTML)
        self.assertIn("function selectedRows(){return visibleRows()}", HTML)
        self.assertNotIn("while(rows.length<limit)", HTML)
        self.assertIn("groups=rangeGroups(rows);rangeLegend(groups,putting)", HTML)
        self.assertIn("${rows.length} visible", HTML)
        self.assertIn(".legend{position:static!important", HTML)
        self.assertIn("flex-wrap:nowrap!important", HTML)
        self.assertIn("grid-template-rows:27px minmax(0,1fr)!important", HTML)

    def test_unchanged_range_render_is_cached(self):
        self.assertIn("rangeSig:''", HTML)
        self.assertIn("if(signature===state.rangeSig)return", HTML)
        self.assertIn("state.rangeSig=signature", HTML)
        self.assertIn("if(host._renderKey!==html)", HTML)

    def test_bounded_envelopes_and_clean_range_art_contract(self):
        self.assertIn("function boundedEnvelope(pts,bounds)", HTML)
        self.assertIn("function median(values)", HTML)
        self.assertIn("coverageScale=Math.max(1,farthest)*1.06", HTML)
        self.assertIn('data-envelope-coverage="all"', HTML)
        self.assertIn("let xx=0,yy=0,xy=0", HTML)
        self.assertIn("data-envelope-core", HTML)
        self.assertIn("type:'ellipse'", HTML)
        self.assertNotIn("type:'hull'", HTML)
        self.assertNotIn("function ellipsePath(e)", HTML)
        self.assertNotIn("data-envelope-power", HTML)
        self.assertIn('<ellipse data-envelope="${esc(c)}"', HTML)
        self.assertNotIn("fill=\"#f1db70\"", HTML)

    def test_shot_list_typography_scales_with_section_width(self):
        self.assertIn("@container sessiontree (min-width:360px)", HTML)
        self.assertIn("@container sessiontree (min-width:480px)", HTML)
        self.assertIn(".shotIdentity b{font-size:13px!important}", HTML)
        self.assertIn(".shotMetric b{font-size:14px!important}", HTML)

    def test_full_session_names_and_heat_compositing_contract(self):
        self.assertIn(".sessionHead{display:grid!important", HTML)
        self.assertIn("white-space:normal!important", HTML)
        self.assertIn("overflow-wrap:anywhere", HTML)
        self.assertIn(".faceStage canvas{z-index:3!important;mix-blend-mode:normal}", HTML)
        heat = re.search(r"function drawHeat\(\)\{(.+?)function media", HTML, re.DOTALL)
        self.assertIsNotNone(heat)
        density = heat.group(1).split("drawFaceCenter", 1)[0]
        self.assertIn("heat.globalCompositeOperation='destination-in'", density)
        self.assertIn("heat.filter=`blur(", density)
        self.assertIn("traceFace(heat,fr)", density)
        self.assertIn("wood:{x:.16,y:.40,w:.69,h:.33", HTML)
        self.assertIn("hybrid:{x:.18,y:.41,w:.65,h:.30", HTML)
        self.assertIn("FACE_LIMIT_MM={driver:{w:105,h:58},wood:{w:92,h:46}", HTML)
        self.assertIn("FACE_MM={driver:{w:105,h:58},wood:{w:128,h:64}", HTML)

    def test_club_faces_are_local_and_consistent_assets(self):
        for kind in ("driver", "wood", "hybrid", "iron", "putter"):
            self.assertIn(f"{kind}:'/assets/club-face-{kind}.png'", HTML)
        self.assertNotIn("taylormadegolf.com", HTML)
        self.assertNotIn("pgatoursuperstore.com", HTML)
        self.assertIn("filter:none!important", HTML)

    def test_putter_ui_and_face_contract(self):
        self.assertIn("function isPutter(c)", HTML)
        self.assertIn("PUTTING_DISTANCE_MAX_FT=90", HTML)
        self.assertIn("PUTTING_SIDE_MAX_FT=30", HTML)
        self.assertIn("isPutter(s.club)===putting", HTML)
        self.assertIn("data-putt-path", HTML)
        self.assertIn("data-putt-envelope", HTML)
        self.assertIn("puttingHole", HTML)
        self.assertIn("ROLL DISTANCE (FT) · AUTO", HTML)
        self.assertIn("BREAK / OFFLINE (FT)", HTML)
        self.assertIn("putter:{x:.04,y:.51,w:.92,h:.42", HTML)
        self.assertIn("putter:{w:110,h:28}", HTML)
        asset = Path(__file__).resolve().parents[1] / "assets" / "club-face-putter.png"
        png = asset.read_bytes()
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertIn(png[25], (4, 6), "putter PNG must have an alpha channel")

    def test_selected_strike_marker_is_not_face_clipped(self):
        selected = re.search(
            r"if\(validImpact\(s,kind\)\)\{(.+?)\}const hm=", HTML, re.DOTALL
        )
        self.assertIsNotNone(selected)
        self.assertIn("ctx.arc(x,y,ballR", selected.group(1))
        self.assertNotIn("traceFace", selected.group(1))
        self.assertNotIn("ctx.clip", selected.group(1))

    def test_report_dispersion_encloses_every_point(self):
        rows = [
            {"club": "I7", "gspro_carry_yards": 150, "side_yards": -12},
            {"club": "I7", "gspro_carry_yards": 155, "side_yards": 4},
            {"club": "I7", "gspro_carry_yards": 190, "side_yards": 18},
        ]
        svg = self.store.report_range_svg(rows)
        ellipse = re.search(
            r'<ellipse cx="([\d.]+)" cy="([\d.]+)" rx="([\d.]+)" ry="([\d.]+)"[^>]+stroke="#0072B2"',
            svg,
        )
        self.assertIsNotNone(ellipse)
        cx, cy, rx, ry = map(float, ellipse.groups())
        points = [
            tuple(map(float, match))
            for match in re.findall(
                r'<circle cx="([\d.]+)" cy="([\d.]+)" r="4"', svg
            )
        ]
        self.assertEqual(len(points), len(rows))
        for x, y in points:
            self.assertLessEqual(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2, 1.01)

    def test_session_report_includes_coaching_metrics(self):
        session_id = self.store.create_session("Report test")
        with self.store.connect() as cx:
            cx.execute(
                "INSERT INTO shots(id, shot_time, club, session_id) VALUES(1, ?, ?, ?)",
                ("2026-08-30T12:00:00", "I7", session_id),
            )
            cx.commit()
        report = self.store.report_html(session_id)
        self.assertIn("Carry consistency", report)
        self.assertIn("Lateral consistency", report)
        self.assertIn("Launch H°", report)
        self.assertIn("Impact X", report)
        self.assertIn("Download full-resolution CSV", report)
        self.assertIn('class="reportSheet"', report)
        self.assertIn('class="coachNotes"', report)
        self.assertIn('class="detailTitle"', report)

    def test_club_aliases_share_readable_report_names(self):
        self.assertEqual(shot_review.canonical_club("7i"), "I7")
        self.assertEqual(shot_review.canonical_club("3w"), "W3")
        self.assertEqual(shot_review.canonical_club("putter"), "PT")
        self.assertEqual(shot_review.display_club("I7"), "7 Iron")
        self.assertEqual(shot_review.display_club("W3"), "3 Wood")
        self.assertEqual(shot_review.display_club("PT"), "Putter")

    def test_putter_report_uses_feet_green_paths_and_hole(self):
        rows = [
            {"id": 1, "club": "PT", "total_distance_yards": 4.0, "side_yards": -0.2, "distance_to_target": 4.1},
            {"id": 2, "club": "PUTTER", "total_distance_yards": 4.3, "side_yards": 0.15, "distance_to_target": 4.1},
        ]
        svg = self.store.report_putting_svg(rows)
        self.assertIn("Putting green with hole", svg)
        self.assertIn("Hole · 12.3 ft", svg)
        self.assertIn("Putter · 2 · feet", svg)
        self.assertEqual(svg.count("<path d="), 3)  # flag plus two roll paths
        self.assertEqual(self.store.report_range_svg(rows), "")

    def test_shot_pages_cover_archives_beyond_old_5000_cap(self):
        session_id = self.store.create_session("Large archive")
        with self.store.connect() as connection:
            connection.executemany(
                "INSERT INTO shots(shot_time,club,session_id) VALUES(?,?,?)",
                [(f"2026-09-01T12:{i//60:02d}:{i%60:02d}", "I7", session_id) for i in range(5105)],
            )
            connection.commit()
        rows = []
        before = None
        while True:
            page = self.store.list_shots(before_id=before, limit=1000)
            rows.extend(page)
            if len(page) < 1000:
                break
            before = page[-1]["id"]
        self.assertEqual(len(rows), 5105)
        self.assertEqual(len({row["id"] for row in rows}), 5105)

    def test_manual_reclassification_enforces_shared_canonical_club_codes(self):
        original = self.store.create_session("Original")
        with self.store.connect() as connection:
            shot_id = connection.execute(
                "INSERT INTO shots(shot_time,club,session_id) VALUES(?,?,?)",
                ("2026-08-31T10:00:00", "I7", original),
            ).lastrowid
            connection.commit()
        changed, error = self.store.update_shot(shot_id, "3 Wood", original)
        self.assertTrue(changed)
        self.assertIsNone(error)
        self.assertEqual(self.store.get_shot(shot_id)["club"], "W3")
        changed, error = self.store.update_shot(shot_id, "laser cannon", original)
        self.assertFalse(changed)
        self.assertIn("supported club", error)

    def test_report_dispersion_falls_back_to_vtrack_carry(self):
        svg = self.store.report_range_svg([
            {"club": "I7", "side_yards": 2.0, "gspro_carry_yards": None, "vtrack_carry_yards": 151.5}
        ])
        self.assertIn("7 Iron", svg)
        self.assertIn("circle", svg)

    def test_cross_origin_mutation_is_rejected_before_side_effect(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.store))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/sessions",
                data=json.dumps({"name": "evil"}).encode(),
                headers={"Content-Type": "application/json", "Origin": "https://evil.example"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(request, timeout=2)
            self.assertEqual(raised.exception.code, 403)
            self.assertFalse(any(row["name"] == "evil" for row in self.store.sessions()))
        finally:
            server.shutdown();server.server_close();worker.join(timeout=2)

    def test_media_range_parsing_handles_suffix_and_invalid_ranges(self):
        media = Path(self.tempdir.name) / "sample.mp4"
        media.write_bytes(b"0123456789")
        session_id = self.store.create_session("Media")
        with self.store.connect() as connection:
            connection.execute("ALTER TABLE shots ADD COLUMN replay_video_path TEXT")
            shot_id = connection.execute(
                "INSERT INTO shots(shot_time,club,session_id,replay_video_path) VALUES(?,?,?,?)",
                ("2026-09-02T12:00:00", "I7", session_id, str(media)),
            ).lastrowid
            connection.commit()
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.store))
        worker = threading.Thread(target=server.serve_forever, daemon=True);worker.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/media/{shot_id}/impact",
                headers={"Range": "bytes=-4"},
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                self.assertEqual(response.status, 206)
                self.assertEqual(response.read(), b"6789")
                self.assertEqual(response.headers["Content-Range"], "bytes 6-9/10")
            bad = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/media/{shot_id}/impact",
                headers={"Range": "bytes=999-1000"},
            )
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(bad, timeout=2)
            self.assertEqual(raised.exception.code, 416)
        finally:
            server.shutdown();server.server_close();worker.join(timeout=2)

    def test_reference_benchmark_is_explicitly_directional_and_non_official(self):
        self.assertIn("Internal directional reference model", HTML)
        self.assertIn("not an official handicap", HTML)
        self.assertIn("How the score works", HTML)
        self.assertIn("Distance and speed use your average divided by the reference target", HTML)
        self.assertIn("Profile targets and multipliers are app-defined practice references", HTML)

    def test_embedded_ui_has_no_overridden_named_function_declarations(self):
        names = re.findall(r"\b(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", HTML)
        duplicates = sorted({name for name in names if names.count(name) > 1})
        self.assertEqual(duplicates, [])
        self.assertNotIn("legacyRenderTree", HTML)


if __name__ == "__main__":
    unittest.main()
