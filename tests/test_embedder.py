"""The feature model ("embedder") a voice model was trained with is read from the .pth and used to convert."""
from __future__ import annotations

import pickle
import zipfile
from pathlib import Path

from app import cover


def fake_pth(path: Path, embedder: str | None) -> Path:
    """A .pth laid out like torch.save (a zip with <name>/data.pkl)."""
    data = {"weight": {}, "config": [1025, 32], "f0": 1, "version": "v2", "speakers_id": 0}
    if embedder is not None:
        data["embedder_model"] = embedder
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(f"{path.stem}/data.pkl", pickle.dumps(data, protocol=2))
        z.writestr(f"{path.stem}/version", "3\n")
    return path


def test_pth_embedder(tmp_path):
    assert cover.pth_embedder(fake_pth(tmp_path / "a.pth", "chinese-hubert-base")) == "chinese-hubert-base"
    assert cover.pth_embedder(fake_pth(tmp_path / "b.pth", "contentvec")) == "contentvec"
    assert cover.pth_embedder(fake_pth(tmp_path / "c.pth", None)) == "contentvec"        # older models
    assert cover.pth_embedder(fake_pth(tmp_path / "d.pth", "spin")) == "spin"            # passed through
    (tmp_path / "e.pth").write_bytes(b"not a zip")
    assert cover.pth_embedder(tmp_path / "e.pth") == "contentvec"
    assert cover.pth_embedder(tmp_path / "missing.pth") == "contentvec"
    try:                                       # a real torch.save file, when torch is installed here
        import torch
    except ImportError:
        return
    torch.save({"weight": {"x": torch.zeros(2)}, "embedder_model": "chinese-hubert-base"}, tmp_path / "t.pth")
    assert cover.pth_embedder(tmp_path / "t.pth") == "chinese-hubert-base"


def test_models_and_conversion_carry_the_embedder(tmp_path):
    voices = tmp_path / "voices"
    fake_pth(voices / "Zh_1" / "Zh_1_30e.pth", "chinese-hubert-base")
    fake_pth(voices / "Zh_1" / "epochs" / "Zh_1_10e_100s.pth", "chinese-hubert-base")
    fake_pth(voices / "Cv_1" / "Cv_1_30e.pth", "contentvec")
    models = {m["name"]: m for m in cover.list_models(voices)}
    assert models["Zh_1"]["embedder"] == "chinese-hubert-base" and models["Cv_1"]["embedder"] == "contentvec"
    assert cover.resolve_model(voices, "Zh_1")["embedder"] == "chinese-hubert-base"
    assert cover.resolve_model(voices, "Zh_1__e10")["embedder"] == "chinese-hubert-base"

    song_dir = tmp_path / "song"
    (song_dir / "source").mkdir(parents=True)
    song = {"source": {"audio": "source/audio.wav", "source_hash": "abc"}}
    p = cover.clean_params({"model": "Zh_1"})
    pl = cover.plan(song_dir, song, p, lambda name: cover.resolve_model(voices, name))
    assert pl["rvc_tasks"] and all(t["embedder"] == "chinese-hubert-base" for t in pl["rvc_tasks"])


def test_train_request_keeps_only_known_embedders():
    assert cover.TRAIN_EMBEDDERS == ("contentvec", "chinese-hubert-base")
    assert set(cover.TRAIN_EMBEDDERS) <= set(cover.EMBEDDERS)
