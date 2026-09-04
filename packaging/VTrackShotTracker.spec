# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

project_root = Path(SPEC).resolve().parent.parent
ffmpeg = os.environ.get("VTRACK_FFMPEG")
binaries = []
if ffmpeg:
    ffmpeg_path = Path(ffmpeg).resolve()
    if not ffmpeg_path.is_file():
        raise SystemExit(f"VTRACK_FFMPEG does not point to a file: {ffmpeg_path}")
    binaries.append((str(ffmpeg_path), "."))

a = Analysis(
    [str(project_root / "vtrack_shot_tracker.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=[
        (str(project_root / "LICENSE"), "."),
        (str(project_root / "THIRD_PARTY_NOTICES.md"), "."),
        (str(project_root / "assets"), "assets"),
    ],
    hiddenimports=[
        "collector.vtrack_shot_collector",
        "review.shot_review",
        "vtrack_desktop",
        "webview",
        "clr",
    ],
    excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "cefpython3", "gi"],
)

# pywebview ships an Android runtime JAR that is not used by the Windows
# desktop build. Excluding it also prevents the portable packaging step from
# tripping over the JAR if another process has opened it.
a.datas = [
    item
    for item in a.datas
    if not item[0].replace("\\", "/").lower().endswith(
        "webview/lib/pywebview-android.jar"
    )
]

pyz = PYZ(a.pure)
gui_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VTrackShotTracker",
    icon=str(project_root / "assets" / "vtrack-app-icon.ico"),
    console=False,
    contents_directory=".",
)
cli_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VTrackShotTrackerCLI",
    icon=str(project_root / "assets" / "vtrack-app-icon.ico"),
    console=True,
    contents_directory=".",
)
coll = COLLECT(
    gui_exe,
    cli_exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="VTrackShotTracker",
)
