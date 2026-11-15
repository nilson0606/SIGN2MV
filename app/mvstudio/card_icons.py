"""Small pictures for the standard picture cards: one line each in ICONS, drawn from a few shapes.

A line is  name|family|words|shapes.  The family says where the icon goes in a card: "sky" (large, in the
sky), "side" (on the ground beside the person), "hold" (in the hand), "bubble" (in a thought cloud over the
head), "rain" (many small ones in the air). The words are what a lyric line can say to get it (Chinese, and
English whole words). The shapes are drawn in a 100 x 100 box whose bottom middle is where the icon stands:
  e cx,cy rx ry C        an ellipse            r x0,y0 x1,y1 C [radius]   a box
  p x,y x,y ... C        a filled outline      l x,y x,y ... C width      a line
C is one letter of COLORS.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

COLORS = {"R": (226, 90, 90), "O": (240, 150, 80), "Y": (250, 214, 110), "G": (110, 186, 130), "B": (110, 160, 210),
          "V": (160, 132, 204), "P": (255, 150, 170), "W": (255, 255, 255), "K": (60, 62, 80), "N": (150, 110, 92),
          "S": (255, 224, 204), "C": (255, 246, 226), "T": (96, 170, 176), "L": (190, 226, 250), "A": (170, 176, 190),
          "D": (250, 206, 96)}

ICONS = """
rose|hold|玫瑰,rose|l 50,100 50,45 G 4;p 50,70 30,60 44,76 G;e 50,32 18 18 R;e 50,30 9 9 P
bouquet|hold|花束,鮮花,送花|p 30,100 70,100 60,55 40,55 C;e 36,40 13 13 P;e 62,40 13 13 Y;e 50,28 14 14 R;e 50,48 10 10 V
sunflower|side|向日葵|l 50,100 50,42 G 5;p 50,74 26,64 44,80 G;e 50,26 26 26 Y;e 50,26 12 12 N
cactus|side|仙人掌,帶刺|r 40,30 60,100 G 10;r 20,50 34,74 G 6;r 66,40 80,66 G 6;e 50,26 6 6 P
sprout|side|發芽,嫩芽,種子,新生,萌芽,seed|p 30,100 70,100 64,84 36,84 N;l 50,84 50,54 G 4;e 38,50 14 8 G;e 62,44 14 8 G
apple|hold|蘋果,apple|e 50,60 28 30 R;l 50,32 54,18 N 4;e 64,22 10 6 G
cake|side|蛋糕,cake|r 18,60 82,100 C 6;r 18,60 82,72 P 6;r 30,36 70,60 C 6;r 30,36 70,46 P 6;l 50,36 50,20 Y 4;e 50,14 5 7 O
gift|side|禮物,驚喜,gift,present,surprise|r 22,46 78,100 R 4;r 18,34 82,50 R 4;r 44,34 56,100 Y;e 38,26 12 8 Y;e 62,26 12 8 Y
candy|hold|糖果,甜蜜,candy,sugar|e 50,50 20 20 P;p 30,50 12,36 12,64 P;p 70,50 88,36 88,64 P;l 40,40 60,60 W 3
icecream|hold|冰淇淋,夏天,summer|p 34,54 66,54 50,100 Y;e 50,40 20 18 P;e 40,28 14 13 C;e 60,28 14 13 L
tea|hold|一杯茶,泡茶,熱茶,tea|r 28,50 68,90 W 8;e 48,50 20 6 N;l 68,58 82,64 68,76 W 5;l 40,40 44,26 A 3;l 54,40 58,24 A 3
beer|hold|啤酒,乾杯,cheers,beer|r 28,36 66,96 Y 6;r 28,26 66,42 W 8;l 66,48 84,54 84,74 66,80 W 6
bottle|side|瓶中信,漂流瓶,瓶子|r 36,34 64,100 L 12;r 44,14 56,36 L 4;r 42,8 58,16 N 3;r 42,56 58,84 C 2
pen|hold|鋼筆,寫字,簽名|p 20,84 16,96 28,92 K;p 20,84 28,92 82,30 74,22 B;p 74,22 82,30 90,18 84,12 D
palette|hold|畫畫,畫筆,顏色,色彩,彩色,paint,color,colors|e 50,56 38 28 C;e 34,48 7 7 R;e 50,40 7 7 Y;e 66,48 7 7 B;e 60,66 7 7 G;e 36,66 6 6 W
scissors|hold|剪刀,剪斷|l 30,20 62,70 A 5;l 70,20 38,70 A 5;e 34,82 10 10 R;e 66,82 10 10 R
bell|hold|鈴聲,鈴鐺,bell|p 26,74 74,74 66,36 50,22 34,36 D;r 22,72 78,82 D 4;e 50,88 7 7 N;e 50,18 5 5 D
watch|hold|手錶,分秒,秒針,一分一秒|r 40,6 60,94 N 4;e 50,50 24 24 W;l 50,50 50,34 K 3;l 50,50 62,54 K 3
mirror|hold|鏡子,鏡中,mirror|e 50,38 26 32 L;e 50,38 20 26 W;r 46,68 54,100 N 3
perfume|side|香水,香味,氣味,味道|r 30,46 70,100 P 8;r 42,28 58,46 D 3;e 50,22 8 6 D;l 62,24 78,16 A 2
lipstick|hold|口紅,化妝|r 38,56 62,100 K 3;r 40,40 60,58 D 2;p 42,40 58,40 58,18 42,28 R
glasses|hold|眼鏡|e 30,50 18 16 L;e 70,50 18 16 L;l 46,48 54,48 K 4;l 12,48 4,40 K 3;l 88,48 96,40 K 3
hat|hold|帽子,hat|e 50,72 44 10 N;p 26,72 74,72 68,34 32,34 N;r 28,60 72,70 R 2
scarfi|hold|圍巾,scarf|r 20,40 80,58 R 8;r 56,54 72,96 R 4;l 58,90 58,98 R 3;l 66,90 66,98 R 3
glove|hold|手套,牽起|r 30,40 66,96 R 10;r 30,16 40,48 R 5;r 42,10 52,48 R 5;r 54,14 64,48 R 5;r 64,46 80,62 R 6;r 30,84 66,96 W 4
shoe|side|鞋子,高跟鞋,球鞋,舞鞋|p 10,96 90,96 90,80 60,72 44,48 22,48 20,80 R;r 10,90 90,98 W 3;l 34,58 50,66 W 3
bag|side|背包,書包,行囊|r 24,36 76,100 B 12;r 34,62 66,90 L 6;l 38,36 38,18 62,18 62,36 K 5
ticket|hold|車票,門票,票根,ticket|r 10,34 90,74 C 4;l 66,36 66,72 A 2;r 18,44 56,50 R;r 18,56 46,62 A;e 78,54 6 6 R
passport|hold|護照,出國,異鄉,他鄉|r 28,16 72,96 B 5;e 50,48 14 14 D;l 36,48 64,48 B 2;r 38,74 62,80 D
map|hold|地圖,map|p 10,26 36,16 64,26 90,16 90,82 64,92 36,82 10,92 C;l 36,16 36,82 A 2;l 64,26 64,92 A 2;l 20,70 40,50 60,62 80,36 R 3;e 80,36 5 5 R
compass|hold|指南針,羅盤,compass|e 50,54 36 36 D;e 50,54 28 28 W;p 50,30 58,54 42,54 R;p 50,78 58,54 42,54 K;e 50,12 6 6 D
globe|side|地球,世界,全世界,world|e 50,48 34 34 B;p 34,30 52,26 56,44 40,52 G;p 58,56 74,50 70,70 56,72 G;l 50,82 50,94 N 5;r 30,92 70,100 N 4
anchor|side|船錨,停泊,靠岸,anchor|e 50,18 9 9 A;l 50,26 50,90 A 6;l 30,42 70,42 A 5;l 16,66 30,86 50,92 70,86 84,66 A 6
rocket|sky|火箭,太空,rocket,space|p 50,6 68,36 68,74 32,74 32,36 W;e 50,42 9 9 L;p 32,60 16,84 32,76 R;p 68,60 84,84 68,76 R;p 40,74 60,74 50,98 O
ufo|sky|飛碟,外星,ufo|e 50,44 20 16 L;e 50,56 44 12 A;e 28,58 4 4 Y;e 50,62 4 4 Y;e 72,58 4 4 Y;p 34,66 66,66 80,98 20,98 Y
planet|sky|行星,土星,星系,planet|e 50,50 26 26 O;l 8,62 92,38 Y 5;e 42,44 8 6 Y
earth|sky|地球上,這世界,earth|e 50,50 36 36 B;p 30,30 52,26 58,46 38,56 G;p 60,58 78,52 72,74 58,76 G;e 30,70 8 6 G
comet|sky|彗星,劃過,comet|e 70,34 12 12 Y;p 62,28 10,84 16,90 70,46 Y;p 66,40 30,90 38,92 76,42 C
lightning|sky|閃電,打雷,雷聲,thunder,lightning|e 40,30 26 18 A;e 62,34 22 16 A;p 52,44 34,72 48,72 40,98 68,62 54,62 62,44 Y
snowflake|rain|雪花,飄雪,snowflake|l 50,10 50,90 W 5;l 15,30 85,70 W 5;l 15,70 85,30 W 5;e 50,50 8 8 L
raindrop|rain|雨滴,滴答,一滴|p 50,10 74,60 50,90 26,60 L;e 42,62 6 9 W
feather|rain|羽毛,輕輕,feather|p 20,90 30,50 60,16 84,14 80,40 50,70 W;l 20,90 80,20 A 3
leaf|rain|葉子,綠葉,樹葉,leaf|p 16,84 26,40 64,16 86,16 82,40 56,74 G;l 16,84 80,22 N 3
flame|side|火焰,燃燒,熱情,烈火,fire,burn|p 50,6 72,44 78,70 64,96 36,96 22,70 34,40 O;p 50,40 62,66 58,92 42,92 38,66 Y
wave|side|浪花,海浪,潮,tide|p 4,100 4,60 24,36 46,40 40,56 58,60 64,44 84,50 96,70 96,100 B;p 24,36 46,40 40,56 30,52 W
island|sky|島,小島,孤島,island|p 14,70 86,70 70,84 30,84 Y;l 50,70 54,34 N 5;p 54,34 30,30 40,44 G;p 54,34 78,28 70,44 G;p 54,34 52,16 64,28 G
iceberg|side|冰山,冰冷,冷漠,cold,ice|p 14,100 28,50 44,64 54,26 72,58 86,100 L;p 54,26 60,44 50,52 W
volcano|sky|火山,爆發|p 10,96 38,36 62,36 90,96 N;p 38,36 62,36 56,50 50,42 44,52 O;e 50,22 12 10 A;e 62,12 8 7 A
tornado|sky|龍捲風,風暴,暴風,storm|p 14,14 86,14 76,30 24,30 A;p 26,34 74,34 64,50 36,50 A;p 38,54 64,54 56,70 44,70 A;p 46,74 58,74 52,96 A
sunrise|sky|日出,朝陽,黎明,sunrise|e 50,70 28 28 Y;r 0,70 100,100 O;l 50,30 50,16 Y 4;l 20,46 10,36 Y 4;l 80,46 90,36 Y 4
house|bubble|房子,家門,回家,家裡|r 24,50 76,96 C 3;p 14,52 50,18 86,52 R;r 44,68 58,96 N 2;r 62,60 72,70 L 2
bed|side|床上,被窩,睡不著,失眠,bed|r 10,60 90,84 C 4;r 6,36 16,96 N 3;r 84,56 94,96 N 3;r 18,48 40,62 W 6;r 40,58 90,74 B 4
sofa|side|沙發,客廳,sofa|r 14,40 86,80 T 10;r 6,56 22,90 T 8;r 78,56 94,90 T 8;r 20,66 80,88 T 6;r 22,88 28,98 N;r 72,88 78,98 N
chair|side|椅子,空位,座位,chair|r 28,10 36,96 N 3;r 28,10 70,18 N 3;r 28,52 72,62 N 3;r 64,58 72,96 N 3;l 44,18 44,52 N 3;l 56,18 56,52 N 3
lampi|side|檯燈,燈下,夜燈,lamp|p 30,40 70,40 60,12 40,12 Y;l 50,40 50,86 A 4;r 34,86 66,96 A 4
bulb|bubble|靈感,點子,想到,idea|e 50,42 26 26 Y;r 40,64 60,84 A 4;l 50,6 50,0 Y 3;l 18,16 12,10 Y 3;l 82,16 88,10 Y 3
tv|side|電視,螢幕,節目|r 10,26 90,84 K 6;r 18,34 82,76 L 3;l 36,10 50,26 64,10 K 3;r 30,84 70,92 K 3
computer|side|電腦,鍵盤,上網,網路|r 18,20 82,70 K 5;r 24,26 76,64 L 2;p 8,96 92,96 82,76 18,76 A
radio|side|收音機,電台,頻率|r 12,40 88,92 N 8;e 34,66 16 16 K;r 56,54 80,62 C;r 56,70 80,78 C;l 70,40 86,10 A 3
record|hold|唱片,黑膠,老歌,旋轉|e 50,50 42 42 K;e 50,50 30 30 K;e 50,50 14 14 R;e 50,50 3 3 W
cassette|hold|卡帶,錄音帶,錄音|r 8,26 92,78 K 6;r 20,36 80,62 C 4;e 36,50 8 8 K;e 64,50 8 8 K;p 26,78 74,78 68,66 32,66 A
mic|hold|麥克風,唱歌,歌唱,sing,singing|e 50,26 18 22 A;r 44,46 56,96 K 4;l 34,30 66,30 K 2;l 36,20 64,20 K 2
headphones|hold|耳機,聽歌,headphones|l 20,60 20,40 50,14 80,40 80,60 K 6;r 10,54 28,86 R 6;r 72,54 90,86 R 6
drum|side|打鼓,鼓聲,心跳聲,節拍,節奏,beat|r 18,44 82,90 R 6;e 50,44 32 10 C;l 26,50 38,88 Y 3;l 50,54 62,90 Y 3;l 74,50 62,88 Y 3;l 10,10 40,40 N 4;l 90,10 60,40 N 4
violin|hold|小提琴,提琴,violin|e 50,70 22 24 N;e 50,44 16 16 N;r 46,4 54,34 K 2;l 50,34 50,86 C 2;l 20,96 90,20 C 2
trumpet|hold|號角,小號,喇叭|p 60,34 92,16 92,74 60,56 D;r 16,40 62,50 D 4;r 26,50 34,66 D 3;r 38,50 46,66 D 3;e 14,45 6 8 D
book|hold|書本,一本書,翻開,閱讀,read|p 10,28 50,36 50,90 10,82 C;p 90,28 50,36 50,90 90,82 C;l 18,44 42,50 A 2;l 18,56 42,62 A 2;l 58,50 82,44 A 2;l 58,62 82,56 A 2
newspaper|hold|報紙,新聞,消息,news|r 14,16 86,90 C 3;r 22,24 78,36 K;r 22,44 48,66 A;l 54,46 78,46 A 3;l 54,56 78,56 A 3;l 22,76 78,76 A 3
envelope|hold|信封,寄信,來信,回信|r 10,28 90,80 C 4;l 10,30 50,60 90,30 A 3;e 50,62 7 7 R
stamp|hold|郵票,郵戳,明信片,postcard|r 12,22 88,82 C 3;r 60,30 80,52 R 2;l 20,40 50,40 A 3;l 20,52 50,52 A 3;l 20,64 44,64 A 3
photo|hold|相片,合照,拍立得,photograph|r 18,12 82,92 W 3;r 24,18 76,68 L 2;e 62,32 8 8 Y;p 24,68 44,44 60,68 G
filmi|hold|電影,影片,劇情,結局,movie,film|r 14,10 86,90 K 4;r 28,18 72,42 L 2;r 28,50 72,74 L 2;r 18,16 24,24 W;r 18,34 24,42 W;r 18,52 24,60 W;r 76,16 82,24 W;r 76,34 82,42 W;r 76,52 82,60 W
teddy|side|泰迪,玩偶,娃娃,布偶,玩具,toy|e 50,70 26 28 N;e 50,34 22 20 N;e 32,18 9 9 N;e 68,18 9 9 N;e 50,40 8 6 C;e 42,30 3 3 K;e 58,30 3 3 K
pillow|side|枕頭,枕邊|r 12,50 88,92 W 16;l 24,64 76,64 L 2
kettle|side|水壺,燒開水|p 22,90 78,90 70,44 30,44 A;p 70,52 92,40 90,50 74,64 A;l 34,44 50,24 66,44 K 4;l 40,30 36,14 W 3
noodle|side|泡麵,一碗麵,宵夜,noodles|p 14,56 86,56 72,96 28,96 R;e 50,56 36 9 C;l 38,54 34,22 N 3;l 48,54 50,20 N 3;l 30,40 26,30 W 3
rice|side|晚餐,餐桌,吃飯,dinner|p 16,58 84,58 72,96 28,96 L;e 50,56 34 16 W;l 70,30 90,8 N 3;l 76,34 96,14 N 3
bread|hold|麵包,早餐,breakfast|r 16,44 84,90 O 14;e 34,42 16 14 O;e 62,40 18 15 O;l 34,56 34,80 N 2;l 50,56 50,80 N 2;l 66,56 66,80 N 2
milk|hold|牛奶,milk|p 30,34 70,34 70,96 30,96 W;p 30,34 50,14 70,34 L;r 36,54 64,76 B 3
cookie|hold|餅乾,cookie|e 50,54 36 36 O;e 36,44 5 5 N;e 60,40 5 5 N;e 50,62 5 5 N;e 66,66 5 5 N;e 34,68 5 5 N
fish|side|魚,fish|e 46,54 32 20 O;p 74,54 94,36 94,72 O;e 30,48 4 4 K;l 46,40 54,54 46,68 W 2
whale|sky|鯨魚,鯨,whale|p 8,56 20,36 60,32 84,50 80,70 30,76 B;p 80,54 96,36 96,66 B;p 20,66 60,72 30,76 W;e 26,50 3 3 K;l 44,32 40,14 L 3;l 44,32 52,16 L 3
dolphin|sky|海豚,dolphin|p 8,60 30,36 62,34 90,58 62,58 40,70 B;p 50,36 60,18 64,38 B;p 86,54 98,44 96,66 B;e 24,50 3 3 K
turtle|side|烏龜,turtle|e 50,66 34 20 G;e 86,62 10 9 G;r 24,82 34,96 G 3;r 62,82 72,96 G 3;l 34,54 50,78 N 2;l 66,54 50,78 N 2
rabbit|side|兔,兔子,rabbit|e 50,74 24 24 W;e 50,42 18 17 W;r 38,6 46,34 W 4;r 54,6 62,34 W 4;e 44,40 3 3 K;e 56,40 3 3 K;e 50,48 3 2 P
dog|side|狗,小狗,dog|e 50,72 26 24 N;e 50,40 20 18 N;p 30,30 26,56 38,44 K;p 70,30 74,56 62,44 K;e 43,38 3 3 K;e 57,38 3 3 K;e 50,48 5 4 K
bear|side|熊,小熊,bear|e 50,70 30 28 N;e 50,36 22 20 N;e 32,20 8 8 N;e 68,20 8 8 N;e 50,42 9 7 C;e 50,40 3 2 K
fox|side|狐狸,fox|p 30,96 70,96 64,56 36,56 O;p 30,56 70,56 50,84 O;p 30,56 34,26 50,44 O;p 70,56 66,26 50,44 O;e 42,60 3 3 K;e 58,60 3 3 K;p 44,72 56,72 50,84 W
deer|side|鹿,deer|e 50,70 22 22 N;e 50,40 14 14 N;l 42,28 34,8 N 3;l 34,16 26,14 N 3;l 58,28 66,8 N 3;l 66,16 74,14 N 3;e 50,46 4 3 K
horse|side|駿馬,白馬,奔馳,騎馬,horse|p 20,60 70,56 78,96 68,96 62,74 34,74 30,96 20,96 N;p 62,58 74,26 88,30 92,44 78,48 N;p 66,34 60,56 70,50 K
sheep|side|羊,綿羊,數羊,sheep|e 50,60 30 24 W;e 30,50 12 12 W;e 66,46 12 12 W;e 48,44 12 12 W;e 22,62 10 9 K;r 36,80 42,96 K 2;r 58,80 64,96 K 2
owl|side|貓頭鷹,深夜裡,owl|e 50,58 28 34 N;e 38,44 11 11 W;e 62,44 11 11 W;e 38,44 4 4 K;e 62,44 4 4 K;p 46,54 54,54 50,62 Y;p 28,28 34,14 42,28 N;p 72,28 66,14 58,28 N
swan|side|天鵝,swan|e 54,74 30 18 W;l 30,70 22,40 34,22 46,28 W 8;p 46,26 58,30 46,34 O
penguin|side|企鵝,penguin|e 50,60 26 36 K;e 50,66 16 26 W;p 44,40 56,40 50,48 O;e 42,34 3 3 W;e 58,34 3 3 W;e 40,96 9 4 O;e 60,96 9 4 O
bee|rain|蜜蜂,蜂,bee|e 50,54 22 16 Y;l 42,40 42,68 K 4;l 54,40 54,68 K 4;e 40,34 12 9 W;e 60,34 12 9 W
ladybug|rain|瓢蟲|e 50,54 24 22 R;l 50,32 50,76 K 2;e 40,48 4 4 K;e 60,48 4 4 K;e 42,64 4 4 K;e 58,64 4 4 K;e 50,30 9 7 K
snail|side|蝸牛,緩慢,snail|e 56,60 24 24 N;e 56,60 12 12 C;p 10,96 86,96 80,84 22,82 C;l 18,82 12,62 C 3;l 26,82 24,60 C 3
web|sky|蜘蛛網,蜘蛛,困住,trapped|l 50,6 50,94 A 2;l 6,50 94,50 A 2;l 18,18 82,82 A 2;l 18,82 82,18 A 2;l 50,24 76,50 50,76 24,50 50,24 A 2;l 50,38 62,50 50,62 38,50 50,38 A 2
dragonfly|rain|蜻蜓|l 20,56 84,48 K 4;e 44,40 20 7 L;e 44,66 20 7 L;e 86,48 5 5 K
nest|side|鳥巢,巢,歸巢|p 14,60 86,60 72,92 28,92 N;e 36,56 9 11 C;e 52,54 9 11 L;e 66,56 9 11 C
egg|hold|雞蛋,破殼,孵|p 50,10 76,54 66,88 34,88 24,54 C;l 30,52 40,44 50,54 60,44 70,52 A 3
cage|side|籠子,牢籠,囚禁,束縛,cage|r 20,24 80,92 A 8;l 32,26 32,90 K 2;l 44,26 44,90 K 2;l 56,26 56,90 K 2;l 68,26 68,90 K 2;l 50,24 50,10 K 3;e 50,60 8 7 Y
chain|hold|鎖鏈,枷鎖,綁住,chain|e 24,30 14 10 A;e 44,46 14 10 A;e 62,62 14 10 A;e 80,78 14 10 A
crown|bubble|皇冠,王冠,女王,國王,crown,king,queen|p 14,84 86,84 92,30 68,56 50,20 32,56 8,30 D;e 50,72 6 6 R;e 28,74 4 4 B;e 72,74 4 4 B
sword|hold|劍,戰鬥,奮戰,fight,sword|p 46,58 54,58 54,14 50,4 46,14 A;r 32,58 68,66 D 3;r 46,66 54,90 N 2;e 50,94 6 6 D
shieldi|hold|盾牌,守護,保護,protect|p 50,8 84,22 80,60 50,94 20,60 16,22 B;p 50,22 70,30 68,56 50,78 W;l 50,22 50,78 B 3
wand|hold|魔法,魔杖,咒語,magic|l 22,90 70,30 K 5;p 74,6 80,22 96,24 84,34 88,50 74,42 60,50 64,34 52,24 68,22 Y
crystal|side|水晶球,預言,占卜,未知|e 50,46 30 30 V;e 40,36 8 10 W;p 26,96 74,96 66,74 34,74 N
dice|hold|骰子,賭注,運氣,dice|r 16,20 84,88 W 10;e 34,38 6 6 K;e 66,38 6 6 K;e 50,54 6 6 R;e 34,70 6 6 K;e 66,70 6 6 K
cards|hold|撲克,紙牌,王牌|r 14,24 58,88 W 5;r 40,14 86,80 W 5;e 63,40 7 7 R;p 56,44 70,44 63,58 R
chess|side|棋子,棋局,對弈|e 50,24 12 12 K;p 40,34 60,34 66,84 34,84 K;r 26,84 74,96 K 4
coin|hold|硬幣,金錢,money|e 50,50 36 36 D;e 50,50 28 28 Y;l 50,32 50,68 D 4;l 40,42 60,42 D 3
diamond|bubble|鑽石,寶石,珍貴,閃耀,diamond|p 26,34 74,34 90,52 50,94 10,52 L;p 26,34 38,52 10,52 W;p 74,34 62,52 90,52 W;l 38,52 50,94 62,52 A 2
treasure|side|寶藏,寶物,treasure|r 14,50 86,96 N 4;p 14,50 22,26 78,26 86,50 N;r 44,44 56,62 D 2;e 34,40 6 6 Y;e 66,40 6 6 Y;l 14,72 86,72 D 3
trophy|hold|獎盃,冠軍,勝利,贏,win|p 28,14 72,14 66,52 34,52 D;l 28,22 12,24 16,42 32,42 D 4;l 72,22 88,24 84,42 68,42 D 4;r 46,52 54,76 D;r 30,76 70,90 N 3
medal|hold|獎牌,榮耀,驕傲,proud|p 34,6 46,6 54,44 42,44 R;p 66,6 54,6 46,44 58,44 B;e 50,66 24 24 D;p 50,52 54,62 64,62 56,70 60,80 50,74 40,80 44,70 36,62 46,62 Y
flag|side|旗幟,終點,目標,goal|l 26,8 26,98 N 5;p 28,10 84,24 28,44 R
target|sky|靶心,瞄準,命中|e 50,50 42 42 R;e 50,50 30 30 W;e 50,50 18 18 R;e 50,50 7 7 W;l 50,50 86,14 K 3
puzzle|hold|拼圖,缺了一塊,完整,puzzle|r 12,30 60,78 B 4;e 60,54 10 10 B;r 64,30 88,78 Y 4;e 38,30 9 9 Y
maze|bubble|迷宮,出口,找不到路|r 10,10 90,90 C 2;l 10,30 70,30 K 3;l 30,50 90,50 K 3;l 10,70 60,70 K 3;l 70,30 70,50 K 3;l 30,50 30,70 K 3
ladder|side|梯子,往上爬,攀,climb|l 30,4 30,98 N 5;l 68,4 68,98 N 5;l 30,20 68,20 N 4;l 30,40 68,40 N 4;l 30,60 68,60 N 4;l 30,80 68,80 N 4
rope|hold|繩,打結,解不開,心結,knot|l 6,50 30,50 N 6;l 70,50 94,50 N 6;e 42,50 14 12 N;e 58,50 14 12 N
eraser|hold|擦掉,抹去,塗掉,erase|p 20,70 54,24 82,44 48,90 P;p 20,70 34,52 62,72 48,90 W;l 14,96 70,96 A 3
trash|side|丟掉,扔掉,垃圾,不要了|p 24,34 76,34 70,96 30,96 A;r 18,24 82,34 A 3;r 42,14 58,24 A 2;l 40,44 42,86 K 2;l 60,44 58,86 K 2
scale|side|天秤,公平,衡量,選擇題,balance|l 50,14 50,90 A 5;l 16,26 84,26 A 4;p 6,54 26,54 16,30 D;p 74,60 94,60 84,30 D;r 30,88 70,96 A 3
stopsign|side|停止,別走,stop|p 34,10 66,10 88,32 88,64 66,86 34,86 12,64 12,32 R;r 28,42 72,54 W 2;r 46,86 54,100 A
arrowup|sky|向上,成長,長大後,進步,grow|p 50,8 84,46 62,46 62,92 38,92 38,46 16,46 G
summit|sky|山頂,頂峰,巔峰,高峰,peak|p 6,94 44,24 62,54 72,40 96,94 A;p 44,24 54,42 36,42 W;l 44,24 44,6 K 3;p 44,6 62,12 44,18 R
bandaid|hold|傷口,癒合,療傷,復原,heal|p 16,64 64,16 84,36 36,84 S;r 40,40 60,60 C 3;e 26,68 2 2 N;e 72,30 2 2 N
pill|hold|解藥,良藥,吃藥,medicine|p 24,60 60,24 78,42 42,78 R;p 42,78 24,60 16,70 30,86 W
thermo|hold|發燒,溫度,體溫,fever|r 44,8 56,70 W 6;e 50,80 14 14 R;r 47,36 53,74 R 2
heartbeat|sky|心跳,脈搏,心電|l 4,54 26,54 34,30 46,78 56,40 64,54 96,54 R 5
infinity|bubble|無限,無盡,永恆,infinity|e 32,50 20 16 V;e 68,50 20 16 V;e 32,50 10 7 W;e 68,50 10 7 W
dove|sky|鴿子,和平,白鴿,peace,dove|p 20,56 44,40 70,44 86,34 80,54 60,66 34,66 W;p 46,42 40,14 66,40 W;p 20,56 6,50 16,62 O;e 26,52 2 2 K
mask|hold|面具,偽裝,假裝,演戲,pretend|p 14,24 86,24 80,66 50,90 20,66 W;e 34,44 9 6 K;e 66,44 9 6 K;l 36,66 50,74 64,66 K 3
zzz|bubble|睡著,入睡,晚安,goodnight|l 20,24 44,24 20,48 44,48 B 5;l 52,44 70,44 52,62 70,62 B 4;l 74,62 86,62 74,74 86,74 B 3
sparkle|rain|閃亮,閃爍,發光,閃閃,shine,sparkle|p 50,4 58,42 96,50 58,58 50,96 42,58 4,50 42,42 Y
angry|bubble|生氣,憤怒,吵架,爭吵,angry|l 34,14 42,34 22,42 R 6;l 66,14 58,34 78,42 R 6;l 34,86 42,66 22,58 R 6;l 66,86 58,66 78,58 R 6
sweat|bubble|緊張,不安,尷尬,nervous|p 50,10 76,58 50,92 24,58 L;e 42,60 6 10 W
xmas|side|聖誕樹,聖誕節,平安夜|p 50,6 74,40 26,40 G;p 50,26 82,66 18,66 G;p 50,50 90,90 10,90 G;r 44,90 56,100 N;e 50,6 5 5 Y;e 38,56 4 4 R;e 62,74 4 4 Y;e 34,82 4 4 B
pumpkin|side|南瓜,萬聖|e 50,62 36 30 O;e 30,62 14 28 O;e 70,62 14 28 O;r 46,22 54,36 G 2;p 34,54 46,54 40,44 K;p 54,54 66,54 60,44 K;p 36,70 64,70 50,82 K
firecracker|side|鞭炮,過年,新春,春節|r 40,30 60,96 R 4;r 40,40 60,48 Y;r 40,78 60,86 Y;l 50,30 56,12 K 3;e 58,8 5 5 O
snowglobe|side|雪球,水晶雪球|e 50,44 32 32 L;p 26,96 74,96 68,76 32,76 N;p 50,34 62,60 38,60 G;e 36,36 3 3 W;e 62,30 3 3 W;e 58,50 3 3 W
umbrellai|sky|遮風,擋雨,避風港,shelter|p 6,54 50,10 94,54 P;l 50,12 50,86 N 4;l 50,86 42,92 36,86 N 4
bus|side|公車上,末班車,校車|r 6,26 94,84 Y 8;r 14,36 34,56 L 3;r 40,36 60,56 L 3;r 66,36 86,56 L 3;e 26,86 9 9 K;e 74,86 9 9 K
taxi|side|計程車,計程,taxi|r 8,50 92,84 Y 8;p 24,50 34,28 66,28 76,50 Y;r 36,34 64,48 L 2;r 42,18 58,28 K 2;e 28,86 9 9 K;e 72,86 9 9 K
scooter|side|機車,摩托車,後座|e 22,80 14 14 K;e 78,80 14 14 K;p 22,74 44,74 54,50 70,50 78,74 60,74 R;l 66,50 62,26 K 4;l 54,26 70,26 K 4;r 34,56 52,64 K 3
skateboard|side|滑板|r 10,66 90,74 O 4;e 26,84 8 8 K;e 74,84 8 8 K
ball|side|足球,踢球,球場,操場|e 50,60 34 34 W;p 50,44 62,54 58,68 42,68 38,54 K;l 50,44 50,28 K 2;l 62,54 80,48 K 2;l 38,54 20,48 K 2
basketball|side|籃球,投籃,basketball|e 50,58 36 36 O;l 50,22 50,94 K 2;l 14,58 86,58 K 2;l 24,34 40,58 24,82 K 2;l 76,34 60,58 76,82 K 2
tent|side|野營,紮營|p 10,94 50,20 90,94 O;p 40,94 50,58 60,94 K
luggage|side|行囊,包袱,重擔,負擔,burden|r 22,30 78,96 N 8;l 38,30 38,14 62,14 62,30 K 5;l 22,52 78,52 K 3;l 22,74 78,74 K 3
keyhole|bubble|鑰匙孔,心鎖,上鎖,locked|r 22,40 78,94 D 8;l 34,40 34,22 66,22 66,40 A 7;e 50,60 8 8 K;p 46,62 54,62 56,80 44,80 K
wall|side|一道牆,高牆,隔閡,距離,隔著,wall,distance|r 6,20 94,96 O 2;l 6,39 94,39 C 2;l 6,58 94,58 C 2;l 6,77 94,77 C 2;l 36,20 36,39 C 2;l 66,39 66,58 C 2;l 30,58 30,77 C 2;l 60,77 60,96 C 2
bridgei|bubble|橋樑,連結,牽絆,connect|l 4,60 96,60 N 6;l 4,60 4,92 N 5;l 96,60 96,92 N 5;l 10,58 30,30 50,22 70,30 90,58 N 4;l 30,30 30,60 N 2;l 50,22 50,60 N 2;l 70,30 70,60 N 2
roots|side|扎根,根源,生根|l 50,4 50,40 N 8;l 50,40 30,60 16,88 N 5;l 50,40 50,96 N 5;l 50,40 70,60 84,88 N 5;l 30,60 40,84 N 3;l 70,60 60,84 N 3
hourhand|bubble|等待,等候,等了|e 50,50 40 40 W;l 50,50 50,22 K 5;l 50,50 70,60 K 4;e 50,50 4 4 R;l 50,14 50,18 K 3;l 86,50 82,50 K 3;l 50,86 50,82 K 3;l 14,50 18,50 K 3
thumbs|bubble|加油,支持,鼓勵,cheer|r 14,48 30,90 B 4;p 30,50 44,46 52,16 64,20 60,44 84,44 84,88 30,88 S
handshake|bubble|約定,說好,答應,勾勾手,約好|p 6,40 40,34 58,50 44,66 6,62 B;p 94,40 60,34 42,50 56,66 94,62 R;e 50,50 12 10 S
footpath|sky|旅途,旅程,路途,journey|p 40,96 60,96 54,60 46,60 A;p 46,56 54,56 52,36 48,36 A;p 48,32 52,32 51,18 49,18 A;e 50,10 6 6 Y
stormcloud|sky|暴雨,大雨,傾盆|e 34,36 24 18 A;e 62,32 26 20 A;r 20,36 84,56 A 10;l 30,62 24,84 L 4;l 46,62 40,90 L 4;l 62,62 56,84 L 4;l 76,62 70,90 L 4
moonbed|sky|月牙,彎月,新月,crescent|e 50,50 36 36 Y;e 64,40 32 32 K
shootingi|bubble|心願,許個願,許願|p 50,8 60,38 92,40 66,58 76,90 50,70 24,90 34,58 8,40 40,38 Y
""".strip()

FAMILIES = ("sky", "side", "hold", "bubble", "rain")


def _load() -> Dict[str, Tuple[str, Tuple[str, ...], List[tuple]]]:
    out: Dict[str, Tuple[str, Tuple[str, ...], List[tuple]]] = {}
    for line in ICONS.splitlines():
        name, fam, words, shapes = line.split("|")
        assert fam in FAMILIES and name not in out, line
        prims: List[tuple] = []
        for sh in shapes.split(";"):
            t = sh.split()
            if t[0] == "e":
                cx, cy = t[1].split(",")
                prims.append(("e", float(cx), float(cy), float(t[2]), float(t[3]), COLORS[t[4]]))
            elif t[0] == "r":
                (x0, y0), (x1, y1) = t[1].split(","), t[2].split(",")
                prims.append(("r", float(x0), float(y0), float(x1), float(y1), COLORS[t[3]], float(t[4]) if len(t) > 4 else 0.0))
            elif t[0] == "p":
                prims.append(("p", [tuple(float(v) for v in q.split(",")) for q in t[1:-1]], COLORS[t[-1]]))
            elif t[0] == "l":
                prims.append(("l", [tuple(float(v) for v in q.split(",")) for q in t[1:-2]], COLORS[t[-2]], float(t[-1])))
            else:
                raise ValueError(line)
        out[name] = (fam, tuple(w for w in words.split(",") if w), prims)
    return out


TABLE = _load()
NAMES = tuple(TABLE)


def draw_icon(k, name: str, x: float, y: float, size: float, shine: bool = True) -> None:
    """Paint the icon with its bottom middle at (x, y), `size` wide and high. shine: its own colours,
    whatever the light of the card (False: it stands in the card's light like everything else)."""
    z = size / 100.0
    ox, oy = x - 50 * z, y - 100 * z
    for pr in TABLE[name][2]:
        if pr[0] == "e":
            k.ell(ox + pr[1] * z, oy + pr[2] * z, pr[3] * z, pr[4] * z, pr[5], e=shine)
        elif pr[0] == "r":
            k.rect(ox + pr[1] * z, oy + pr[2] * z, ox + pr[3] * z, oy + pr[4] * z, pr[5], r=pr[6] * z, e=shine)
        elif pr[0] == "p":
            k.poly([(ox + px * z, oy + py * z) for px, py in pr[1]], pr[2], e=shine)
        else:
            k.stroke([(ox + px * z, oy + py * z) for px, py in pr[1]], pr[2], max(1.5, pr[3] * z), e=shine)
