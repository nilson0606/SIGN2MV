"""Each separation layer reports its own progress only (a demucs layer used to leak into the next one)."""
from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))

import tqdm  # noqa: E402

import separate  # noqa: E402


class Rec:
    def __init__(self, name: str, log: list):
        self.name, self.log = name, log

    def __call__(self, pct: float) -> None:
        self.log.append((self.name, round(pct)))

    def phase(self, sub: str) -> None:
        self.log.append((self.name, sub))


def test_layers_do_not_leak_into_each_other():
    original = tqdm.tqdm
    demucs_like = types.ModuleType("demucs_like")           # `import tqdm`, calls tqdm.tqdm(...)
    demucs_like.tqdm = tqdm
    roformer_like = types.ModuleType("roformer_like")       # `from tqdm import tqdm`
    roformer_like.tqdm = tqdm.tqdm
    log: list = []

    separate.patch_tqdm(demucs_like, Rec("separate", log))
    bar = demucs_like.tqdm.tqdm(total=4)        # the libraries' bars advance once per chunk
    for _ in range(4):
        bar.update(1)
    assert tqdm.tqdm is original                              # the shared module is never changed
    first = list(log)
    assert first and all(name == "separate" for name, _ in first)

    separate.patch_tqdm(roformer_like, Rec("lead", log))
    bar = roformer_like.tqdm(total=5)
    for _ in range(5):
        bar.update(1)
    second = log[len(first):]
    assert second and all(name == "lead" for name, _ in second), second   # was: separate, lead, separate, ...
    assert second[-1] == ("lead", "save")
