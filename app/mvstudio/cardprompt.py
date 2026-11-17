"""A picture card as words: the prompt an image model (Sana) draws the card from.

The plan of a card ("w2|place|light|weather|subject|prop|frame|pos|n", cardworld) says where the picture
is, in what light, who is in it doing what, and what else is there. Here those become one English
sentence, with the song's two people described the same way on every card (from the song's world), so
that the model draws the same pair through the whole song.

Nothing here draws or needs the model: it is text in, text out, the same text for the same card.
"""
from __future__ import annotations

import colorsys
import re
from typing import Any, Dict, Optional, Sequence

from . import card_icons, cardworld

STYLE = "soft watercolor anime illustration, clean lines, gentle colors, the picture fills the whole frame"
# [2026-11-17] The tone of the cards is for the AI cards too (the user chose 黑白漫畫 and got colour): the finished
# picture gets the same change of colours as a simple card (cards.toned), and the black-and-white tone is also
# drawn as one, in ink and screentone, where a colour picture made grey would look washed out.
STYLE_TONE = {"manga": "black and white manga illustration, clean ink lines, grey screentone shading, monochrome, "
                       "the picture fills the whole frame"}
NEGATIVE_TONE = {"manga": ", color, colorful"}
NEGATIVE = ("letterbox, black bars, border, picture frame, text, caption, speech bubble, watermark, "
            "signature, extra people, crowd, deformed hands, extra fingers, distorted face, creepy face, "
            "exaggerated expression, wide open mouth, teeth, asymmetrical eyes, bad anatomy")
# [2026-11-17] Faces. Asked for "crying" or "a sad face", the model draws a face so strong it frightens; and it
# has few pixels for a face that is small in the picture. So a feeling is said quietly (a mood, where the
# eyes look), never as a strong expression, and every card that shows a face asks for a calm, simple one.
CALM = "simple soft anime face with a calm natural expression, closed mouth"
# [2026-11-17] Asked for by the user, as a choice: no face is shown. Whoever is in the picture is seen from
# behind, from the side or with the face turned away, in every shot. (Of the first 41 AI cards the ones seen
# from behind were all fine; the frightening ones were faces.)
AWAY = "seen from behind or in side view, faces turned away from the viewer, no face visible"
NEGATIVE_AWAY = ", face looking at the viewer, front view of a face"
# [2026-11-17] And two more, each a mode of its own (they were one at first, with the small figures on one scene in
# four; the user: 純風景就純風景，小人物就小人物分開). Scenery ("none"): the place of the card with its light, its
# weather and its thing fills the picture and nobody is in it. Small figures ("small"): the same scenery with the
# people of the card as small figures far away, on which a bad face or a bad limb does not show.
SCENERY = "wide scenery shot, nobody in the picture"
SCENERY_SMALL = ("extreme wide scenery shot, the landscape fills the picture, the figures very small and far away, "
                 "no face visible")
NEGATIVE_SCENERY = ", close-up, portrait, large figure, face"
GARMENT = {"skirt": "blouse", "dress": "dress", "shorts": "shirt", "tee": "t-shirt", "hoodie": "hoodie",
           "jacket": "jacket"}


# ---- the people -------------------------------------------------------------------------------------------
def colour(rgb: Sequence[int]) -> str:
    r, g, b = (max(0, min(255, int(v))) / 255.0 for v in rgb[:3])
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < 0.14:
        return "white" if v > 0.88 else "light grey" if v > 0.62 else "grey" if v > 0.35 else "black"
    deg = h * 360
    name = ("red" if deg < 14 or deg >= 346 else "orange" if deg < 40 else "yellow" if deg < 66
            else "green" if deg < 160 else "teal" if deg < 192 else "blue" if deg < 252
            else "purple" if deg < 292 else "pink")
    if name == "red" and v > 0.85 and s < 0.6:
        name = "pink"
    if name == "orange" and v < 0.72:
        return "dark brown" if v < 0.42 else "brown"
    if v > 0.86 and s < 0.3:
        return "pale " + name
    if v < 0.5:
        return "dark " + name
    return name


# the hair colours a card world is made from, as an image model should hear them: the simple cards' blue-grey
# and wine-red are shades of dark hair there, and said as "dark blue" the model paints bright blue hair
_HAIR = {(92, 70, 70): "dark brown", (52, 48, 62): "black", (134, 88, 62): "brown", (182, 134, 88): "light brown",
         (116, 62, 70): "dark auburn", (70, 84, 110): "black"}


def hair(rgb: Sequence[int]) -> str:
    r, g, b = (int(v) for v in rgb[:3])
    if (r, g, b) in _HAIR:
        return _HAIR[(r, g, b)]
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    if v < 0.32 or (s < 0.25 and v < 0.45):
        return "black"
    if s < 0.16:
        return "grey" if v < 0.8 else "white"
    deg = h * 360
    if deg < 50 or deg >= 340:
        return "dark brown" if v < 0.45 else "brown" if v < 0.72 else "light brown" if s > 0.4 else "blonde"
    return colour(rgb)


CUT = {"long": "long", "bob": "bob-cut", "ponytail": "ponytail", "twin": "twin-tail", "bun": "tied-up",
       "short": "short", "fringe": "short fringed", "spiky": "short spiky"}
WEAR = {"skirt": "a {top} blouse and a {low} skirt", "dress": "a {top} dress",
        "shorts": "a {top} shirt and {low} shorts", "tee": "a {top} t-shirt and {low} trousers",
        "hoodie": "a {top} hoodie and {low} trousers", "jacket": "a {top} jacket and {low} trousers"}
KIND = {"girl": "young woman", "boy": "young man", "mother": "middle-aged woman", "father": "middle-aged man",
        "grandma": "old woman", "grandpa": "old man", "child": "small child"}


# [2026-11-17] Asked for by the user: one or two people, and two are plainly a man and a woman, as on the simple
# cards. The model made the man of a pair a second woman when his clothes were pink (the simple cards' world gives
# either of them any colour), and added people of its own. So a man is said to be tall and wears no pink or
# purple here, the number of people is said in the prompt (ONE, PAIR), and negative() names what must not come.
MALE = ("boy", "father", "grandpa")
_MANS = {"pink": "light grey", "pale pink": "light grey", "purple": "dark blue", "pale purple": "light grey",
         "dark purple": "dark blue", "dark pink": "grey"}
ONE = "alone, only one person in the picture"
PAIR = "a couple, exactly two people, one man and one woman"


def clothes(rgb: Sequence[int], kind: str) -> str:
    name = colour(rgb)
    return _MANS.get(name, name) if kind in MALE else name


def person(look: Dict[str, Any], kind: str) -> str:
    """One person, said the same way on every card. (No glasses, hat or scarf: the model gives them to
    whoever stands beside the one who has them.)"""
    wear = WEAR.get(str(look.get("wear")), "a {top} top and {low} trousers").format(
        top=clothes(look.get("top") or (240, 240, 240), kind), low=clothes(look.get("low") or (80, 90, 110), kind))
    tall = "tall " if kind in ("boy", "father") else ""
    return (f"a {tall}{KIND.get(kind, kind)} with {CUT.get(str(look.get('cut')), 'short')} "
            f"{hair(look.get('hair') or (60, 50, 50))} hair, wearing {wear}")


def head_count(spec: str) -> int:
    """How many people the plan of a card shows: 0, 1, 2 (3 with both parents beside the lead)."""
    p = str(spec).split("|")
    subject, frame = p[4], p[6]
    who = p[9].split(".")[2] if len(p) > 9 and len(p[9].split(".")) > 2 else ""
    if frame == "still" or subject == "none":
        return 0
    n = 2 if subject.startswith("duo") else 1
    if subject.startswith("solo") and who in cardworld.CAST:
        n = 2
    if who == "p":
        n += 1
    return n


def negative(spec: str, people: str = "", tone: str = "") -> str:
    """What the picture of this card must not show: the same for every card, and by how many people it has."""
    out = NEGATIVE + {"away": NEGATIVE_AWAY, "none": NEGATIVE_SCENERY, "small": NEGATIVE_SCENERY}.get(people, "")
    out += NEGATIVE_TONE.get(tone, "")
    n = 0 if people == "none" else head_count(spec)
    if n == 0:
        return out + ", people, person, human figure"
    if n == 1:
        return out + ", two people, couple, second person, group"
    if n == 2:
        p = str(spec).split("|")
        who = p[9].split(".")[2] if len(p) > 9 and len(p[9].split(".")) > 2 else ""
        # the pair of the song is a man and a woman; a mother or a child beside the lead may be of the lead's own sex
        return out + ", three people, third person, group" + ("" if who in cardworld.CAST else ", two women, two men")
    return out


# [2026-11-17] Two small figures came out as two men (the user's card: two hoodies and two short heads, from
# behind). Far away and from behind only the outline tells a man from a woman, and in black and white the colour
# of a top tells nothing, so a small figure is said by its outline: the hair (a woman's cut, a man's short hair),
# what a woman wears below (a skirt, a dress, shorts), and the man the taller of the two.
LEGS = {"skirt": " and a skirt", "shorts": " and shorts"}
TRESS = {"long": "long hair", "bob": "bob-cut hair", "ponytail": "a long ponytail", "twin": "long twin tails",
         "bun": "hair tied up in a bun"}


def brief(look: Dict[str, Any], kind: str) -> str:
    """One person in a few words, for a figure that is small in the picture: told by the outline."""
    top = f"{clothes(look.get('top') or (240, 240, 240), kind)} {GARMENT.get(str(look.get('wear')), 'top')}"
    if kind in MALE:
        return f"a {'taller ' if kind in ('boy', 'father') else ''}{KIND.get(kind, kind)} with short hair in a {top}"
    if kind == "child":
        return f"a {KIND[kind]} in a {top}"
    return (f"a {KIND.get(kind, kind)} with {TRESS.get(str(look.get('cut')), 'long hair')} in a {top}"
            f"{LEGS.get(str(look.get('wear')), '')}")


def small_figures(world: Dict[str, Any], subject: str, who: str = "") -> str:
    """The people of a card as small figures far away: who they are, and only whether they stand, sit or walk."""
    lead = "boy" if world.get("lead") == "boy" else "girl"
    other = "girl" if lead == "boy" else "boy"
    a, b = brief(world[lead], lead), brief(world[other], other)
    if who == "o":
        a, b = b, a
    elif who in cardworld.CAST:
        cast = cardworld.cast_people(world)
        b = (f"{brief(cast['mother'], 'mother')} and {brief(cast['father'], 'father')}" if who == "p"
             else brief(cast[cardworld.CAST[who]], cardworld.CAST[who]))
    doing = ("walking" if any(k in subject for k in ("walk", "run", "away", "follow")) else
             "sitting" if any(k in subject for k in ("sit", "ground", "stars", "backs", "lean", "crouch")) else "standing")
    if subject.startswith("duo") or (subject.startswith("solo") and who in cardworld.CAST):
        pair = "only two small figures, a man and a woman" if who not in cardworld.CAST else "the small figures"
        return f"far away, {pair}, {a} and {b}, {doing} together"
    return f"far away, the single small figure of {b if subject.startswith('other') else a}, {doing}, alone"


def persons(world: Dict[str, Any], who: str = "") -> Dict[str, str]:
    """{"a": the lead, "b": the other one}; who (a cast letter of the card) puts someone else where the
    other one stands: a mother, a father, a grandmother, a grandfather, a child, both parents."""
    lead = "boy" if world.get("lead") == "boy" else "girl"
    other = "girl" if lead == "boy" else "boy"
    out = {"a": person(world[lead], lead), "b": person(world[other], other)}
    if who == "o":
        out["a"], out["b"] = out["b"], out["a"]
    elif who in cardworld.CAST:
        cast = cardworld.cast_people(world)
        if who == "p":
            out["b"] = f"{person(cast['mother'], 'mother')} and {person(cast['father'], 'father')}"
        else:
            name = cardworld.CAST[who]
            out["b"] = person(cast[name], name)
    return out


# ---- the place --------------------------------------------------------------------------------------------
TERRAIN = {
    "grass": "on a wide grassy hill", "coast": "on the seashore", "skyline": "on a hill above a city skyline",
    "town": "in a small town street", "peaks": "in the mountains, peaks behind", "woods": "in the woods",
    "snow": "on a snowy field", "wheat": "in a wheat field", "river": "by a river", "dunes": "among sand dunes",
    "cliff": "on a cliff above the sea", "plaza": "in a city plaza", "lake": "by a calm lake",
    "terraces": "among rice terraces", "harbor": "at a harbor", "canyon": "in a red rock canyon",
    "bamboo": "in a bamboo grove", "orchard": "in an orchard", "lavender": "in a lavender field",
    "rooftops": "above the rooftops of a town", "island": "on a small island beach", "waterfall": "near a waterfall",
    "savanna": "on a savanna", "aurora": "on a snowy plain under the northern lights", "reeds": "among tall reeds by the water",
    "tracks": "beside railway tracks", "oldtown": "in an old town lane", "park": "in a city park",
    "highway": "beside an open highway", "boardwalk": "on a seaside boardwalk", "cloudsea": "on a peak above a sea of clouds",
}
PLACE = {
    "meadow": "in a meadow", "sea": "at the seaside", "rooftop": "on a rooftop", "street": "on a city street",
    "school": "in a schoolyard", "classroom": "inside a classroom", "station": "on a train platform",
    "park": "in a park", "bridge": "on a bridge", "forest": "in a forest", "lake": "by a lake",
    "room": "inside a cosy bedroom", "flowers": "in a field of flowers", "road": "on a long country road",
    "pier": "on a wooden pier", "hill": "on a hilltop", "cafe": "inside a cafe by the window",
    "busstop": "at a bus stop", "library": "inside a library", "train": "inside a train carriage by the window",
    "market": "in a street market", "snowtown": "in a snowy town", "garden": "in a garden",
    "alley": "in a narrow alley", "field": "in an open field", "fair": "at a fairground",
    "stairs": "on a long flight of outdoor stairs", "riverbank": "on a riverbank",
}
LANDMARK = {
    "ferris": "a ferris wheel", "clocktower": "a clock tower", "phonebooth": "a phone booth", "camp": "a campfire and a tent",
    "bigtree": "one big old tree", "cherry": "a cherry blossom tree", "maple": "a red maple tree", "gate": "an old gate",
    "shelter": "a small wooden shelter", "benchlamp": "a bench under a street lamp", "vending": "a vending machine",
    "trainpass": "a train passing in the distance", "farbridge": "a long bridge in the distance",
    "radiotower": "a radio tower", "watertower": "a water tower", "hotair": "hot air balloons in the sky",
    "sailboats": "sailboats on the water", "observatory": "an observatory dome", "stage": "an empty outdoor stage",
    "lifeguard": "a lifeguard tower", "jetty": "a wooden jetty", "jet": "a jet crossing the sky", "tents": "a row of tents",
    "lanterns": "hanging lanterns", "torii": "a red torii gate", "arch": "a stone arch", "eiffel": "a tall iron lattice tower",
    "hut": "a small hut", "treehouse": "a tree house", "store": "a corner store", "rollercoaster": "a roller coaster",
    "waterwheel": "a water wheel", "archbridge": "an arched stone bridge", "watchtower": "a watchtower",
    "trafficlight": "a traffic light", "grave": "a gravestone", "greatwall": "a long stone wall over the hills",
    "bigship": "a big ship", "rowboat": "a rowboat", "fishingboat": "a fishing boat", "beachumbrella": "a beach umbrella",
    "palmtree": "a palm tree", "pinetree": "a pine tree", "baretree": "a bare tree", "appletree": "an apple tree",
    "ginkgo": "a golden ginkgo tree", "flowerbed": "a flower bed", "cablecar": "a cable car", "foodcart": "a food cart",
    "flowershop": "a flower shop", "bookshop": "a little bookshop", "hoop": "a basketball hoop", "goal": "a soccer goal",
    "pool": "a swimming pool", "picnic": "a picnic blanket", "bbq": "a barbecue grill", "weddingarch": "a wedding flower arch",
    "skylanterns": "sky lanterns rising", "postoffice": "a post office", "crane": "a construction crane",
    "windturbine": "wind turbines", "powerpole": "a power pole", "dish": "a satellite dish", "stump": "a tree stump",
    "wishtree": "a wishing tree hung with ribbons", "moongate": "a round moon gate", "stonelantern": "a stone lantern",
    "koiflags": "carp streamers in the wind", "dragonboat": "a dragon boat", "teahouse": "a tea house",
    "archway": "a stone archway", "hotspring": "a steaming hot spring", "sandcastle": "a sand castle",
    "launchpad": "a rocket on a launch pad", "pirateship": "an old sailing ship", "ticketbooth": "a ticket booth",
    "crossing": "a railway crossing", "gasstation": "a gas station", "apartment": "an apartment block",
    "porchswing": "a porch swing", "lovelocks": "a fence covered in love locks", "heartsign": "a heart-shaped sign",
    "icestand": "an ice cream stand", "fruitstand": "a fruit stand", "balloonstand": "a balloon stand",
    "swings": "a set of swings", "lighthouse": "a lighthouse", "greenhouse": "a greenhouse",
    "mailbox": "a mailbox", "doghouse": "a doghouse", "signpost": "a signpost", "well": "an old stone well",
    "slide": "a playground slide", "none": "",
}
FRONT = {
    "none": "", "flowers": "flowers in the foreground", "grass": "tall grass in the foreground",
    "fence": "a wooden fence in the foreground", "railing": "a railing in the foreground",
    "lamps": "street lamps", "branches": "branches in the foreground", "rocks": "rocks in the foreground",
    "puddles": "puddles on the ground", "reeds": "reeds in the foreground", "tulips": "tulips in the foreground",
    "sunflowers": "sunflowers in the foreground", "bushes": "bushes in the foreground", "vines": "hanging vines",
    "lanternline": "a line of lanterns overhead", "bunting": "bunting flags overhead", "wires": "power lines overhead",
    "stones": "stones in the foreground", "posts": "wooden posts in the foreground", "snowdrift": "snowdrifts",
    "shells": "shells on the sand", "candles": "small candles in the foreground", "wheat": "wheat in the foreground",
    "stringlights": "string lights overhead", "clothesline": "a clothesline with laundry",
}
LIGHT = {"dawn": "at dawn, soft pink morning light", "day": "on a bright day, blue sky",
         "golden": "at golden hour, warm low sunlight", "sunset": "at sunset, orange sky",
         "dusk": "at dusk, purple twilight", "night": "at night, deep blue sky with stars",
         "overcast": "under a grey overcast sky"}
WEATHER = {"clear": "", "cloudy": "the sky full of clouds", "rain": "rain falling", "snow": "snow falling"}

# ---- who does what: {a} the lead, {b} the other one ---------------------------------------------------------
SUBJECT = {
    "none": "",
    "solo_front": "{a}, standing and facing the viewer", "solo_back": "{a}, standing, seen from behind",
    "solo_walk": "{a}, walking", "solo_sit": "{a}, sitting", "solo_reach": "{a}, reaching one hand up toward the sky",
    "solo_open": "{a}, standing with both arms wide open", "solo_wave": "{a}, waving goodbye with one hand",
    "solo_run": "{a}, running", "solo_hips": "{a}, standing with hands on the hips",
    "solo_think": "{a}, one hand on the chin, thinking", "solo_cover": "{a}, head lowered, hiding the face in both hands",
    "solo_heart": "{a}, one hand on the heart", "solo_cheer": "{a}, raising both arms happily",
    "solo_point": "{a}, pointing into the distance", "solo_shade": "{a}, shading the eyes with one hand and looking far away",
    "solo_pray": "{a}, hands together in prayer", "solo_head": "{a}, head lowered, one hand on the forehead",
    "solo_jump": "{a}, jumping in the air", "solo_crouch": "{a}, crouching down with the head lowered",
    "solo_ground": "{a}, sitting on the ground hugging the knees", "solo_away": "{a}, walking away, seen from behind",
    "solo_give": "{a}, holding something out with both hands", "solo_look": "{a}, looking up at the sky",
    "other_back": "{b}, standing, seen from behind", "other_front": "{b}, standing and facing the viewer",
    "other_away": "{b}, walking away, seen from behind",
    "duo_front": "{a} and {b}, standing side by side, facing the viewer",
    "duo_back": "{a} and {b}, side by side, seen from behind", "duo_sit": "{a} and {b}, sitting side by side",
    "duo_apart": "{a} and {b}, standing apart, turned away from each other", "duo_hands": "{a} and {b}, holding hands",
    "duo_face": "{a} and {b}, standing face to face, looking at each other", "duo_hug": "{a} and {b}, hugging each other",
    "duo_walk": "{a} and {b}, walking together", "duo_run": "{a} and {b}, running together",
    "duo_backs": "{a} and {b}, sitting back to back", "duo_lean": "{a} and {b}, one leaning on the other's shoulder",
    "duo_cheer": "{a} and {b}, raising their arms happily", "duo_point": "{a} and {b}, one pointing into the distance",
    "duo_follow": "{a} walking ahead and {b} following behind", "duo_wave": "{a} and {b}, waving to each other from a distance",
    "duo_dance": "{a} and {b}, dancing together", "duo_ground": "{a} and {b}, sitting on the ground side by side",
    "duo_stars": "{a} and {b}, lying on the ground looking up at the sky",
    "duo_comfort": "{a} comforting {b}, a hand on the shoulder", "duo_far": "{a} and {b}, standing far apart from each other",
}
FRAME = {
    "wide": "wide shot, full body, the figures small in the scenery", "mid": "medium full shot, full body",
    "close": "close-up, upper body", "far": "extreme wide shot, tiny figures in a vast landscape",
    "still": "close-up still life, no people", "sil": "wide shot, dark silhouettes against the light",
    "over": "over-the-shoulder view", "hands": "close-up of the hands",
    "mirror": "wide shot, reflected in still water", "moon": "wide shot, a huge full moon behind",
    "split": "wide shot, far apart on opposite sides of the picture", "window": "seen through a window",
    "photo": "wide shot, the faded look of an old photograph", "globe": "wide shot",
    "memory": "wide shot, the soft hazy look of a memory", "tilt": "wide shot, tilted camera angle",
    "give": "medium full shot, one handing something to the other", "under": "low angle, looking up",
    "toward": "medium full shot, coming toward the viewer",
}
FACE = {"smile": "a gentle smile", "sad": "a quiet sad look", "closed": "eyes closed", "wow": "a look of surprise",
        "laugh": "a gentle smile", "wry": "a faint smile", "tear": "a quiet sad mood", "cry": "looking down, a quiet sad mood",
        "angry": "a slight frown", "shy": "a shy look", "love": "a tender look", "worry": "a worried look",
        "miss": "a longing look", "lonely": "a lonely look", "sleepy": "sleepy eyes", "firm": "a determined look"}
SIDE = {"l": "on the left side of the picture", "r": "on the right side of the picture", "c": ""}

# ---- what else is in the picture ----------------------------------------------------------------------------
PROP = {
    "none": "", "stars": "a sky full of stars", "shooting": "a shooting star", "bigmoon": "a huge full moon",
    "hearts": "a tender romantic mood", "letter": "holding a letter", "plane": "a paper plane flying",
    "birds": "birds in the sky", "balloons": "colorful balloons", "clover": "a four-leaf clover",
    "petals": "petals drifting in the wind", "leaves": "leaves drifting in the wind", "tears": "a quiet sad mood",
    "dots": "a silent, speechless mood", "ask": "a puzzled look", "call": "one hand beside the mouth, calling",
    "notes": "music in the air", "lantern": "holding a glowing lantern", "kite": "a kite in the sky",
    "rainbow": "a big rainbow across the sky", "fireflies": "fireflies glowing around", "umbrella": "holding an umbrella",
    "bike": "a bicycle", "thread": "a red thread tied to a finger", "wings": "small angel wings on the back",
    "frames": "old photographs hanging on a string", "clock": "a large clock", "bubbles": "soap bubbles floating",
    "hourglass": "an hourglass", "calendar": "a wall calendar", "suitcase": "a suitcase", "phone": "holding a phone",
    "key": "an old key", "candle": "a lit candle", "ring": "a ring", "cranes": "paper cranes", "dandelion": "dandelion seeds in the wind",
    "broken": "a quiet sad mood", "wine": "a glass of wine", "guitar": "holding a guitar", "camera": "holding a camera",
    "diary": "an open diary", "footprints": "footprints on the ground", "door": "a half-open door",
    "raincloud": "one dark rain cloud overhead", "rays": "rays of sunlight breaking through", "fireworks": "fireworks in the sky",
    "paperboat": "a paper boat on the water", "butterfly": "a butterfly flying nearby", "cat": "a cat nearby",
    "thought": "lost in thought", "dream": "eyes closed, a dreamy mood",
    # the icons that are a feeling, a sign or a mark rather than a thing
    "twohearts": "a tender romantic mood", "heartwings": "a tender romantic mood", "heartbeat": "a hand on the heart",
    "question": "a puzzled look", "zzz": "sleepy", "sparkle": "sparkles of light", "angry": "a slight frown",
    "sweat": "", "infinity": "a calm, endless horizon", "thumbs": "giving a thumbs up",
    "handshake": "shaking hands", "arrowup": "looking upward", "arrowleft": "looking back over the shoulder",
    "checkmark": "a relieved look", "yesterday": "the faded look of a memory", "moonbed": "a large crescent moon in the sky",
    "summit": "a mountain summit in the distance", "pill": "holding a small medicine capsule in an open palm",
    "medicine": "a small medicine bottle and pills", "potion": "holding a small glass bottle of dark liquid",
    "mask": "a white face mask", "trash": "a trash bin", "stopsign": "a stop sign", "footpath": "a path leading away",
    "stormcloud": "dark storm clouds overhead", "hourhand": "a large clock", "photoframe": "a framed photograph",
    "bookopen": "an open book", "textbook": "a stack of school books", "tornado": "a whirlwind in the distance",
    "constellation": "constellations in the sky", "dizzy": "",
    "e_sun": "the bright sun large in the sky", "e_cloud": "heavy clouds gathering right overhead",
    "e_headphone": "wearing headphones", "e_crescent_moon": "a crescent moon in the sky",
    "e_rainbow": "a big rainbow across the sky", "e_umbrella": "holding an umbrella",
}
_PIECES = ("heart", "hearts", "book", "open", "photo", "frame", "two", "big", "moon", "bed", "rain", "storm",
           "cloud", "foot", "path", "hour", "hand", "key", "hole", "stop", "sign", "arrow", "up", "down", "left",
           "right", "snow", "sun", "star", "fire", "paper", "ice", "tea", "rice", "fish", "bird", "tree", "leaf",
           "flower", "ball", "boat", "ship", "house", "light", "lamp", "bell", "wing", "wings", "glass", "cup",
           "box", "bag", "shoe", "hat", "ring", "letter", "mail", "phone", "clock", "watch", "door", "window",
           "wall", "bridge", "road", "sea", "wave", "sand", "stone", "rock", "wind", "night", "day", "love",
           "baby", "old", "new", "red", "blue", "green", "gold", "black", "white", "cake", "candy", "seed",
           "bone", "tail", "shell", "egg", "cube", "bottle", "basket", "cooker", "tart", "roll", "noodle",
           "blossom", "rise", "set", "globe", "crane", "humming", "wood", "pecker", "polar", "bear", "panda",
           "gold", "clown", "puffer", "gull", "horse", "whale", "half", "full", "shooting", "wheat", "ear",
           "sugar", "spring", "hot", "pot", "dog", "cotton", "shaved", "fried", "bubble", "water", "candle",
           "cane", "ginger", "bread", "veg", "maple", "ginkgo", "pine", "cone", "cherry", "potted", "plant",
           "hay", "bale", "crystal", "salt", "shaker", "pencil", "note", "notes", "music", "school", "text")
_MORE = ("wedding", "dress", "glasses", "closed", "kerchief", "perfume", "lipstick", "mark", "nail", "polish",
         "tooth", "brush", "rocking", "chair", "feather", "duster", "holder", "flash", "electric", "alarm",
         "screw", "driver", "watering", "can", "wheel", "barrow", "paint", "bucket", "roller", "measuring",
         "tape", "draw", "spinning", "kitchen", "sheet", "stand", "player", "curtain", "stage", "ballet",
         "stub", "chalk", "board", "smart", "chat", "type", "writer", "roll", "motor", "cycle", "jet",
         "fighter", "air", "balloon", "space", "station", "traffic", "parking", "meter", "steering",
         "boarding", "pass", "sleeping", "rose", "volley", "fishing", "rod", "score", "top", "wand",
         "broken", "bandaged", "sleepy", "face", "cross", "roads", "five", "envelope", "dance", "plate",
         "pumpkin", "lantern", "broom", "stick", "prayer", "beads", "dream", "catcher", "castle", "gate",
         "treasure", "map", "toss", "carriage", "birthday", "card", "graduation", "bouquet", "credit",
         "diamond", "scales", "justice", "painter", "tools", "camera", "micro", "mirror", "compass",
         "scale", "well", "cassette", "microphone", "telescope", "newspaper", "ticket", "calligraphy",
         "dumplings", "dragon", "lotus", "sword", "shield", "hourglass", "infinity", "dandelion", "cone")
_TWINS = ("scarf", "lamp", "shield", "film", "umbrella", "bridge", "shooting", "cliff", "cave", "cloud", "wind",
          "rainbow", "heart", "moon", "star", "sun", "flower", "tree", "book", "clock", "key", "ring", "bell",
          "satellite", "lighthouse", "surfboard", "ferriswheel", "tombstone", "microphone")
_WHOLE = ("pineapple", "sunflower", "lighthouse", "greenhouse", "strawberry", "watermelon", "butterfly",
          "dragonfly", "grasshopper", "caterpillar", "headphones", "chopsticks", "skateboard", "basketball",
          "volleyball", "motorcycle", "chandelier", "binoculars", "calculator", "dictionary", "stethoscope",
          "wheelchair", "typewriter", "microscope", "gramophone", "tambourine", "chrysanthemum")


def _split(name: str, known: frozenset, memo: dict) -> Optional[list]:
    """name as the fewest known pieces, or None."""
    if not name:
        return []
    if name in memo:
        return memo[name]
    best = None
    for n in range(len(name), 1, -1):
        if name[:n] in known and (n > 2 or name[:n] == "up"):
            rest = _split(name[n:], known, memo)
            if rest is not None and (best is None or 1 + len(rest) < len(best)):
                best = [name[:n]] + rest
    memo[name] = best
    return best


_KNOWN = frozenset(_PIECES + _MORE)


def words(name: str) -> str:
    """A name that has no words of its own, as words: e_alarm_clock -> alarm clock, weddingdress ->
    wedding dress, cloudi -> cloud (the icon twin of a drawn thing ends in i)."""
    if name.startswith("e_"):
        return name[2:].replace("_", " ")
    if name.endswith("i") and name[:-1] in _TWINS:
        name = name[:-1]
    name = re.sub(r"\d+$", "", name)
    if "_" in name:
        return name.replace("_", " ")
    if name in _WHOLE or len(name) < 9:
        return name
    out = _split(name, _KNOWN, {})
    return " ".join(out) if out and len(out) > 1 else name


def _a(text: str) -> str:
    if text.endswith("s") and not text.endswith(("ss", "us")):
        return text
    return ("an " if text[:1] in "aeiou" else "a ") + text


def prop(name: str, still: bool = False, alone: bool = False) -> str:
    """alone: the thing with nobody to hold or wear it (a scenery card)."""
    if alone:
        text = prop(name)
        if re.search(r"\b(look|mood|smile|frown|eyes|face|hand|hands|thumbs|shoulder)\b", text):
            return ""                                  # a feeling or a gesture: nothing to show without people
        return re.sub(r"^(holding|wearing) ", "", text)
    if name in PROP and not still:
        return PROP[name]
    text = words(name)
    if name.startswith("e_") and re.search(r"\bface\b|smil|grin|cry|tear|kiss|frown|angry|sleep", text):
        if "medical mask" in text:
            return "a white face mask" if still else "wearing a white face mask"
        return ""                             # an emoji face: a strong expression is what the model draws badly
    if still and name in PROP:
        text = re.sub(r"^(holding|wearing) ", "", PROP[name])
        return text + " on a table"
    return _a(text) + (" on a table" if still else "")


def place(name: str) -> str:
    parts = str(name).split(".")
    if len(parts) < 3:
        return PLACE.get(parts[0], f"at a {words(parts[0])}")
    terrain, landmark, front = parts[0], parts[1], parts[2]
    view = parts[3] if len(parts) > 3 else ""
    out = [TERRAIN.get(terrain, f"in a {words(terrain)} landscape")]
    mark = LANDMARK.get(landmark, _a(words(landmark)))
    if mark:
        out.append({"near": f"{mark} close by", "small": f"{mark} far in the distance"}.get(view, f"{mark} in the background"))
    fr = FRONT.get(front, f"{words(front)} in the foreground")
    if fr:
        out.append(fr)
    return ", ".join(out)


def build(spec: str, world: Optional[Dict[str, Any]], people: str = "", tone: str = "") -> Optional[str]:
    """The prompt of a card, or None for a card that is not one of a song's world (the first cards had
    no people of their own and no plan to read). people: "away" no face is shown (AWAY); "none" scenery,
    nobody in the picture; "small" scenery with the people of the card small and far away (SCENERY_SMALL)."""
    away, scenery = people == "away", people in ("none", "small")
    if not world or not cardworld.parse(spec) or not cardworld.valid_world(world):
        return None
    p = str(spec).split("|")
    where, light, weather, subject, thing, frame, pos = p[1:8]
    face, who = "-", ""
    if len(p) > 9:
        f = p[9].split(".")
        face, who = f[0], (f[2] if len(f) > 2 else "")
    still = frame == "still"
    bits = []
    doing = "" if still or scenery else SUBJECT.get(subject, "{a}, " + words(subject.split("_", 1)[-1]))
    if doing:
        ppl = persons(world, who)
        if subject.startswith("solo") and who in cardworld.CAST:
            # someone of the family beside the lead: the card shows both
            doing = doing + ", with {b} beside"
        hidden = away
        if hidden:
            doing = doing.replace("standing and facing the viewer", "standing, seen from behind").replace(
                ", facing the viewer", ", seen from behind").replace("coming toward the viewer", "walking away")
        bits.append(doing.format(**ppl))
        count = head_count(spec)
        if count == 1:
            bits.append(ONE)
        elif count == 2 and who not in cardworld.CAST:
            bits.insert(len(bits) - 1, PAIR)           # said first, then who the two are
        if FACE.get(face) and not hidden:
            bits.append(FACE[face])
        if SIDE.get(pos) and subject.startswith(("solo", "other")):
            bits.append(SIDE[pos])
    far = people == "small" and not still and subject != "none"
    if far:
        bits.append(small_figures(world, subject, who))
    thing_text = prop(thing, still, alone=scenery and not still)
    if thing_text:
        bits.append(thing_text)
    bits.append(place(where))
    bits.append(LIGHT.get(light, ""))
    if WEATHER.get(weather):
        bits.append(WEATHER[weather])
    if scenery and not still:
        bits.append(SCENERY_SMALL if far else SCENERY)
    else:
        bits.append(FRAME.get(frame, FRAME["wide"]).replace("coming toward the viewer", "walking away")
                    if doing and away else FRAME.get(frame, FRAME["wide"]))
    if doing and away:
        bits.append(AWAY)
    elif doing and frame not in ("sil", "far"):
        bits.append(CALM)
    bits.append(STYLE_TONE.get(tone, STYLE))
    out = []
    for b in ", ".join(b for b in bits if b).split(", "):     # a mood said by the face and by the thing is said once
        if b not in out:
            out.append(b)
    return ", ".join(out)


def known_props() -> int:
    """How many of the pictures have words of their own (the rest are said by their names)."""
    return sum(1 for n in card_icons.TABLE if n in PROP)
