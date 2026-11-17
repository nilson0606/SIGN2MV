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
NEGATIVE = ("letterbox, black bars, border, picture frame, text, caption, speech bubble, watermark, "
            "signature, extra people, crowd, deformed hands, extra fingers")


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


def hair(rgb: Sequence[int]) -> str:
    r, g, b = (int(v) for v in rgb[:3])
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


def person(look: Dict[str, Any], kind: str) -> str:
    """One person, said the same way on every card. (No glasses, hat or scarf: the model gives them to
    whoever stands beside the one who has them.)"""
    wear = WEAR.get(str(look.get("wear")), "a {top} top and {low} trousers").format(
        top=colour(look.get("top") or (240, 240, 240)), low=colour(look.get("low") or (80, 90, 110)))
    return (f"a {KIND.get(kind, kind)} with {CUT.get(str(look.get('cut')), 'short')} "
            f"{hair(look.get('hair') or (60, 50, 50))} hair, wearing {wear}")


def people(world: Dict[str, Any], who: str = "") -> Dict[str, str]:
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
    "solo_think": "{a}, one hand on the chin, thinking", "solo_cover": "{a}, covering the face with both hands",
    "solo_heart": "{a}, one hand on the heart", "solo_cheer": "{a}, cheering with both fists raised",
    "solo_point": "{a}, pointing into the distance", "solo_shade": "{a}, shading the eyes with one hand and looking far away",
    "solo_pray": "{a}, hands together in prayer", "solo_head": "{a}, holding the head with both hands",
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
    "duo_cheer": "{a} and {b}, cheering together", "duo_point": "{a} and {b}, one pointing into the distance",
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
FACE = {"smile": "smiling", "sad": "a sad face", "closed": "eyes closed", "wow": "a surprised face",
        "laugh": "laughing", "wry": "a wry smile", "tear": "a tear on the cheek", "cry": "crying",
        "angry": "an angry face", "shy": "blushing", "love": "a loving look", "worry": "a worried face",
        "miss": "a longing look", "lonely": "a lonely look", "sleepy": "sleepy eyes", "firm": "a determined face"}
SIDE = {"l": "on the left side of the picture", "r": "on the right side of the picture", "c": ""}

# ---- what else is in the picture ----------------------------------------------------------------------------
PROP = {
    "none": "", "stars": "a sky full of stars", "shooting": "a shooting star", "bigmoon": "a huge full moon",
    "hearts": "a tender romantic mood", "letter": "holding a letter", "plane": "a paper plane flying",
    "birds": "birds in the sky", "balloons": "colorful balloons", "clover": "a four-leaf clover",
    "petals": "petals drifting in the wind", "leaves": "leaves drifting in the wind", "tears": "tears on the face",
    "dots": "a silent, speechless mood", "ask": "a puzzled look", "call": "calling out loud",
    "notes": "music in the air", "lantern": "holding a glowing lantern", "kite": "a kite in the sky",
    "rainbow": "a big rainbow across the sky", "fireflies": "fireflies glowing around", "umbrella": "holding an umbrella",
    "bike": "a bicycle", "thread": "a red thread tied to a finger", "wings": "small angel wings on the back",
    "frames": "old photographs hanging on a string", "clock": "a large clock", "bubbles": "soap bubbles floating",
    "hourglass": "an hourglass", "calendar": "a wall calendar", "suitcase": "a suitcase", "phone": "holding a phone",
    "key": "an old key", "candle": "a lit candle", "ring": "a ring", "cranes": "paper cranes", "dandelion": "dandelion seeds in the wind",
    "broken": "a sorrowful, heartbroken mood", "wine": "a glass of wine", "guitar": "holding a guitar", "camera": "holding a camera",
    "diary": "an open diary", "footprints": "footprints on the ground", "door": "a half-open door",
    "raincloud": "one dark rain cloud overhead", "rays": "rays of sunlight breaking through", "fireworks": "fireworks in the sky",
    "paperboat": "a paper boat on the water", "butterfly": "a butterfly flying nearby", "cat": "a cat nearby",
    "thought": "lost in thought", "dream": "eyes closed, a dreamy mood",
    # the icons that are a feeling, a sign or a mark rather than a thing
    "twohearts": "a tender romantic mood", "heartwings": "a tender romantic mood", "heartbeat": "a hand on the heart",
    "question": "a puzzled look", "zzz": "sleepy", "sparkle": "sparkles of light", "angry": "an angry look",
    "sweat": "a nervous look", "infinity": "a calm, endless horizon", "thumbs": "giving a thumbs up",
    "handshake": "shaking hands", "arrowup": "looking upward", "arrowleft": "looking back over the shoulder",
    "checkmark": "a relieved look", "yesterday": "the faded look of a memory", "moonbed": "a large crescent moon in the sky",
    "summit": "a mountain summit in the distance", "pill": "holding a small medicine capsule in an open palm",
    "medicine": "a small medicine bottle and pills", "potion": "holding a small glass bottle of dark liquid",
    "mask": "a white face mask", "trash": "a trash bin", "stopsign": "a stop sign", "footpath": "a path leading away",
    "stormcloud": "dark storm clouds overhead", "hourhand": "a large clock", "photoframe": "a framed photograph",
    "bookopen": "an open book", "textbook": "a stack of school books", "tornado": "a whirlwind in the distance",
    "constellation": "constellations in the sky", "dizzy": "a dizzy look",
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


def prop(name: str, still: bool = False) -> str:
    if name in PROP and not still:
        return PROP[name]
    text = words(name)
    if name.startswith("e_") and re.search(r"\bface\b|smil|grin|cry|tear|kiss|frown|angry|sleep", text):
        if "medical mask" in text:
            return "a white face mask" if still else "wearing a white face mask"
        return "" if still else f"the look of a {text}"
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


def build(spec: str, world: Optional[Dict[str, Any]]) -> Optional[str]:
    """The prompt of a card, or None for a card that is not one of a song's world (the first cards had
    no people of their own and no plan to read)."""
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
    doing = "" if still else SUBJECT.get(subject, "{a}, " + words(subject.split("_", 1)[-1]))
    if doing:
        ppl = people(world, who)
        if subject.startswith("solo") and who in cardworld.CAST:
            # someone of the family beside the lead: the card shows both
            doing = doing + ", with {b} beside"
        bits.append(doing.format(**ppl))
        if FACE.get(face):
            bits.append(FACE[face])
        if SIDE.get(pos) and subject.startswith(("solo", "other")):
            bits.append(SIDE[pos])
    thing_text = prop(thing, still)
    if thing_text:
        bits.append(thing_text)
    bits.append(place(where))
    bits.append(LIGHT.get(light, ""))
    if WEATHER.get(weather):
        bits.append(WEATHER[weather])
    bits.append(FRAME.get(frame, FRAME["wide"]))
    bits.append(STYLE)
    return ", ".join(b for b in bits if b)


def known_props() -> int:
    """How many of the pictures have words of their own (the rest are said by their names)."""
    return sum(1 for n in card_icons.TABLE if n in PROP)
