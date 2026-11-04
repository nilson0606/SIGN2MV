"""MV photo slots: the photo count sees every slot up to MAX_SCENES (no engine needed)."""
from __future__ import annotations

from app.mvstudio import core


def test_count_existing_scene_images_up_to_max(tmp_path):
    (tmp_path / "scene_05.png").write_bytes(b"x")
    assert core.count_existing_scene_images(str(tmp_path)) == 5
    (tmp_path / "scene_40.png").write_bytes(b"x")          # past the old 36-photo limit
    assert core.count_existing_scene_images(str(tmp_path)) == 40
    (tmp_path / f"scene_{core.MAX_SCENES:02d}_beach.jpg").write_bytes(b"x")
    assert core.count_existing_scene_images(str(tmp_path)) == core.MAX_SCENES
    assert core.count_existing_scene_images(str(tmp_path / "missing")) == 0
