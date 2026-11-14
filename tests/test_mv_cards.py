"""Simple picture cards (app/mvstudio/cards.py and the MV page's button): drawn only into the parts of the
timeline that show no photo, never over a photo, all in one tone, and taken out again without touching the
photos or the timeline."""
import io

from PIL import Image

from app.mvstudio import cards, core
from test_mv_photos import _aligned_project, png, state


def test_pick_follows_the_words_and_never_repeats_side_by_side():
    lines = [("intro", "～ 前奏 ～"), ("lyric", "雨落在窗外的小巷"), ("lyric", "追著夜空的流星"), ("lyric", "追著夜空的流星"),
             ("interlude", "～ 間奏 ～"), ("lyric", "你是我的幸運"), ("lyric", "la la la"), ("lyric", "oh oh oh"),
             ("lyric", "追著夜空的流星"), ("outro", "～ 尾奏 ～")]
    got = cards.pick(lines)
    assert got[0] == ("opening", 0) and got[-1] == ("ending", 0)
    assert got[1][0] == "rain_meadow" and got[2] == ("shooting_star", 0) and got[5][0] == "clover"
    assert got[3][0] != "shooting_star"                      # the same line again right after: another scene
    assert got[8] == ("shooting_star", 1)                    # later again: the same scene in its other look
    assert got[4][0] in cards.GENERAL and got[6][0] in cards.GENERAL and got[7][0] in cards.GENERAL
    assert all(a[0] != b[0] for a, b in zip(got, got[1:]))
    assert cards.pick(lines) == got
    # Simplified lines find the same scenes; a song with no known word still changes scene on every line
    assert cards.pick([("lyric", "追着夜空的流星"), ("lyric", "眼泪悄悄落下")]) == [("shooting_star", 0), ("tear_dusk", 0)]
    plain = cards.pick([("lyric", "na na na")] * 30)
    assert all(a[0] != b[0] for a, b in zip(plain, plain[1:])) and {n for n, _ in plain} == set(cards.GENERAL)
    assert {s for _, scs in cards.WORDS for s in scs} | set(cards.GENERAL) | {"opening", "ending"} <= set(cards.SCENES)


def test_every_scene_draws_in_both_looks_and_every_tone():
    def raw(im):
        return im.tobytes()
    for name in cards.SCENES:
        a = cards.draw(name, 0)
        assert a.size == (1920, 1080) and a.mode == "RGB", name
        assert len(set(a.resize((48, 27)).getdata())) > 20, name          # a picture, not a flat colour
    for name in ("smile_tear", "bike_road"):                              # own second look / mirrored
        assert raw(cards.draw(name, 0)) != raw(cards.draw(name, 1))
    a = cards.draw("sea", 0)
    assert raw(a) == raw(cards.draw("sea", 0))
    tones = {t: cards.draw("sea", 0, t) for t in cards.TONES}
    assert len({raw(im) for im in tones.values()}) == len(cards.TONES)
    assert all(r == g == b for r, g, b in tones["manga"].resize((32, 18)).getdata())
    for bad in (("nothing", 0, "fresh"), ("sea", 0, "sepia")):
        try:
            cards.draw(*bad)
        except KeyError:
            continue
        raise AssertionError(bad)


def _post(client, path, **body):
    return client.post(path, json=body)


def _middle(path):
    with Image.open(path) as im:
        return im.convert("RGB").getpixel((960, 300))


def test_cards_fill_only_the_empty_parts(client, root):
    sid, slug, pdir = _aligned_project(client, root)
    scenes = pdir / "scenes"
    tl = core.load_project_dict(slug)["timeline"]
    lyric_scenes = sorted({int(s["scene"]) for s in tl if not core.instrumental_key(s)})
    # a photo of the user's on one line, before anything is drawn
    mine = lyric_scenes[1]
    assert client.post("/api/mv/upload_scene", data={"slug": slug, "scene_id": str(mine)},
                       files={"file": ("a.png", png("red"), "image/png")}).json()["status"] == "ok"
    plan = _post(client, "/api/mv/cards/plan", slug=slug).json()
    slots = [e["slot"] for e in plan["empty"]]
    assert plan["tone"] == "fresh" and plan["cards"] == [] and plan["timeline"] == len(tl)
    assert f"scene:{mine}" not in slots and len(slots) == len(set(slots))
    assert set(slots) >= {f"scene:{n}" for n in lyric_scenes if n != mine}
    intro = next((s for s in tl if s.get("type") == "intro"), None)
    if intro:   # the intro borrows line 1's photo; with none there it gets a card of its own
        assert "inst:intro" in slots and next(e for e in plan["empty"] if e["slot"] == "inst:intro")["card"] == "opening"
    names = [e["card"] for e in plan["empty"]]
    assert all(n in cards.SCENES for n in names)

    # a slot with a photo is refused; so are a made-up slot and a made-up tone
    assert _post(client, "/api/mv/cards/draw", slug=slug, slot=f"scene:{mine}", tone="fresh").status_code == 409
    assert _post(client, "/api/mv/cards/draw", slug=slug, slot="scene:../x", tone="fresh").status_code == 400
    assert _post(client, "/api/mv/cards/draw", slug=slug, slot=slots[0], tone="sepia").status_code == 400
    assert _post(client, "/api/mv/cards/draw", slug="nope/none", slot=slots[0], tone="fresh").status_code == 404

    for slot in slots:
        res = _post(client, "/api/mv/cards/draw", slug=slug, slot=slot, tone="fresh")
        assert res.status_code == 200, res.text
    done = _post(client, "/api/mv/cards/done", slug=slug).json()
    assert done["empty"] == [] and sorted(c["slot"] for c in done["cards"]) == sorted(slots)
    assert all(c["tone"] == "fresh" for c in done["cards"])
    data, shown = state(client, slug)
    assert set(shown) >= set(lyric_scenes) and data["not_imported"]["waiting"] == 0     # they count as photos from the page
    assert _middle(scenes / f"scene_{mine:02d}.png") == (255, 0, 0)                      # the user's photo is as it was
    proj = core.load_project_dict(slug)
    assert all(core.seg_photo_path(proj, s) for s in proj["timeline"])
    # pressing again finds nothing to do and draws nothing twice
    assert _post(client, "/api/mv/cards/draw", slug=slug, slot=slots[0], tone="fresh").status_code == 409

    # another tone for the whole song: the cards are drawn again, the photo is not
    first = scenes / f"scene_{lyric_scenes[0]:02d}.png"
    before = first.read_bytes()
    assert _post(client, "/api/mv/cards/draw", slug=slug, slot=f"scene:{mine}", tone="night", redraw=True).status_code == 409
    for c in done["cards"]:
        assert _post(client, "/api/mv/cards/draw", slug=slug, slot=c["slot"], tone="night", redraw=True).status_code == 200
    after = _post(client, "/api/mv/cards/plan", slug=slug).json()
    assert after["tone"] == "night" and {c["tone"] for c in after["cards"]} == {"night"} and len(after["cards"]) == len(slots)
    assert first.read_bytes() != before and _middle(scenes / f"scene_{mine:02d}.png") == (255, 0, 0)
    assert [(c["slot"], c["card"], c["look"]) for c in after["cards"]] == [(c["slot"], c["card"], c["look"]) for c in done["cards"]]

    # the user puts a photo over one card: it is a photo from then on
    over = lyric_scenes[0]
    assert client.post("/api/mv/upload_scene", data={"slug": slug, "scene_id": str(over)},
                       files={"file": ("b.png", png("blue"), "image/png")}).json()["status"] == "ok"
    now = _post(client, "/api/mv/cards/plan", slug=slug).json()
    assert f"scene:{over}" not in [c["slot"] for c in now["cards"]] and len(now["cards"]) == len(slots) - 1
    assert _post(client, "/api/mv/cards/draw", slug=slug, slot=f"scene:{over}", tone="night", redraw=True).status_code == 409

    # taking the cards out leaves both photos and the timeline
    gone = _post(client, "/api/mv/cards/remove", slug=slug).json()
    assert gone["status"] == "ok" and gone["removed"] == len(slots) - 1 and gone["instrument_photos"] == {}
    assert sorted(s["scene_id"] for s in gone["all_scenes"] if s.get("exists")) == sorted([mine, over])
    assert _middle(scenes / f"scene_{mine:02d}.png") == (255, 0, 0) and _middle(scenes / f"scene_{over:02d}.png") == (0, 0, 255)
    assert core.load_project_dict(slug)["timeline"] == tl
    again = _post(client, "/api/mv/cards/plan", slug=slug).json()
    # the intro borrows line 1, which now has the user's photo: it shows that and needs no card
    assert again["cards"] == [] and again["tone"] == "night"
    assert {e["slot"] for e in again["empty"]} == set(slots) - {f"scene:{over}", "inst:intro"}
    assert _post(client, "/api/mv/cards/remove", slug=slug).json()["removed"] == 0


def test_one_card_taken_out_comes_back_the_same_and_no_timeline_means_nothing_to_draw(client, root):
    sid, slug, pdir = _aligned_project(client, root)
    plan = _post(client, "/api/mv/cards/plan", slug=slug).json()
    for e in plan["empty"]:
        assert _post(client, "/api/mv/cards/draw", slug=slug, slot=e["slot"], tone="warm").status_code == 200
    target = next(e for e in plan["empty"] if e["slot"].startswith("scene:"))
    sid_n = int(target["slot"].split(":")[1])
    (pdir / "scenes" / f"scene_{sid_n:02d}.png").unlink()     # an empty slot among the cards
    left = _post(client, "/api/mv/cards/plan", slug=slug).json()
    assert [(e["slot"], e["card"], e["look"]) for e in left["empty"]] == [(target["slot"], target["card"], target["look"])]
    assert left["tone"] == "warm"

    # a project that has not been aligned has no parts to draw for
    slug2 = client.post("/api/mv/project/create", json={"song_id": sid, "slug": "bare", "title": "t", "scene_count": 3}).json()["project"]["slug"]
    bare = _post(client, "/api/mv/cards/plan", slug=slug2).json()
    assert bare["empty"] == [] and bare["timeline"] == 0
