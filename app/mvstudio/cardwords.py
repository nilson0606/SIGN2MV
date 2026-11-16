# -*- coding: utf-8 -*-
"""[2026-11-16] More words for the picture cards, and more than one picture for a word.

Five hundred songs from an open lyrics corpus were read (cardgrammar) and their words counted: of the nouns the
cards had a picture for a little over half, of the verbs three in ten, of the adjectives and adverbs a quarter.
The words here are the commonest of those that had none. Two things are new beside the words themselves:

  * a word has several pictures (時光: an hourglass, a clock, a calendar...). Each time the word comes in a song
    the next one is taken, so the same word is not the same card every time. VARY does the same for the things
    the cards knew already (hearts, stars, a letter...). The song's own thing (cardstory "keep") never changes.
  * these words are a second choice: what cardworld's own rows find in a line comes first, so no card that had
    a thing before gets another one. A word of one character counts only as a whole word of the line (cardgrammar's
    words), so 手 is not found in 分手 nor 火 in 火車.

Everything is written in the traditional characters the songs are in; table() gives it simplified, with the
names the cards cannot draw left out (a typing mistake here must not break a card).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Sequence, Tuple

# ---------------------------------------------------------------------------------------------- things
# (words, pictures). The first picture is the plainest; the rest are other ways to show the same word.
NOUNS: Tuple[Tuple[Tuple[str, ...], Tuple[str, ...]], ...] = (
    # time
    (("時光", "光陰", "歲月", "時代", "時期", "世紀", "歷史", "年華", "流年"), ("hourglass", "clock", "calendar", "sandglass", "clockwall")),
    (("往事", "舊事", "過去", "昨天", "當初", "當年"), ("yesterday", "photoframe", "album", "phoneold", "gramophone")),
    (("明天", "未來", "將來"), ("tomorrow", "sunrise", "telescopehand", "arrowright")),
    (("青春", "年少", "年輕"), ("kite", "pinwheel", "bicyclei", "skateboard")),
    (("童年", "小時候", "孩子", "小孩", "寶寶", "兒時"), ("teddy", "rockinghorse", "pinwheel", "kitei", "toycar")),
    (("時刻", "一刻", "瞬間", "一刹", "剎那", "轉眼"), ("stopwatch", "hourhand", "shootingi", "sparkle")),
    # life
    (("生命", "性命", "生機", "一生", "今生"), ("sprout", "sapling", "heartbeat", "e_seedling")),
    (("生活", "日子", "日常", "工作"), ("calendari", "coffee", "alarmclock", "briefcase")),
    (("人生", "命運", "天意", "緣分", "緣份", "無緣", "注定", "註定"), ("crossroads", "compassrose", "footpath", "dice", "e_knot")),
    (("起點", "原點", "終點", "地點", "盡頭", "路口"), ("milestone", "flagrace", "roadsign", "footpath")),
    (("過程", "旅途", "旅程", "一程", "路途", "冒險"), ("footpath", "maproll", "suitcase", "compass", "treasuremap")),
    # feeling (a heart of some kind; the face says which feeling)
    (("感覺", "感受", "情緒", "心情", "感情", "情感", "真情", "深情", "情意", "情懷", "情誼", "友情", "情"),
     ("hearti", "heartbeat", "twohearts", "likeheart")),
    (("靈魂", "魂"), ("feather", "sparkle", "halo", "ghost")),
    (("幸福", "美滿", "圓滿", "完美"), ("clover3", "fullmoon", "star5", "infinityheart")),
    (("傷痕", "傷口", "傷害", "痕跡", "疤", "傷"), ("bandaid", "bandagedheart", "brokenheart", "e_adhesive_bandage")),
    (("遺憾", "挫折", "失敗", "悲劇", "殘缺"), ("hourglassbroken", "brokenheart", "raincloud", "halfmoon")),
    (("錯", "對錯", "罪", "過錯"), ("crossmark", "nosign", "warning")),
    (("謊言", "謊", "假象", "借口", "藉口", "面具"), ("maski", "e_performing_arts", "brokenheart")),
    (("諾言", "誓言", "約定", "承諾", "誓約", "保證"), ("pinky", "ring", "heartlock", "rings2", "contract")),
    (("祝福", "禮物", "心意"), ("gift", "ribbon", "bouquet", "e_wrapped_gift")),
    (("關係", "關懷", "陪伴", "默契", "知己", "緣"), ("handshake", "twohearts", "chain")),
    # thought
    (("理由", "原因", "問題", "難題", "疑問", "謎"), ("question", "puzzle", "e_puzzle_piece", "maze")),
    (("結果", "結局", "答案"), ("keyhole", "checkmark", "envelopeopen", "question")),
    (("意義", "道理", "思想", "理想", "目的", "追求", "渴望", "目標", "方向"), ("star5", "lightbulb", "compass", "telescopehand", "summit")),
    (("想像", "想象", "幻想", "幻覺", "傳說", "神話", "童話", "魔力", "魔法"), ("crystalball", "unicorn", "genielamp", "spellbook", "magicwand")),
    (("現實", "真相"), ("alarmclock", "mirror", "clockwall")),
    (("力氣", "力量", "勇氣", "熱血"), ("fist", "shieldi", "lightning", "dumbbell")),
    (("記錄", "紀錄", "珍藏", "紀念"), ("album", "treasure", "photoframe", "polaroid")),
    (("習慣",), ("clockwall", "coffee", "toothbrush")),
    (("滋味", "味道"), ("tea", "coffee", "candy", "lemon")),
    (("空間", "空白", "空虛", "空"), ("circle", "ellipsis", "windowi")),
    (("遊戲", "賭", "輸贏"), ("gamepad", "dice", "chessking", "pokerchip")),
    # the world
    (("世上", "世間", "人間", "紅塵", "天下", "萬物", "天地", "人類"), ("earth", "globe", "planet", "e_globe_showing_asia_australia")),
    (("天空", "藍天", "天上", "天際", "天邊", "晴空"), ("cloudi", "birds", "e_sun_behind_cloud", "kitei")),
    (("天堂", "神", "天使"), ("angel", "halo", "cloudi")),
    (("大地", "地上", "土地", "草地", "草"), ("grass", "sprout", "clover3", "daisy")),
    (("天氣", "氣候"), ("cloudi", "sun", "umbrellai", "thermo")),
    (("空氣", "氣息", "呼吸", "幽香", "芬芳", "香味"), ("windi", "dandelionseed", "feather", "perfume")),
    (("水", "泉水", "水珠", "水滴", "露水", "漣漪"), ("droplet", "wave", "dewdrop", "e_droplet", "puddle")),
    (("火", "火焰", "火花", "烈火"), ("flame", "firei", "campfire", "e_fire", "ember")),
    (("光", "光線", "光輝", "光芒", "亮光", "曙光"), ("rays", "sparkles", "lightbulb", "e_glowing_star", "sunrise")),
    (("煙", "塵", "灰", "灰燼"), ("smoke", "ash", "fog")),
    (("冰", "霜", "寒冰"), ("icecube", "iceberg", "icicle", "e_ice")),
    (("沙", "沙灘", "塵沙"), ("footprintsand", "sandbucket", "shell", "sandglass")),
    (("影", "倒影", "影子", "身影", "背影"), ("shadowi", "mirror", "puddle")),
    # people and home
    (("媽媽", "母親", "爸爸", "父親", "父母", "家人", "親人", "家", "家鄉", "故鄉"), ("house", "e_house_with_garden", "photoframe", "doorway")),
    (("名字", "姓名", "稱呼"), ("gifttag", "badge", "penpaper")),
    # the body (a part of it, close)
    (("手", "雙手", "手心", "手中", "掌心", "手指", "指尖"), ("hand", "handshake", "pinky", "finger")),
    (("眼", "眼睛", "眼神", "眼裡", "眼中", "眼光", "視線", "瞳孔", "眼眸", "雙眼"), ("eye", "glasses", "magnifier")),
    (("腳步", "步伐", "腳印", "腳", "足跡"), ("footprints", "footprint", "footprintsand")),
    (("嘴", "嘴唇", "唇", "雙唇"), ("lips", "lipstickmark")),
    (("耳", "耳朵", "耳邊"), ("ear", "earphones", "conch")),
    (("腦", "腦海", "腦袋"), ("brain", "thought", "bulb")),
    # sound, words, art
    (("歌", "首歌", "情歌", "歌曲", "歌聲", "音樂", "旋律", "節奏", "音符"), ("notes", "musicsheet", "mic", "e_musical_notes", "headphones")),
    (("話", "情話", "對白", "言語", "話語", "句子", "語氣"), ("chatbubble", "ellipsis", "e_megaphone")),
    (("詩", "詩句", "詩篇", "文字"), ("scroll", "quill", "penpaper", "bookopen")),
    (("戲", "角色", "演技", "舞台", "喜劇", "劇本"), ("maski", "curtainstage", "clapper", "e_performing_arts")),
    (("畫面", "場景", "情景", "情節", "片段", "鏡頭"), ("filmi", "filmreel", "e_film_frames", "photo")),
    (("笑聲", "笑話"), ("smile", "chatbubble", "loveface")),
    # small things
    (("線", "絲線", "情絲"), ("yarn", "e_thread", "kiteline")),
    (("牆", "圍牆"), ("wall", "fencei")),
    (("錢", "金錢", "財富"), ("coins", "banknote", "moneybag")),
    (("血", "汗", "汗水"), ("droplet", "sweat", "heartbeat")),
    (("糖", "糖果", "蜜"), ("candy", "lollipop", "sugarcube", "honey")),
    (("胭脂", "口紅", "妝"), ("lipstick", "makeup", "mirror")),
    (("箭",), ("heartarrow", "archery", "target")),
    (("玻璃", "鏡", "鏡子"), ("mirror", "windowi", "e_window")),
)

# what is done, when the line names no thing: (words, pictures)
VERBS: Tuple[Tuple[Tuple[str, ...], Tuple[str, ...]], ...] = (
    (("忘記", "忘", "遺忘", "忘掉", "忘懷", "淡忘", "忘了"), ("ellipsis", "fog", "hourglassbroken", "e_fallen_leaf")),
    (("想起", "記得", "記住", "記起", "回首", "回顧", "回望", "回味", "重溫"), ("thought", "photoframe", "yesterday", "album")),
    (("找", "尋找", "找到", "尋覓", "找回", "尋", "尋到", "探"), ("magnifier", "compass", "flashlight", "binoculars")),
    (("變", "改變", "變得", "變化", "變成", "化作", "化成", "化為"), ("season", "cocoon", "butterfly", "arrowright")),
    (("吹", "吹起", "吹來", "吹散", "吹開", "飄"), ("windi", "dandelionseed", "leaf", "pinwheel")),
    (("流", "流淌", "淌", "流過", "滴", "灑", "流向", "流動"), ("river", "droplet", "wave", "raindrop")),
    (("吃", "喝", "飲", "品嘗", "嘗"), ("bowl", "cup", "tea", "chopsticks", "coffee")),
    (("畫", "描繪", "畫下"), ("palette", "brush", "painting", "crayon")),
    (("醒來", "醒", "睜開", "甦醒"), ("alarmclock", "sunrise", "sunriseclock")),
    (("死", "毀滅", "摧毀", "幻滅", "熄滅", "熄", "消散", "消失", "逝去", "凋落"), ("ash", "e_wilted_flower", "hourglassbroken", "candle")),
    (("放棄", "放下", "放開", "放手", "捨得", "投降", "認輸", "鬆開", "成全"), ("e_balloon", "kitei", "feather", "dandelionseed")),
    (("開始", "出發", "踏上", "啟程", "開啟", "重來"), ("sunrise", "flagrace", "footpath", "arrowright")),
    (("結束", "散場", "落幕", "收場", "完結"), ("curtainstage", "sunsetclock", "hourglass", "checkmark")),
    (("期待", "盼望", "盼", "期盼", "期望", "守候", "守望", "憧憬"), ("telescopehand", "clockwall", "calendari", "hourglass")),
    (("懂", "明白", "了解", "理解", "懂得", "發現", "發覺", "領悟"), ("bulb", "lightbulb", "checkmark")),
    (("面對", "對抗", "抵抗", "抵擋", "承受", "承擔", "挑戰", "闖"), ("shieldi", "fist", "shieldsword", "summit")),
    (("感謝", "謝謝", "感激", "感恩", "報答"), ("bouquet", "gift", "hearti")),
    (("原諒", "接受", "包容", "寬容", "體貼"), ("handshake", "dove", "bandagedheart")),
    (("迷失", "迷惘", "徬徨", "彷徨", "迷茫", "茫然", "徘徊", "流浪", "漂泊", "遊蕩"), ("maze", "crossroads", "fog", "compassrose")),
    (("騙", "欺騙", "說謊", "掩飾", "假裝", "敷衍", "強裝", "故作", "扮"), ("maski", "e_performing_arts")),
    (("學", "學會", "學習", "教", "讀"), ("bookopen", "textbook", "pencil", "gradcap")),
    (("買", "賣", "賺錢", "換", "交換"), ("coins", "pricetag", "handbag")),
    (("穿", "穿著", "戴", "披"), ("coat", "scarfi", "hat", "dress")),
    (("洗", "洗去", "擦", "抹"), ("soap", "bubblei", "handkerchief")),
    (("唱", "唱歌", "唱著歌", "哼", "歌唱"), ("mic", "notes", "musicsheet", "e_microphone")),
    (("說", "講", "告訴", "傾訴", "細訴", "談", "聊", "開口", "回答", "解釋", "訴", "訴說"), ("chatbubble", "e_megaphone", "ellipsis")),
    (("照", "照耀", "閃", "閃耀", "亮", "發光"), ("rays", "sparkles", "lightbulb", "spotlight")),
    (("落", "落下", "掉落", "墜", "沉", "沉沒", "滑落"), ("leaf", "feather", "raindrop", "arrowdown")),
    (("升起", "升", "飛翔", "飛舞", "高飛"), ("hotairballoon", "e_balloon", "arrowup", "kitei")),
    (("燒", "燃", "燃燒", "點燃"), ("flame", "firei", "candle", "matches")),
    (("冷卻", "凍", "凍結", "冰封", "結冰"), ("snowflake", "icecube", "icicle", "heartice")),
    (("嘆息", "嘆", "歎", "發呆", "呆"), ("ellipsis", "windi", "cloudi", "zzz")),
    (("輸", "贏", "失敗", "成功", "勝"), ("trophy", "medal", "flagrace", "crossmark")),
    (("回來", "歸來", "回家", "歸", "回去", "歸去", "返回"), ("house", "doorway", "footprints")),
    (("留下", "留", "留住", "挽留", "留在", "保留", "挽回"), ("anchori", "keyring", "heartlock")),
    (("吻", "親", "熱吻", "親吻"), ("lips", "lipstickmark", "twohearts")),
    (("打開", "推開", "敞開", "開啟"), ("doorway", "keyhole", "envelopeopen", "e_unlocked")),
    (("關上", "鎖上", "鎖", "封閉"), ("padlock", "e_locked", "door")),
    (("寫",), ("penpaper", "quill", "notebook")),
)

# how it is, when the line names no thing and nothing is done with a picture: (words, pictures)
HOWS: Tuple[Tuple[Tuple[str, ...], Tuple[str, ...]], ...] = (
    (("冷", "寒冷", "冰冷", "冰涼", "寒", "冷冷的", "寒風"), ("snowflake", "icicle", "e_cloud_with_snow", "heartice")),
    (("暖", "溫暖", "熱", "炎熱", "暖暖的", "溫熱"), ("sun", "rays", "campfire", "e_sun", "tea")),
    (("永遠", "永久", "永恆", "地久天長", "天長地久", "地老天荒", "一輩子", "一世", "永不"), ("infinity", "infinityheart", "ring", "hourglass")),
    (("長", "漫長", "久", "很久", "漫漫", "長久"), ("hourglass", "footpath", "clockwall", "calendari")),
    (("快", "匆匆", "匆忙", "急", "匆匆忙忙", "馬上", "立刻"), ("stopwatch", "windi", "hourhand", "shootingi")),
    (("早", "早已", "早就", "最初", "起初", "初次"), ("sunrise", "sunriseclock", "yesterday", "sprout")),
    (("新", "新鮮", "嶄新"), ("sprout", "gift", "sparkles", "sunrise")),
    (("舊", "老", "依舊", "仍舊", "古老", "陳舊"), ("phoneold", "radioold", "gramophone", "photo", "clockwall")),
    (("紅", "紅色", "火紅", "鮮紅"), ("rose", "hearti", "lanternred", "mapleleaf")),
    (("藍", "藍色", "湛藍"), ("wave", "droplet", "whale", "e_water_wave")),
    (("白", "蒼白", "潔白", "白色", "雪白"), ("snowflake", "feather", "cloudi", "dove")),
    (("綠", "綠色", "青"), ("leaf", "sprout", "clover3", "fern")),
    (("金色", "黃", "金黃", "昏黃"), ("sunflower", "ginkgoleaf", "star5", "sun")),
    (("茫茫", "朦朧", "模糊", "迷濛", "迷蒙", "朦朦朧朧", "隱約"), ("fog", "cloudi", "e_fog", "windowi")),
    (("自由", "逍遙", "自在", "輕鬆"), ("dove", "kitei", "feather", "e_balloon")),
    (("簡單", "平凡", "平常", "平淡", "單純", "純真"), ("daisy", "sprout", "cup", "circle")),
    (("神秘", "奇怪", "奇妙", "神奇", "稀奇"), ("crystalball", "keyhole", "question", "maski")),
    (("安全", "安穩", "平安"), ("shieldi", "umbrellai", "house")),
    (("不停", "不斷", "一再", "再次", "再度", "重複", "反覆", "常常", "時常", "經常", "始終"), ("infinity", "hourhand", "season", "clockwall")),
    (("到處", "四處", "處處", "隨處"), ("compassrose", "footprints", "maproll")),
    (("偶爾", "偶然", "碰巧", "恰好"), ("dice", "clover3", "shootingi")),
    (("無聲", "無言", "沉默", "默然", "無語", "安靜"), ("ellipsis", "zzz", "e_fallen_leaf")),
    (("真心", "真實", "真正", "真誠", "誠懇", "坦白", "真"), ("hearti", "handshake", "mirror")),
    (("深", "深深", "深處", "深刻"), ("anchori", "keyhole", "whale")),
    (("高", "高高", "最高"), ("summit", "hotairballoon", "kitei", "arrowup")),
    (("重", "沉重", "沈重"), ("anchori", "dumbbell", "stone")),
    (("輕", "輕盈", "輕輕"), ("feather", "dandelionseed", "bubblei")),
    (("甜", "甜蜜", "甜美"), ("candy", "honey", "lollipop", "cupcake")),
    (("苦", "苦澀", "酸"), ("coffee", "lemon", "pill", "tea")),
    (("美麗", "美", "漂亮", "最美", "迷人", "動人", "燦爛", "璀璨", "繽紛"), ("rose", "sparkles", "butterfly", "bouquet", "e_glowing_star")),
    (("瘋狂", "瘋癲", "瘋", "狂"), ("dizzy", "tornado", "lightning")),
)

# ------------------------------------------------------------------------------------------ people's stance
# (words, how the people stand). Whole words of the line, or two characters and more anywhere in it.
POSES: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("朋友", "知己", "伴侶", "情人", "戀人", "情侶", "愛人", "女朋友", "男朋友", "相伴", "相隨", "相守", "互相", "一同", "共同", "陪伴著"), "duo_walk"),
    (("相見", "見面", "相逢", "重逢", "相聚", "團聚", "邂逅", "遇到", "遇上", "相識", "相會"), "duo_face"),
    (("分開", "別離", "分離", "決裂", "分手", "失散", "各自"), "duo_apart"),
    (("懷裡", "懷抱", "懷中", "臂彎", "胸膛", "相擁", "擁", "抱緊", "緊緊"), "duo_hug"),
    (("躲", "逃避", "躲藏", "閃避", "退縮"), "solo_crouch"),
    (("跳",), "solo_jump"),
    (("坐", "坐在"), "solo_sit"),
    (("站", "站在", "佇", "佇立"), "solo_front"),
    (("逃", "逃跑", "奔", "奔跑", "衝", "追", "追逐", "趕"), "solo_run"),
    (("離開", "走開", "遠走", "出走", "走了", "告別"), "solo_away"),
    (("跌倒", "跌", "倒下", "摔"), "solo_ground"),
    (("望", "凝望", "望著", "看著", "遠望", "仰望", "抬頭"), "solo_look"),
    (("低頭", "垂頭"), "solo_head"),
    (("祝福", "願", "但願", "許願"), "solo_pray"),
    (("感謝", "謝謝", "感激", "珍惜"), "solo_heart"),
    (("放棄", "放下", "放開", "放手", "張開", "敞開"), "solo_open"),
    (("留住", "挽留", "挽回", "伸手"), "solo_reach"),
    (("面對", "對抗", "抵抗", "堅強", "不怕"), "solo_hips"),
    (("發呆", "猶豫", "考慮", "猜", "懷疑", "想想"), "solo_think"),
)

# how far the card looks: (words, shot)
SHOTS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("遙遠", "遠", "遠遠", "遠處", "天涯", "很遠", "最遠", "遼闊", "廣闊", "無邊", "蒼茫"), "far"),
    (("臉", "臉龐", "臉上", "面容", "容顏", "表情", "模樣", "樣子", "近", "靠近", "貼近", "面前", "眼前"), "close"),
)

# the light of the card: (words, light)
LIGHTS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("黑暗", "漆黑", "黑", "暗", "晦暗", "灰暗", "陰暗", "深宵", "深夜", "天黑"), "night"),
    (("昏黃", "黃昏", "夕陽", "日落"), "sunset"),
    (("天明", "天亮", "清晨", "破曉", "黎明"), "dawn"),
)

# ------------------------------------------------------------------- other pictures for what the cards knew
VARY: Dict[str, Tuple[str, ...]] = {
    "hearts": ("hearts", "twohearts", "hearti", "heartwings", "infinityheart"),
    "stars": ("stars", "e_glowing_star", "constellation", "sparkles", "e_milky_way"),
    "shooting": ("shooting", "shootingi", "comet", "e_shooting_star"),
    "letter": ("letter", "envelope", "envelopeopen", "postcard", "e_envelope"),
    "plane": ("plane", "airplane", "e_small_airplane", "e_airplane_departure"),
    "birds": ("birds", "dove", "swallow", "e_bird"),
    "balloons": ("balloons", "e_balloon", "hotairballoon"),
    "clover": ("clover", "clover3", "e_four_leaf_clover"),
    "petals": ("petals", "cherryblossom", "e_cherry_blossom"),
    "leaves": ("leaves", "mapleleaf", "ginkgoleaf", "e_fallen_leaf", "leaf"),
    "lantern": ("lantern", "lanterni", "lanternred", "e_red_paper_lantern"),
    "fireflies": ("fireflies", "sparkles", "sparkle"),
    "frames": ("frames", "photoframe", "photo", "polaroid", "album"),
    "clock": ("clock", "clockwall", "alarmclock", "watch", "e_mantelpiece_clock"),
    "bubbles": ("bubbles", "bubblei", "e_bubbles"),
    "hourglass": ("hourglass", "sandglass", "e_hourglass_done"),
    "calendar": ("calendar", "calendari", "e_tear_off_calendar", "e_spiral_calendar"),
    "suitcase": ("suitcase", "suitcasei", "luggage", "backpack"),
    "phone": ("phone", "phoneold", "e_mobile_phone", "e_telephone"),
    "key": ("key", "keyring", "e_old_key", "keyhole"),
    "candle": ("candle", "candleholder", "candle3", "e_candle"),
    "ring": ("ring", "diamondring", "rings2", "e_ring"),
    "cranes": ("cranes", "cranebird"),
    "dandelion": ("dandelion", "dandelionseed"),
    "broken": ("broken", "brokenheart", "bandagedheart"),
    "wine": ("wine", "e_wine_glass", "cocktail", "champagne", "toast2"),
    "guitar": ("guitar", "e_guitar", "ukulele"),
    "camera": ("camera", "e_camera", "polaroid", "camerafilm"),
    "diary": ("diary", "notebook", "e_notebook_with_decorative_cover", "bookopen"),
    "footprints": ("footprints", "footprint", "footprintsand"),
    "door": ("door", "doorway", "e_door", "gate"),
    "raincloud": ("raincloud", "stormcloud", "e_cloud_with_rain"),
    "rays": ("rays", "sunrise", "e_sun_behind_cloud"),
    "fireworks": ("fireworks", "e_fireworks", "e_sparkler"),
    "paperboat": ("paperboat", "sailboat", "e_sailboat"),
    "cat": ("cat", "e_cat", "e_black_cat"),
    "thought": ("thought", "chatbubble", "ellipsis"),
    "dream": ("dream", "moonbed", "zzz"),
    "notes": ("notes", "e_musical_notes", "musicsheet", "e_musical_score"),
    "rose": ("rose", "e_rose", "bouquet", "tulip"),
    "sun": ("sun", "e_sun", "sunrise"),
    "pill": ("pill", "medicine", "potion", "e_pill"),
    "wall": ("wall", "fencei"),
    "globe": ("globe", "earth", "e_globe_showing_asia_australia"),
    "maze": ("maze", "crossroads", "compassrose"),
}
NOT_VARIED = ("umbrella", "bike", "thread", "wings", "tears", "dots", "ask", "call", "bigmoon", "rainbow", "kite", "none")


# ------------------------------------------------------------------------------------------------ reading
_TABLE: Dict[str, Any] = {}


def table(simple: Callable[[str], str], drawable: Callable[[str], bool]) -> Dict[str, Any]:
    """The lists above, in simplified characters, with only the pictures the cards can draw:
    {"pics": [(words, pictures, kind)], "poses": [(words, subject)], "shots": [...], "lights": [...], "vary": {...}}"""
    if _TABLE:
        return _TABLE
    pics = []
    for kind, rows in (("noun", NOUNS), ("verb", VERBS), ("how", HOWS)):
        for ws, ps in rows:
            ok = tuple(p for p in dict.fromkeys(ps) if drawable(p) and p not in NOT_VARIED)
            if ok:
                pics.append((tuple(dict.fromkeys(simple(w) for w in ws)), ok, kind))
    _TABLE.update(
        pics=pics,
        poses=[(tuple(simple(w) for w in ws), s) for ws, s in POSES],
        shots=[(tuple(simple(w) for w in ws), s) for ws, s in SHOTS],
        lights=[(tuple(simple(w) for w in ws), s) for ws, s in LIGHTS],
        vary={k: tuple(p for p in dict.fromkeys(v) if drawable(p)) for k, v in VARY.items() if drawable(k)})
    _TABLE["words"] = {w: kind for ws, _ps, kind in pics for w in ws}
    for name in ("poses", "shots", "lights"):
        for ws, _s in _TABLE[name]:
            for w in ws:
                _TABLE["words"].setdefault(w, name)
    return _TABLE


def words() -> List[Tuple[str, str]]:
    """Every word of the lists (traditional) with the kind of word it is, for the word splitter (cardgrammar)."""
    out = []
    for tag, rows in (("n", NOUNS), ("v", VERBS), ("a", HOWS), ("v", POSES), ("a", SHOTS), ("a", LIGHTS)):
        for ws, _what in rows:
            out.extend((w, tag) for w in ws)
    return out


def read(line: str, tokens: Sequence[str], tb: Dict[str, Any], says: Callable[[str, Sequence[str]], bool]) -> Dict[str, Any]:
    """What these lists find in a (simplified) line: {"pics": pictures, "kind": noun|verb|how, "subject", "shot",
    "light"}, each only when found. `tokens`: the line's whole words (simplified; empty without the word
    splitter, and then only words of two characters and more are found). Not after a no / never (`says`)."""
    toks = set(tokens)

    def has(ws: Sequence[str]) -> bool:
        return any((len(w) >= 2 or w in toks) and says(line, (w,)) for w in ws)
    out: Dict[str, Any] = {}
    for ws, ps, kind in tb["pics"]:
        if has(ws):
            out["pics"], out["kind"] = ps, kind
            break
    for key, name in (("subject", "poses"), ("shot", "shots"), ("light", "lights")):
        for ws, what in tb[name]:
            if has(ws):
                out[key] = what
                break
    return out
