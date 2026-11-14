"""Simple picture cards (app/mvstudio/cards.py and the MV page's button): drawn only into the parts of the
timeline that show no photo, never over a photo, all in one tone, and taken out again without touching the
photos or the timeline."""
import io

from PIL import Image

from app.mvstudio import cards, cardworld, core
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


def test_a_song_has_a_look_of_its_own():
    a, b = cards.song_seed("song_a_demo"), cards.song_seed("song_b_demo")
    assert a and b and a != b and cards.song_style(0) == cards.PLAIN
    for name in ("blossom_meet", "sea", "classroom_heart"):
        plain, one, two = cards.draw(name), cards.draw(name, 0, "fresh", a), cards.draw(name, 0, "fresh", b)
        assert len({plain.tobytes(), one.tobytes(), two.tobytes()}) == 3, name
        assert one.tobytes() == cards.draw(name, 0, "fresh", a).tobytes()
        assert one.tobytes() != cards.draw(name, 1, "fresh", a).tobytes()
    # the lines without a known word do not show the same landscapes in every song
    plain = [("lyric", "na na na")] * 40
    sets = [frozenset(n for n, _ in cards.pick(plain, cards.song_seed(f"song{i}"))) for i in range(12)]
    assert all(len(st) == cards.GENERAL_USED for st in sets) and len(set(sets)) > 6
    for i in range(12):
        got = cards.pick(plain + [("lyric", "雨落在窗外的小巷"), ("lyric", "雨落在窗外的小巷")], cards.song_seed(f"song{i}"))
        assert all(x[0] != y[0] for x, y in zip(got, got[1:])) and got == cards.pick(plain + [("lyric", "雨落在窗外的小巷")] * 2, cards.song_seed(f"song{i}"))
        assert {got[-1][0], got[-2][0]} <= {"rain_meadow", "rain_together", "umbrella_wait", "window_rain", "window_quiet"}
    assert cards.pick(plain, 0) == cards.pick(plain)
    # a line sung many times: four pictures before one comes back, and never two the same side by side
    seed = cards.song_seed("song_a_demo")
    many = cards.pick([("lyric", "追著夜空的流星"), ("lyric", "na na na")] * 5, seed)
    stars = [x for x in many if x[0] == "shooting_star"]
    assert [look for _, look in stars] == [0, 1, 2, 3, 0]
    assert len({cards.draw("shooting_star", look, "fresh", seed).tobytes() for look in range(4)}) == 4
    assert len({cards.draw("bike_road", look, "fresh", seed).tobytes() for look in range(4)}) == 4
    # 妳 counts as 你, and the 星 of a weekday is no star
    assert cards.pick([("lyric", "如何的想妳")])[0][0] in ("window_quiet", "letter")
    assert cards.pick([("lyric", "星期天的下午")])[0][0] in cards.GENERAL


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
    if intro:   # the intro borrows line 1's photo; with none there it gets a card of its own (no people in it)
        assert "inst:intro" in slots and cardworld.parse(next(e for e in plan["empty"] if e["slot"] == "inst:intro")["card"])[3] == "none"
    names = [e["card"] for e in plan["empty"]]
    assert all(cardworld.parse(n) for n in names) and len(set(names)) == len(names) and cardworld.valid_world(plan["world"])

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

    # the song's look stays while its cards are there, and is the one its name gives
    import json
    rec = json.loads((pdir / "cards.json").read_text(encoding="utf-8"))
    seed = cards.song_seed(slug)
    assert rec["seed"] == seed and left["seed"] == seed and rec["tone"] == "warm"
    assert rec["world"] == plan["world"] == left["world"] and cardworld.valid_world(rec["world"])
    other = next(e for e in plan["empty"] if e["slot"].startswith("scene:") and e["slot"] != target["slot"])
    with Image.open(pdir / "scenes" / ("scene_%02d.png" % int(other["slot"].split(":")[1]))) as im:
        assert im.convert("RGB").tobytes() == cards.draw(other["card"], other["look"], "warm", seed, rec["world"]).tobytes()
    # the library remembers the song's world for the songs after it
    hist = cards.read_history(root / "library")
    assert [h["slug"] for h in hist] == [slug] and hist[0]["world"] == rec["world"]
    # cards from before songs had worlds keep the first cards' scenes for what is added to them
    rec.pop("seed"); rec.pop("world")
    for v in rec["cards"].values():
        v["card"], v["look"] = "sea", 0
    (pdir / "cards.json").write_text(json.dumps(rec), encoding="utf-8")
    old = _post(client, "/api/mv/cards/plan", slug=slug).json()
    assert old["seed"] == 0 and old["world"] is None and len(old["empty"]) == 1 and old["empty"][0]["card"] in cards.SCENES
    assert _post(client, "/api/mv/cards/draw", slug=slug, slot=old["empty"][0]["slot"], tone="warm").status_code == 200
    with Image.open(pdir / "scenes" / f"scene_{sid_n:02d}.png") as im:
        assert im.convert("RGB").tobytes() == cards.draw(old["empty"][0]["card"], old["empty"][0]["look"], "warm", 0).tobytes()
    assert json.loads((pdir / "cards.json").read_text(encoding="utf-8"))["seed"] == 0
    # taken out and made again: the song's own look
    assert _post(client, "/api/mv/cards/remove", slug=slug).json()["removed"] == len(plan["empty"])
    anew = _post(client, "/api/mv/cards/plan", slug=slug).json()
    assert anew["round"] == 1 and anew["seed"] == cards.song_seed(slug + "#1") and cardworld.valid_world(anew["world"])
    assert anew["world"] != plan["world"] and len(anew["empty"]) == len(plan["empty"])

    # a project that has not been aligned has no parts to draw for
    slug2 = client.post("/api/mv/project/create", json={"song_id": sid, "slug": "bare", "title": "t", "scene_count": 3}).json()["project"]["slug"]
    bare = _post(client, "/api/mv/cards/plan", slug=slug2).json()
    assert bare["empty"] == [] and bare["timeline"] == 0


def test_worlds_keep_away_from_the_songs_before_and_cards_never_repeat():
    lines = [("intro", "")] + [("lyric", t) for t in ("雨落在窗外的小巷", "追著夜空的流星", "na na na", "你是我的幸運", "一起對抗全世界",
                                                      "hold my hand tonight", "追著夜空的流星", "na na na")] * 6 + [("outro", "")]
    recent = []
    for i in range(8):
        seed = cards.song_seed(f"song{i}")
        wd = cardworld.choose_world(seed, recent)
        assert cardworld.valid_world(wd) and wd == cardworld.choose_world(seed, recent)
        if recent:      # at most two places shared with the song just before, and never its whole look
            assert len(set(wd["places"]) & set(recent[-1]["places"])) <= 2, (i, wd["places"], recent[-1]["places"])
            assert cardworld.world_distance(wd, recent[-1]) > 12
        specs = cardworld.plan(lines, seed, wd)
        assert len(specs) == len(lines) and len(set(specs)) == len(specs) and all(cardworld.parse(sp) for sp in specs)
        assert specs == cardworld.plan(lines, seed, wd)
        got = [cardworld.parse(sp) for sp in specs]
        assert got[1][2] == "rain" and got[2][1] == "night" and got[2][4] == "shooting" and got[4][4] == "clover"
        assert got[6][1] == "night" and got[6][3] == "duo_hands"          # English words count too
        recent.append(wd)
    assert not cardworld.parse("w2|sea|day|clear|none|none|wide|c|x") and not cardworld.parse("sea") and not cardworld.valid_world({"v": 2})


def test_every_place_person_and_thing_draws():
    wd = cardworld.make_world(3)
    seen = set()
    for i, place in enumerate(cardworld.PLACES):
        im = cardworld.draw(cardworld.card(place, list(cardworld.LIGHTS)[i % 7], cardworld.WEATHERS[i % 3], "none", "none", "wide", "c", 0), wd, 5)
        assert im.size == (1920, 1080) and im.mode == "RGB" and len(set(im.resize((48, 27)).getdata())) > 20, place
        seen.add(im.resize((32, 18)).tobytes())
    assert len(seen) == len(cardworld.PLACES)
    for i, subject in enumerate(cardworld.SUBJECTS):
        for wd2 in (wd, cardworld.make_world(40 + i)):
            cardworld.draw(cardworld.card("park", "day", "clear", subject, "none", cardworld.FRAMES[i % 3], cardworld.POSES[i % 3], i % 2), wd2, 5)
    for i, prop in enumerate(cardworld.PROPS):
        for subject in ("solo_front", "duo_face", "none"):
            cardworld.draw(cardworld.card("meadow", "night" if i % 2 else "day", "clear", subject, prop, "mid", "c", 0), wd, 5)
    a = cardworld.card("sea", "sunset", "clear", "solo_back", "birds", "mid", "l", 0)
    assert cardworld.draw(a, wd, 5).tobytes() == cardworld.draw(a, wd, 5).tobytes()
    assert cardworld.draw(a, wd, 5).tobytes() != cardworld.draw(a, cardworld.make_world(4), 5).tobytes()
    assert cards.draw(a, 0, "manga", 5, wd).size == (1920, 1080) and cards.valid_card(a) and cards.valid_card("sea") and not cards.valid_card("x")
