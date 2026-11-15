"""Simple picture cards (app/mvstudio/cards.py and the MV page's button): drawn only into the parts of the
timeline that show no photo, never over a photo, all in one tone, and taken out again without touching the
photos or the timeline."""
import io

from PIL import Image

from app.mvstudio import card_icons, cards, cardworld, core
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


def test_the_standard_grade_has_more_places_and_shots_and_leaves_the_simple_one_alone():
    simple = cardworld.make_world(9)
    assert "grade" not in simple and set(simple["places"]) <= set(cardworld.PLACES) and len(simple["places"]) == 5
    lines = [("intro", "")] + [("lyric", t) for t in ("雨落在窗外的小巷", "夕陽下我們牽著手", "na na na", "寫一封信給你", "向著夢想奔跑",
                                                      "咖啡店的午後", "擁抱著你", "追著夜空的流星", "la la la", "時間停在那一年")] * 4 + [("outro", "")]
    assert all(cardworld.parse(sp)[5] in cardworld.FRAMES for sp in cardworld.plan(lines, 5, simple))
    shots, places = set(), set()
    recent = []
    for i in range(6):
        seed = cards.song_seed(f"std{i}")
        wd = cardworld.choose_world(seed, recent, "standard")
        assert cardworld.valid_world(wd) and wd["grade"] == "standard" and len(wd["places"]) == 10
        assert sum(1 for p in wd["places"] if cardworld.composite(p)) == 6
        specs = cardworld.plan_standard(lines, seed, wd)
        assert len(set(specs)) == len(specs) == len(lines) and specs == cardworld.plan_standard(lines, seed, wd)
        got = [cardworld.parse(sp) for sp in specs]
        assert all(got) and got[0][5] not in cardworld.FRAMES_STD and got[-1][5] not in cardworld.FRAMES_STD
        assert got[6][0] == "cafe" and got[7][3] == "duo_hug" and got[5][3] == "solo_run" and got[5][4] == "dream"
        shots |= {g[5] for g in got}
        places |= {g[0] for g in got}
        recent.append(wd)
    assert shots >= set(cardworld.FRAMES_STD) and len(places) >= 30
    # every landmark stands somewhere, every element draws, and the words of a line can name them
    n = sum(1 for t in cardworld.TERRAINS for lm in cardworld.LANDMARKS if cardworld.fits(lm, t))
    assert n >= 350 and all(any(cardworld.fits(lm, t) for t in cardworld.TERRAINS) for lm in cardworld.LANDMARKS)
    wd0 = cardworld.make_world(8, "standard")
    said = cardworld.plan_standard([("lyric", "海邊的燈塔還亮著"), ("lyric", "摩天輪轉了一圈"), ("lyric", "把行李收好就出發"), ("lyric", "沙漠裡的一口井")], 3, wd0)
    got = [cardworld.parse(sp) for sp in said]
    assert got[0][0].split(".")[1] == "lighthouse" and got[1][0].split(".")[1] == "ferris" and got[2][4] == "suitcase"
    assert got[3][0].split(".")[:2] == ["dunes", "well"]
    for i, lm in enumerate(cardworld.LANDMARKS):
        t = next(t for t in cardworld.TERRAINS if cardworld.fits(lm, t))
        cardworld.draw(cardworld.card(f"{t}.{lm}.{cardworld.FRONTS[i % 9]}", list(cardworld.LIGHTS)[i % 7], "clear", "solo_back", "none", "wide", "c", 0), wd0, 5)
    for i, t in enumerate(cardworld.TERRAINS):
        cardworld.draw(cardworld.card(f"{t}.signpost.none", "night" if i % 2 else "day", "clear", "none", "none", "wide", "c", 0), wd0, 5)
    for i, prop in enumerate(cardworld.PROPS_STD):
        for subject in ("solo_front", "duo_face", "none"):
            cardworld.draw(cardworld.card("grass.bigtree.grass", "day", "clear", subject, prop, "mid", "lr"[i % 2], 0), wd0, 5)
    assert not cardworld.parse("w2|grass.nothing.none|day|clear|none|none|wide|c|0") and cardworld.valid_place("coast.lighthouse.rocks")
    wd = cardworld.make_world(3, "standard")
    for i, place in enumerate(cardworld.PLACES_STD):
        im = cardworld.draw(cardworld.card(place, list(cardworld.LIGHTS)[i % 7], "clear", cardworld.SUBJECTS_STD[i % 2], "none", "mid", "c", 0), wd, 5)
        assert im.size == (1920, 1080) and im.mode == "RGB" and len(set(im.resize((48, 27)).getdata())) > 20, place
    for i, shot in enumerate(cardworld.FRAMES_STD):
        for prop in ("none", "letter", "hearts", "clock", "frames", "thread"):
            cardworld.draw(cardworld.card("sea", "sunset", "clear", "duo_hands" if i % 2 else "solo_front", prop, shot, "c", i), wd, 5)
    a = cardworld.card("sea", "sunset", "clear", "duo_hands", "none", "sil", "c", 0)
    assert cardworld.draw(a, wd, 5).tobytes() == cardworld.draw(a, wd, 5).tobytes()
    assert cardworld.draw(a, simple, 5).size == (1920, 1080)      # a simple world draws such a card as a plain one


def test_the_page_can_ask_for_the_standard_grade_and_change_between_the_two(client, root):
    sid, slug, pdir = _aligned_project(client, root)
    plan = _post(client, "/api/mv/cards/plan", slug=slug, grade="standard").json()
    assert plan["grade"] == "standard" and plan["world"]["grade"] == "standard" and plan["cards"] == []
    assert _post(client, "/api/mv/cards/plan", slug=slug).json()["grade"] == "simple"
    for e in plan["empty"]:
        assert _post(client, "/api/mv/cards/draw", slug=slug, slot=e["slot"], tone="fresh", grade="standard").status_code == 200
    # while cards are there the song keeps their grade, whatever is asked for
    for g in ("simple", "standard"):
        st = _post(client, "/api/mv/cards/done", slug=slug, grade=g).json()
        assert st["grade"] == "standard" and len(st["cards"]) == len(plan["empty"]) and st["empty"] == []
    assert _post(client, "/api/mv/cards/draw", slug=slug, slot=plan["empty"][0]["slot"], tone="warm", redraw=True).status_code == 200
    # taken out: the other grade can start
    assert _post(client, "/api/mv/cards/remove", slug=slug).json()["removed"] == len(plan["empty"])
    again = _post(client, "/api/mv/cards/plan", slug=slug, grade="simple").json()
    assert again["grade"] == "simple" and "grade" not in again["world"] and len(again["empty"]) == len(plan["empty"])


def test_icons_more_than_two_hundred_things_and_a_line_sung_again_shows_another():
    things = set(cardworld.PROPS[1:]) | set(cardworld.PROPS_STD) | set(card_icons.NAMES)
    assert len(card_icons.NAMES) >= 160 and len(things) >= 200
    assert not set(card_icons.NAMES) & (set(cardworld.PROPS) | set(cardworld.PROPS_STD))
    assert all(fam in card_icons.FAMILIES and words and shapes for fam, words, shapes in card_icons.TABLE.values())
    wd = cardworld.make_world(8, "standard")
    lines = [("lyric", "送你一束玫瑰"), ("lyric", "火箭飛向太空"), ("lyric", "靈感突然出現"), ("lyric", "雪花輕輕落下"), ("lyric", "抱著我的泰迪熊")]
    got = [cardworld.parse(sp) for sp in cardworld.plan_standard(lines, 3, wd)]
    assert [g[4] for g in got] == ["rose", "rocket", "bulb", "snowflake", "teddy"]
    assert not any(cardworld.parse(sp)[4] in card_icons.TABLE for sp in cardworld.plan(lines, 3, cardworld.make_world(8)))   # simple: as before
    # every family in a card with one person, two, and nobody, and on the table
    for fam in card_icons.FAMILIES:
        name = next(n for n in card_icons.NAMES if card_icons.TABLE[n][0] == fam)
        for subject, frame in (("solo_front", "mid"), ("duo_face", "wide"), ("none", "wide"), ("none", "still")):
            im = cardworld.draw(cardworld.card("grass.bigtree.none", "day", "clear", subject, name, frame, "l", 0), wd, 5)
            assert im.size == (1920, 1080)
    kk = cardworld.K(wd, "day", 1)
    for name in card_icons.NAMES:
        card_icons.draw_icon(kk, name, 300, 400, 200)
    # the same line six times: not six times the same thing
    again = [("lyric", "想你的夜裡寫一封信")] * 6
    props = [cardworld.parse(sp)[4] for sp in cardworld.plan_standard(again, 3, wd)]
    assert props == ["thought", "letter"] * 3, props
    once = [("lyric", "把蛋糕切開")] * 4
    props = [cardworld.parse(sp)[4] for sp in cardworld.plan_standard(once, 3, wd)]
    assert props[0] == "cake" and props[1] == "none" and props[2] == "cake", props


def test_premium_tells_the_song_as_one_story():
    from app.mvstudio import cardstory
    verse = ["清晨的街道很安靜", "我一個人走過轉角", "陽光照在窗台上", "想起你說過的話"]
    pre = ["也許有一天", "我們會再見面"]
    chorus = ["我們在雨中的約定", "撐著同一把傘", "你笑著說不分開", "直到星星都睡了"]
    bridge = ["後來我搬到遠方", "沒有下雨的城市", "每天看著天空"]
    lines = ([("intro", "")] + [("lyric", t) for t in verse + pre + chorus] + [("interlude", "")]
             + [("lyric", t) for t in bridge + pre + chorus + chorus] + [("outro", "")])
    secs = cardstory.sections(lines, "雨中的約定")
    assert [s["sec"] for s in secs] == (["intro"] + ["verse"] * 4 + ["pre"] * 2 + ["chorus"] * 4 + ["interlude"] + ["bridge"] * 3
                                        + ["pre"] * 2 + ["chorus"] * 8 + ["outro"])
    assert [s["turn"] for s, (k, _) in zip(secs, lines) if s["sec"] == "chorus"] == [0] * 4 + [1] * 4 + [2] * 4
    wd = cardworld.make_world(11, "premium")
    assert wd["grade"] == "premium" and cardworld.valid_world(wd)
    wd = cardstory.prepare(wd, lines, "雨中的約定")
    assert wd["keep"] == "umbrella" and wd["keep_col"] and cardworld.valid_world(wd)
    specs, st = cardstory.plan_premium(lines, 11, wd, "雨中的約定")
    assert specs == cardstory.plan_premium(lines, 11, wd, "雨中的約定")[0]
    assert len(specs) == len(lines) and len(set(specs)) == len(specs) and all(cardworld.parse(sp) for sp in specs)
    got = [cardworld.parse(sp) for sp in specs]
    ch = [g for g, s in zip(got, secs) if s["sec"] == "chorus"]
    # every chorus at the song's one chorus place (one terrain, one landmark), seen in several ways
    assert len({tuple(g[0].split(".")[:2]) for g in ch}) == 1 and len({g[0] for g in ch}) >= 4 and len({g[5] for g in ch}) >= 4
    assert all(g[3].startswith("duo") for g, s in zip(got, secs) if s["sec"] == "chorus" and s["turn"] == 0 and g[4] not in ("tears",))
    assert sum(1 for g in got if g[4] == "none") <= len(got) // 4          # few cards with nothing in them
    order = cardstory.ORDER
    turn_light = {}
    for g, s in zip(got, secs):
        if s["sec"] == "chorus" and g[1] != "overcast":
            turn_light.setdefault(s["turn"], set()).add(g[1])
    assert all(len(v) == 1 for v in turn_light.values())         # a chorus keeps its light ...
    ls = [order.index(next(iter(turn_light[t]))) for t in sorted(turn_light)]
    assert ls == sorted(ls) and ls[0] < ls[-1]                   # ... and each one comes later
    assert all(g[4] in ("umbrella", "umbrellai") for g, s in zip(got, secs) if s["sec"] in ("verse", "pre", "chorus", "bridge") and s["k"] == 0)
    assert got[0][0] == got[-1][0] == st["home"] and got[-1][1] == "night" and got[-1][5] == "moon"   # the last card: the first place again, at night
    b = next(g for g, (k, t) in zip(got, lines) if t == "沒有下雨的城市")
    assert b[2] == "clear"                                       # "no rain": no rain
    for sp in specs[:3] + specs[-3:]:
        assert cardworld.draw(sp, wd, 1).size == (1920, 1080)
    # a verse sung again before the chorus is not the chorus; the title says where the chorus starts
    v2 = [("lyric", t) for t in ("第一段的話", "第二段的話", "又唱一次的主歌", "還是那段主歌", "唱出歌名雨中的約定", "副歌第二句")]
    song = v2 + v2[2:] + v2[4:]
    secs = cardstory.sections(song, "雨中的約定")
    assert [s["sec"] for s in secs] == ["verse", "verse", "pre", "pre", "chorus", "chorus", "pre", "pre", "chorus", "chorus", "chorus", "chorus"]
    assert [s["turn"] for s in secs if s["sec"] == "chorus"] == [0, 0, 1, 1, 2, 2]
    # nothing in the words: the lead wears a red scarf all through
    plain = cardstory.prepare(cardworld.make_world(12, "premium"), [("lyric", "啦啦啦"), ("lyric", "嗯嗯嗯")])
    assert plain["keep"] == "" and plain[plain["lead"]]["extra"] == "scarf"


def test_the_page_can_ask_for_the_premium_grade(client, root):
    sid, slug, pdir = _aligned_project(client, root)
    plan = _post(client, "/api/mv/cards/plan", slug=slug, grade="premium").json()
    assert plan["grade"] == "premium" and plan["world"]["grade"] == "premium" and "keep" in plan["world"] and plan["cards"] == []
    assert plan == _post(client, "/api/mv/cards/plan", slug=slug, grade="premium").json()
    for e in plan["empty"]:
        assert _post(client, "/api/mv/cards/draw", slug=slug, slot=e["slot"], tone="fresh", grade="premium").status_code == 200
    for g in ("simple", "standard", "premium"):
        st = _post(client, "/api/mv/cards/done", slug=slug, grade=g).json()
        assert st["grade"] == "premium" and st["world"] == plan["world"] and len(st["cards"]) == len(plan["empty"]) and st["empty"] == []
    assert _post(client, "/api/mv/cards/remove", slug=slug).json()["removed"] == len(plan["empty"])
    assert _post(client, "/api/mv/cards/plan", slug=slug, grade="standard").json()["world"]["grade"] == "standard"


def test_more_parts_shots_and_ways_to_stand():
    from app.mvstudio import card_parts, cardstory
    things = set(cardworld.PROPS[1:]) | set(cardworld.PROPS_STD) | set(card_icons.NAMES)
    assert len(things) >= 1000 and len(cardworld.TERRAINS) >= 30 and len(cardworld.LANDMARKS) >= 150 and len(cardworld.FRONTS) >= 25
    assert len(cardworld.SUBJECTS[1:] + cardworld.SUBJECTS_STD + cardworld.SUBJECTS_PREM) >= 40
    assert len(cardworld.FRAMES + cardworld.FRAMES_STD + cardworld.FRAMES_PREM) >= 12
    pairs = [(t, lm) for t in cardworld.TERRAINS for lm in cardworld.LANDMARKS if cardworld.fits(lm, t)]
    assert len(pairs) >= 2000 and all(any(cardworld.fits(lm, t) for t in cardworld.TERRAINS) for lm in cardworld.LANDMARKS)
    assert all(any(cardworld.fits(lm, t) for lm in ("bigtree", "signpost", "bicycle", "hotair")) for t in cardworld.TERRAINS)
    # a song's world is never given by chance a landmark that only words ask for
    for i in range(40):
        wd = cardworld.make_world(500 + i, ("standard", "premium")[i % 2])
        assert cardworld.valid_world(wd) and len(wd["places"]) == (10, 16)[i % 2]
        for pl in wd["places"]:
            c = cardworld.composite(pl)
            assert not c or (c[1] not in card_parts.KEYWORD_ONLY and cardworld.fits(c[1], c[0]) and cardworld.front_fits(c[2], c[0])), pl
    # all of them draw
    wd = cardworld.make_world(21, "premium")
    lights, seen = list(cardworld.LIGHTS), set()
    for i, t in enumerate(card_parts.TERRAIN_FN):
        lm = next(x for x in ("bigtree", "signpost", "bicycle", "hotair") if cardworld.fits(x, t))
        im = cardworld.draw(cardworld.card(f"{t}.{lm}.none", lights[i % 7], "clear", "none", "none", "wide", "c", 0), wd, 2)
        seen.add(im.resize((32, 18)).tobytes())
    assert len(seen) == len(card_parts.TERRAIN_FN)
    for i, lm in enumerate(card_parts.LANDMARK_FN):
        t = [x for x in cardworld.TERRAINS if cardworld.fits(lm, x)][i % 3 % sum(1 for x in cardworld.TERRAINS if cardworld.fits(lm, x))]
        f = [x for x in cardworld.FRONTS if cardworld.front_fits(x, t)]
        pl = cardworld.with_view(f"{t}.{lm}.{f[i % len(f)]}", None, ("", "near", "centre", "small")[i % 4])
        assert cardworld.valid_place(pl) and cardworld.composite(pl)[1] == lm
        assert cardworld.draw(cardworld.card(pl, lights[i % 7], "clear", "solo_back", "none", "wide", "c", 0), wd, 2).size == (1920, 1080)
    for i, f in enumerate(card_parts.FRONT_FN):
        t = next(x for x in cardworld.TERRAINS if cardworld.front_fits(f, x))
        cardworld.draw(cardworld.card(f"{t}.signpost.{f}", "night" if i % 2 else "day", "clear", "duo_front", "none", "mid", "c", 0), wd, 2)
    for i, sub in enumerate(cardworld.SUBJECTS_PREM):
        cardworld.draw(cardworld.card("grass.bigtree.none", "day", "clear", sub, "none", ("mid", "wide", "far")[i % 3], cardworld.POSES[i % 3], i % 2), wd, 2)
    shots = set()
    for i, fr in enumerate(cardworld.FRAMES_PREM):
        for pl, light, sub in (("coast.lighthouse.rocks", "sunset", "duo_hands"), ("classroom", "night", "duo_apart")):
            sp = cardworld.card(pl, light, "clear", sub, "hearts", fr, "c", i)
            im = cardworld.draw(sp, wd, 2)
            assert im.size == (1920, 1080) and im.mode == "RGB" and im.tobytes() == cardworld.draw(sp, wd, 2).tobytes()
            shots.add(im.resize((32, 18)).tobytes())
            cardworld.draw(sp, cardworld.make_world(21), 2)          # a simple world draws it as an ordinary card
    assert len(shots) == 2 * len(cardworld.FRAMES_PREM)
    k = cardworld.K(wd, "day", 1)
    for name in card_icons.NAMES:
        card_icons.draw_icon(k, name, 500, 500, 200)
    # the longest word wins: the shark, not "fish"; simple worlds read as before
    lines = [("lyric", t) for t in ("一隻鯊魚游過", "熊貓在吃竹子", "買了一份熱狗", "湖畔的風", "在拜拜的時候", "刻骨銘心的愛")]
    got = [cardworld.parse(sp) for sp in cardworld.plan_standard(lines, 3, cardworld.make_world(8, "standard"))]
    assert [g[4] for g in got[:3]] == ["shark", "panda", "hotdog"] and got[3][0].startswith("lake.")
    assert "temple" not in got[4][0] and got[5][4] != "bone"
    rows = cardstory._rows()
    assert cardstory.hints(cardworld._simple("沒有鯊魚"), rows).get("prop") != "shark"
    simple = cardworld.make_world(8)
    assert cardworld.plan(lines, 3, simple) == cardworld.plan(lines, 3, simple) and all(
        cardworld.parse(sp)[4] in cardworld.PROPS and cardworld.parse(sp)[0] in cardworld.PLACES for sp in cardworld.plan(lines, 3, simple))
    # the standard grade keeps to its own shots and stances
    long = [("intro", "")] + [("lyric", t) for t in ("雨落在窗外的小巷", "夕陽下我們牽著手", "回憶裡的那年", "月光下跳舞", "亂了頭緒")] * 8 + [("outro", "")]
    for i in range(4):
        swd = cardworld.make_world(60 + i, "standard")
        for sp in cardworld.plan_standard(long, 60 + i, swd):
            g = cardworld.parse(sp)
            assert g[3] not in cardworld.SUBJECTS_PREM and g[5] not in cardworld.FRAMES_PREM and not cardworld.view_of(g[0])
    # premium: many kinds of shot and stance in one song
    pwd = cardstory.prepare(cardworld.make_world(61, "premium"), long, "")
    specs = cardstory.plan_premium(long, 61, pwd, "")[0]
    got = [cardworld.parse(sp) for sp in specs]
    assert len(set(specs)) == len(specs) and len({g[5] for g in got}) >= 7 and len({g[3] for g in got}) >= 8
    assert {"memory", "photo"} & {g[5] for g in got} and "moon" in {g[5] for g in got}
    for a, b in zip(got, got[1:]):
        assert not (a[5] == b[5] and a[5] in cardworld.FRAMES_STD + cardworld.FRAMES_PREM), (a, b)


def test_the_song_name_comes_first_and_emoji_only_when_nothing_else_has_the_word():
    from app.mvstudio import card_emoji, card_icons, cardstory
    # 〈彩虹〉: the rainbow is the song's thing in premium, and what a standard line that says 彩虹 shows
    assert cardstory.title_keep("彩虹")[0] == "rainbow" and cardstory.title_keep("小雨")[0] == "umbrella"
    assert cardstory.title_keep("找一個字代替") is None
    parts = [("intro", "～ 前奏 ～"), ("lyric", "哪裡有彩虹告訴我 能不能把我的願望還給我"), ("lyric", "所有的雲都跑到我這裡"),
             ("lyric", "有沒有口罩一個給我"), ("outro", "～ 尾奏 ～")]
    wd = cardworld.make_world(11, "standard")
    got = [cardworld.parse(sp) for sp in cardworld.plan_standard(parts, 11, wd, "彩虹")]
    assert got[1][4] == "rainbow" and got[2][2] == "cloudy" and got[3][4] == "e_face_with_medical_mask"
    pw = cardstory.prepare(cardworld.make_world(11, "premium"), parts, "彩虹")
    assert pw["keep"] == "rainbow"
    specs = cardstory.plan_premium(parts, 11, pw, "彩虹")[0]
    assert any(cardworld.parse(sp)[4] == "rainbow" for sp in specs)
    # the emoji are in the icon table after the hand-made ones, and their words after every other row
    names = list(card_icons.TABLE)
    assert len(card_emoji.ENTRIES) > 400 and names.index("e_rainbow") > max(names.index(n) for n in names if not n.startswith("e_"))
    assert all(what["prop"].startswith("e_") for _ws, what in cardworld.EMOJI_HINTS)
    assert not any(what.get("prop", "").startswith("e_") for _ws, what in cardworld.ICON_HINTS)


def test_an_emoji_card_is_drawn():
    from app.mvstudio import card_emoji
    wd = cardworld.make_world(4, "standard")
    for prop in ("e_teddy_bear", "e_cloud", "e_red_apple"):
        spec = cardworld.card("road", "day", "cloudy", "solo_front", prop, "still", "c", 0)
        assert cardworld.valid_card(spec) if hasattr(cardworld, "valid_card") else cardworld.parse(spec)
        im = cardworld.draw(spec, wd, 1)
        assert im.size == (1920, 1080)
    # the shapes are filled as SVG fills them: the cloud's outline and inside, and nothing outside it
    layers = card_emoji._layers("e_cloud", 64)
    cover = layers[0][1]
    assert cover[32, 32] and not cover[2, 2] and 0.25 < cover.mean() < 0.8


def test_what_a_line_does_with_its_thing():
    from app.mvstudio import cardphrase, cardstory as cs
    rows = cs._rows()
    things = [(ws, w) for ws, w in rows if w.get("prop") and w["prop"] not in cs.NOT_A_THING]
    places = [(ws, w) for ws, w in rows if w.get("place") or w.get("terrain") or w.get("landmark")]

    def read(t):
        r = cardphrase.read(cardworld._simple(t), things, cs._negated, cardworld._simple, places)
        return (r["act"], r["thing"]) if r else None
    assert read("我想留一張紙給妳") == ("give", "letter")          # the thing before 給
    assert read("送你一束玫瑰") == ("give", "rose")                 # the thing after 送你
    assert read("忙著追逐天空中的流星") == ("toward", "shooting")
    assert read("我聽見雨滴落在青青草地")[0] == "listen"
    assert read("我看不見你") is None                               # 看不見: not done
    assert read("回到過去") is None and read("往事只能回味") is None   # 往 in 往事
    assert read("給我勇氣") is None                                 # a feeling is nothing to hand over
    assert cardphrase.read(cardworld._simple("與你相遇"), things, cs._negated, cardworld._simple, places)["with"]
    # in a song: handing over the thing, under it, towards it
    parts = [("lyric", "我想摘兩顆星給妳"), ("lyric", "我們在星空下"), ("lyric", "朝著氣球跑去")]
    w = cs.prepare(cardworld.make_world(3, "premium"), parts, "")
    got = [cardworld.parse(sp) for sp in cs.plan_premium(parts, 3, w, "")[0]]
    assert got[0][3] == "duo_face" and got[0][5] == "give" and got[0][4] in card_icons_table()
    for sp in cs.plan_premium(parts, 3, w, "")[0]:
        assert cardworld.draw(sp, w, 1).size == (1920, 1080)
    for frame, prop, subject in (("under", "e_umbrella", "duo_front"), ("toward", "e_balloon", "solo_away"), ("give", "envelope", "duo_face")):
        assert cardworld.draw(cardworld.card("road", "day", "clear", subject, prop, frame, "l", 0), w, 2).size == (1920, 1080)


def card_icons_table():
    from app.mvstudio import card_icons
    return card_icons.TABLE


def test_the_grammar_of_a_line_gives_a_face_a_count_and_who():
    pytest = __import__("pytest")
    pytest.importorskip("jieba")
    from app.mvstudio import cardgrammar as cg, cardstory as cs
    rows = cs._rows()
    r = cg.read("我想摘兩顆星給妳", rows)
    assert r["who"] == "我" and r["to"] == "你" and [t["n"] for t in r["things"] if t["word"] == "星"] == [2]
    assert cg.read("沒有地球太陽還是會繞會繞", rows)["who"] == "太陽"          # the noun before the verb; 沒有 does nothing
    assert cg.read("所有的雲都跑到我這裡", rows)["who"] == "雲" and cg.read("害怕破壞完美的平衡點", rows)["who"] == "我"
    assert cg.read("看不見妳的笑", rows)["face"] == "" and cg.read("害怕破壞完美的平衡點", rows)["face"] == "擔心"
    # in a card: the tenth field, drawn; a card without it is as before
    sp = cardworld.card("road", "day", "clear", "duo_face", "e_glowing_star", "give", "c", 0, "shy", 2, "m")
    assert sp.endswith("|shy.2.m") and cardworld.parse(sp) and cardworld.extras(sp) == ("shy", 2, "m")
    assert cardworld.card("road", "day", "clear", "solo_front", "none", "mid", "c", 0).count("|") == 8
    assert cardworld.parse(sp[:-7] + "nope.2.m") is None and cardworld.parse(sp[:-1] + "x") is None
    w = cs.prepare(cardworld.make_world(3, "premium"), [("lyric", "x")], "")
    for face in cardworld.FACES:
        assert cardworld.draw(cardworld.card("road", "day", "clear", "solo_front", "none", "close", "c", 0, face, 1, "o"), w, 1).size == (1920, 1080)
    assert cardworld.draw(sp, w, 1).size == (1920, 1080)
    parts = [("lyric", "我想摘兩顆星給妳"), ("lyric", "你張開了雙翼"), ("lyric", "害怕破壞完美的平衡點")]
    w = cs.prepare(cardworld.make_world(3, "premium"), parts, "")
    got = [cardworld.extras(sp) for sp in cs.plan_premium(parts, 3, w, "")[0]]
    assert got[0][1] == 2 and got[1][2] == "o" and got[2][0] == "worry"


def test_who_does_it_in_a_line():
    """[2026-11-16] Who a line is about: more than one doer, and the ones who are not (whose, where, with whom)."""
    pytest = __import__("pytest")
    pytest.importorskip("jieba")
    from app.mvstudio import cardgrammar as cg, cardstory as cs
    rows = cs._rows()
    who = lambda t: cg.read(t, rows)["who"]  # noqa: E731
    assert who("我走回從前你往未來飛") == "我、你" and who("我知道你會懂") == "我、你"      # a second doer inside the clause
    assert who("你和我走過那條街") == "你、我" and who("原來我們和愛情曾經靠得那麼近") == "我們"
    r = cg.read("與你相遇 好幸運", rows)
    assert r["who"] == "我" and r["to"] == "你" and who("為妳翹課的那一天") == "我"       # with / for whom is not who does it
    assert who("妳說依賴 是我們的阻礙") == "你"                                          # 我們的: whose
    assert who("是誰風裏雨裏一直默默守護在原地") == "誰" and who("是你讓我看見彩虹") == "你、我"
    assert who("但偏偏 風漸漸 把距離吹得好遠") == "風" and who("但偏偏 雨漸漸 大到我看妳不見") == "雨、我"
    assert who("我們有始有終 就走到世界盡頭") == "我們"                                  # 就: the same ones go on
    assert who("原來你是我最想留住的幸運") == "你" and who("也是我現在正服下的毒藥") == "我"
    assert who("想你想到失眠") == "我" and who("放在你眺望我的夜裡") == "我"             # 想你想到: not 你; …的夜裡 says which night
    assert cg.read("大到我看妳不見", rows)["to"] == "你"


def test_a_word_is_a_noun_by_where_it_stands():
    """[2026-11-16] jieba gives a word one tag everywhere (願望 and 解藥 verbs, 張開 a name); the place in the line decides."""
    pytest = __import__("pytest")
    pytest.importorskip("jieba")
    from app.mvstudio import cardgrammar as cg, cardstory as cs
    rows = cs._rows()

    def parts(t):
        r = cg.read(t, rows)
        return [x["word"] for x in r["things"]], list(r["do"])
    assert parts("能不能把我的願望還給我") == (["願望"], ["還給"])                 # after 的
    assert "解藥" in parts("也許時間是一種解藥")[0] and "笑" in parts("看不見妳的笑")[0]       # after a counter; after 的
    assert parts("我喜歡你的笑")[1] == ["喜歡"]
    nouns, verbs = parts("遇見愛以後")
    assert "愛" in nouns and verbs == ["遇見"]                                  # one of the cards' things after a verb
    assert "等待" in parts("想要等待 卻害怕失去")[1] and parts("忙著微笑和哭泣")[0] == []        # still done
    assert parts("你張開了雙翼") == (["雙翼"], ["張開"]) and "沙灘" in parts("海浪輕輕拍著沙灘")[0]   # jieba's "names"
    assert parts("把回憶鎖進抽屜")[0] == ["回憶", "抽屜"] and "飛" in parts("我走回從前你往未來飛")[1]
