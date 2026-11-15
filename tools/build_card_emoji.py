"""Build app/mvstudio/card_emoji.json.gz: the emoji pictures the picture cards can use, with the Chinese words
that ask for them.

Sources (download them with npm, then point this script at the unpacked folders):
  npm pack @iconify-json/fluent-emoji-flat cldr-annotations-full
  - Fluent Emoji Flat (Microsoft, MIT): the pictures, as SVG shapes in a 32 x 32 box.
  - Unicode CLDR annotations, zh-Hant (Unicode License v3): each emoji's name and keywords in Traditional Chinese.

  python tools/build_card_emoji.py <fluent-emoji-flat package dir> <cldr-annotations-full package dir>

Only things are taken (animals and plants, food, objects, places and vehicles, the sky), no people, faces, flags
or signs, and only pictures drawn with plain filled shapes (no gradients, clipping or strokes). Each gets a
"family" (where it goes in a card, as in card_icons) and the words that ask for it: its name and those of its
keywords that are at least two characters, not too common among the emoji, and not on the STOP list.
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path

GROUPS = ("Animals & Nature", "Food & Drink", "Objects", "Travel & Places", "Activities")
EXTRA = ("face-with-medical-mask",)        # a mask (口罩) is only there as a face wearing one
SKIP = re.compile(r"(-suit$|mahjong|flower-playing|pool-8|chess|joystick|video-game|game-die|oclock|thirty|-face$|^flag|^map-of|kaaba|synagogue|mosque|hindu-temple|shinto|dagger|crossed-swords|"
                  r"water-pistol|bow-and-arrow|cigarette|syringe|drop-of-blood|x-ray|petri-dish|dna|test-tube|alembic|"
                  r"military-helmet|bikini|briefs|thong|one-piece|razor|plunger|toilet|mouse-trap|nazar|hamsa|joker|"
                  r"slot-machine|ballot|fax|pager|trackball|computer-disk|floppy|optical-disk|dvd|videocassette|"
                  r"control-knobs|level-slider|card-index|card-file|inbox|outbox|file-|clipboard|bar-chart|chart-|"
                  r"bookmark-tabs|label|link$|linked-paperclips|paperclip|pushpin|round-pushpin|straight-ruler|triangular-ruler|"
                  r"nut-and-bolt|clamp|gear|magnet|hook|screwdriver|wrench|hammer-and|pick$|carpentry|axe|"
                  r"identification|receipt|ledger|envelope-with-arrow|incoming-envelope|e-mail|mobile-phone-with|"
                  r"speaker|loudspeaker|bell-with-slash|battery|electric-plug|low-battery|"
                  r"yen|euro|pound-banknote|dollar|chart|motorized-wheelchair|manual-wheelchair|white-cane|crutch|"
                  r"construction|stop-sign|traffic-light|police-car-light|fuel-pump|oil-drum|barber|love-hotel|"
                  r"japanese-post|post-office|bank|hospital|department-store|convenience-store|factory|stadium|"
                  r"articulated|delivery-truck|pickup-truck|sport-utility|oncoming|minibus|trolleybus|auto-rickshaw|"
                  r"monorail|suspension-railway|light-rail|railway-car|tram-car|mountain-railway|motorway|"
                  r"ring-buoy|rescue|fire-extinguisher|safety|prayer-beads|diya|funeral|coffin|chains|broken-chain|"
                  r"lotion|sponge|soap|toothbrush|broom|bucket|roll-of-paper|wastebasket|shower|bathtub|"
                  r"poultry-leg|cut-of-meat|bacon|meat-on-bone|fish-cake|oden|falafel|tamale|stuffed|flatbread|"
                  r"fondue|canned|beverage-box|mate$|amphora|chopsticks|spoon|kitchen-knife|fork-and|salt|butter|"
                  r"pig-nose|paw-prints|microbe|bug$|cockroach|fly$|mosquito|worm|scorpion|spider|sauropod|t-rex|"
                  r"mammoth|dodo|bison|beaver|badger|skunk|otter|sloth|orangutan|gorilla|guide-dog|service-dog|"
                  r"ox$|water-buffalo|ram$|ewe|goat|boar|llama|two-hump|rhinoceros|hippopotamus|crocodile|"
                  r"empty-nest|nest-with|coral|rosette|herb|leafy|ginger|garlic|onion|bell-pepper|hot-pepper|"
                  r"broccoli|cucumber|eggplant|pea-pod|beans|olive|potato|roasted|chestnut|peanuts|avocado|"
                  r"wood$|brick|rock$|seat$|wheel$|thermometer|timer|stopwatch|hourglass-not|bellhop|luggage$)")
STOP = {"天氣", "臉", "物品", "東西", "符號", "動物", "植物", "食物", "飲料", "生病", "同性", "雙性", "跨性別", "交通", "交通工具",
        "車輛", "建築", "建築物", "地方", "運動", "遊戲", "工具", "器具", "日本", "中國", "美國", "歐洲", "非洲", "亞洲", "美洲",
        "澳洲", "西班牙", "墨西哥", "法國", "義大利", "印度", "韓國", "英國", "德國", "水果", "蔬菜", "早餐", "午餐", "晚餐",
        "點心", "甜點", "料理", "餐點", "餐廳", "辦公", "辦公室", "文件", "裝置", "設備", "電腦", "臉部", "表情", "醫生", "牙醫",
        "皮膚科", "病菌", "不舒服", "疾病", "感冒", "藥物", "垃圾", "工作", "工程", "物體", "鳥類", "昆蟲", "哺乳類", "爬蟲類",
        "海洋", "大自然", "自然", "天空", "宇宙", "地點", "旅行", "旅遊", "出遊", "休閒", "娛樂", "慶祝", "節日", "派對", "生日",
        "時間", "時鐘", "小時", "鐘點", "俄羅斯", "原住民的", "得分", "牌局", "低手", "熱帶", "外太空人", "填充", "玩物", "長絨毛"}
ONE_CHAR = {"雲", "霧", "虹"}   # one-character names that are safe enough to look for in a line

SKY_NAMES = re.compile(r"^(sun|sun-with-face|sun-behind.*|cloud.*|crescent-moon|full-moon|new-moon|.*quarter-moon|waxing.*|waning.*|"
                       r"comet|glowing-star|star|shooting-star|milky-way|ringed-planet|rainbow|airplane|small-airplane|"
                       r"airplane-departure|airplane-arrival|helicopter|rocket|flying-saucer|satellite|parachute|globe-.*|"
                       r"tornado|cyclone|fog|wind-face|bird|dove|eagle|owl|blackbird|swan|phoenix-bird|bat|butterfly|honeybee|"
                       r"kite|fireworks|carp-streamer|balloon|high-voltage|money-with-wings|aerial-tramway|mountain-cableway|"
                       r"sunrise|sunset|night-with-stars|cityscape.*|bridge-at-night|sunrise-over-mountains)$")
RAIN_NAMES = re.compile(r"^(snowflake|droplet|fallen-leaf|maple-leaf|leaf-fluttering-in-wind|cherry-blossom|feather|musical-note|"
                        r"musical-notes|sparkles|bubbles|confetti-ball|coin|four-leaf-clover|shamrock|gem-stone)$")
BUBBLE_NAMES = re.compile(r"^(face-with-medical-mask|crystal-ball|light-bulb|magnifying-glass.*|musical-score)$")
SIDE_OBJECTS = re.compile(r"^(bed|chair|couch-and-lamp|door|window|ladder|moai|musical-keyboard|long-drum|drum|postbox|"
                          r"shopping-cart|television|desktop-computer|printer|toolbox|placard|package|basket|"
                          r"mantelpiece-clock|film-projector|telescope|microscope|headstone|closed-mailbox.*|open-mailbox.*|"
                          r"balance-scale|christmas-tree|tanabata-tree|pine-decoration|goal-net|flag-in-hole|"
                          r"pot-of-food|shallow-pan-of-food|birthday-cake|potted-plant|deciduous-tree|evergreen-tree|"
                          r"palm-tree|cactus|sunflower|sheaf-of-rice|seedling|umbrella-on-ground|beach-with-umbrella|"
                          r"jack-o-lantern|wrapped-gift|teddy-bear|nesting-dolls|japanese-dolls|wind-chime|red-paper-lantern|"
                          r"brown-mushroom|mushroom|watermelon|pineapple|coconut|honey-pot|jar|teapot|snowman.*|camping|tent)$")
HOLD_FLOWERS = re.compile(r"^(rose|tulip|hibiscus|blossom|white-flower|wilted-flower|bouquet|lotus|hyacinth)$")


def family(name: str, group: str) -> str:
    if SKY_NAMES.match(name):
        return "sky"
    if RAIN_NAMES.match(name):
        return "rain"
    if BUBBLE_NAMES.match(name):
        return "bubble"
    if HOLD_FLOWERS.match(name):
        return "hold"
    if SIDE_OBJECTS.match(name) or group in ("Animals & Nature", "Travel & Places"):
        return "side"
    return "hold"


NUM = r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"


def shapes(body: str):
    """The picture as plain shapes, or None when it uses something else."""
    if re.search(r"Gradient|clipPath|<use|transform|stroke|opacity|mask", body):
        return None
    out = []
    for tag, attrs in re.findall(r"<(\w+)([^>]*)/?>", body):
        a = dict(re.findall(r'([\w:-]+)="([^"]*)"', attrs))
        if tag in ("g", "defs"):
            continue
        fill = a.get("fill", "#000")
        if fill == "none":
            continue
        if not re.fullmatch(r"#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6}", fill):
            return None
        if len(fill) == 4:
            fill = "#" + "".join(ch * 2 for ch in fill[1:])
        fill = fill[1:].lower()
        if tag == "path":
            out.append(["p", fill, 1 if a.get("fill-rule") == "evenodd" else 0, a["d"]])
        elif tag == "circle":
            out.append(["e", fill, float(a.get("cx", 0)), float(a.get("cy", 0)), float(a["r"]), float(a["r"])])
        elif tag == "ellipse":
            out.append(["e", fill, float(a.get("cx", 0)), float(a.get("cy", 0)), float(a["rx"]), float(a["ry"])])
        elif tag == "rect":
            rx = float(a.get("rx", a.get("ry", 0)))
            out.append(["r", fill, float(a.get("x", 0)), float(a.get("y", 0)), float(a["width"]), float(a["height"]), rx])
        else:
            return None
    return out or None


def main(flat_dir: str, cldr_dir: str) -> None:
    flat = Path(flat_dir)
    icons = json.loads((flat / "icons.json").read_text(encoding="utf-8"))
    cats = json.loads((flat / "metadata.json").read_text(encoding="utf-8"))["categories"]
    chars = json.loads((flat / "chars.json").read_text(encoding="utf-8"))
    by_name = {}
    for hexes, name in chars.items():
        by_name.setdefault(name, "".join(chr(int(h, 16)) for h in hexes.split("-")))
    ann = json.loads((Path(cldr_dir) / "annotations" / "zh-Hant" / "annotations.json").read_text(encoding="utf-8"))
    ann = {k.replace("️", ""): v for k, v in ann["annotations"]["annotations"].items()}
    picked = []
    for group in GROUPS:
        for name in cats[group]:
            if not SKIP.search(name):
                picked.append((name, group))
    picked += [(n, "Smileys & Emotion") for n in EXTRA]
    cand = {}
    for name, group in picked:
        ch = by_name.get(name, "").replace("️", "")
        a = ann.get(ch)
        body = icons["icons"].get(name, {}).get("body")
        if not a or not body:
            continue
        shp = shapes(body)
        if not shp:
            continue
        tts = a.get("tts", [""])[0]
        words = [tts] + [w for w in a.get("default", []) if w != tts]
        cand[name] = (family(name, group), words, shp)
    common = Counter(w for _f, ws, _s in cand.values() for w in set(ws))
    table = {}
    for name, (fam, words, shp) in cand.items():
        keep = []
        for i, w in enumerate(words):
            w = w.strip()
            if not w or w in STOP or re.search(r"[A-Za-z0-9]", w) or (len(w) >= 3 and w.endswith("座")):   # (signs of the zodiac)
                continue
            if len(w) < 2 and w not in ONE_CHAR:
                continue
            if i > 0 and common[w] > 4:
                continue
            if w not in keep:
                keep.append(w)
        if keep:
            table[name] = {"family": fam, "words": keep, "shapes": shp}
    data = {"source": "Fluent Emoji Flat (Microsoft, MIT) and Unicode CLDR zh-Hant annotations (Unicode License v3); "
                      "built by tools/build_card_emoji.py", "box": 32, "emoji": table}
    out = Path(__file__).resolve().parent.parent / "app" / "mvstudio" / "card_emoji.json.gz"
    with gzip.open(out, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    fams = Counter(v["family"] for v in table.values())
    print(f"{len(table)} emoji ({dict(fams)}), {out.stat().st_size} bytes -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
