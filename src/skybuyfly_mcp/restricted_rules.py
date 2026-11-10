# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The restricted-goods screen's text rules: brand-independent signs of tobacco and nicotine (``restricted``).

Every pattern reads text folded by ``restricted.folded`` (case-folded, accents and trademark signs dropped, single
spaces, plain apostrophes). The examples are real catalogue titles (``skybuyfly_mcp_tests/fixtures/restricted_*``).
"""

from __future__ import annotations

import re
from typing import Final

_MARKETS: Final = r"(?:de|at|dk|pl|nl|fr|it|es|cz|hu|sk|si|hr|gr|pt|be|lu|se|fi|no|ch|gb|uk|ie|lt|lv|ee|ro|bg|eng s)"
_PACK_COUNT: Final = r"(?:[1-9]|10|12|14|15|16|18|20|24|25|30|40|50|100)"
_VITOLA: Final = (
    r"\b(?:robustos?|toro|belicosos?|torpedos?|panetelas?|panatelas?|lonsdales?|perfectos?|puritos?|brevas|gigante"
    r"|(?:petit|double|half|gran) coronas?|corona gorda)\b"
)
_COUNT: Final = r"\b\d{1,2}\s?(?:x\s?\d{1,3}\s?)?(?:pcs|stk|'?s|er|pieces|cigars)\b"

KIND_WORDS: Final = re.compile(
    r"\bcigaret|\bcigarillo|\bc'llos\b|\bcigarrillo|\bzigarett|\bzigarill|\bzigarre|\bsigarett|\bsigaret|\bsigar[oi]\b"
    r"|\bpapieros|\bsavukk|\bcigarr(?:o|os|er)\b|\bpuros\b"
    r"|\be-?cig|\be-?zig|\be-?liquid|\bvapes?\b|\bvaping\b|\bvape pen|\bpod ?kit\b|\bsnus\b|\bnicotine?\b|\bnikotin"
    r"|\bheated tobacco|\btobacco heat|\bheat ?sticks?\b|\bfor (?:glo|iqos|ploom|lil)\b|\bglo hyper\b|\btabakerhitzer"
    r"|\bpfeifentabak|\bdrehtabak|\bfeinschnitt|\bstopftabak|\bkautabak|\bschnupftabak|\bsnuff\b"
    r"|\b(?:rolling|pipe|shisha|hookah|hand-?rolling|fine cut|ryo|chewing) tobacco\b|\btabac a rouler\b|\bshag\b"
    r"|\bhalfzware\b|\bnavy flake\b|\bready rubbed\b|\bmoassel|\bmaassel|\bmu'?assel"
    r"|たばこ|タバコ|煙草|香烟|卷烟|雪茄|电子烟|烟草|烟丝|细支|香煙|捲煙|紙巻|葉巻|담배|궐련|сигарет|табак|папирос"
    r"|кальян|水烟",
)
"""Words for a tobacco or nicotine product in English, German, French, Spanish, Italian, Dutch, Polish, Finnish,
Swedish, Japanese, Chinese, Korean and Russian: cigarettes, cigarillos ("Ascots Cigarillos", "Davidoff Mini C'llos
Silv 50s"), e-cigarettes and e-liquids, vapes, snus, nicotine ("SKRUF #4 Crystal Fresh nicotine bags 12mg"), heated
tobacco and its sticks ("Tabakerhitzer - Online kaufen", "Kent neo true for glo hyper"), pipe and roll-your-own
tobacco ("Dreh- & Pfeifentabak", "Navy Flake 100g"), snuff and chewing tobacco, shisha tobacco ("moassel",
"кальян"). "Cigar", "tobacco" and the shisha pipe alone are ``AMBIGUOUS_WORDS``."""

JAPANESE_BRANDS: Final = re.compile(
    r"セブンスター|メビウス|マールボロ|ウィンストン|パーラメント|ラッキー・?ストライク|ピアニッシモ|アイコス|テリア・|プルーム・",
)
"""Tobacco brands written in katakana by Japanese shops ("セブンスター" by "日本たばこ"): a brand of
``restricted_brands`` is read in Latin letters only (``restricted.name_words``). The names other goods carry in
Japanese too (ピース "piece", ホープ, クール, ハイライト "highlighter", キャメル "camel colour", エコー, テリア
"terrier") are left out, but for TEREA and Ploom written with JT's and PMI's middle dot ("テリア・メンソール",
"プルーム・エックス")."""

_CHINESE_SIGN: Final = r"\s*\(?\s*(?:软|硬|細支|细支|中支|短支|爆珠|精品|典藏|经典|經典|九五|\d)"
CHINESE_BRANDS: Final = re.compile(
    r"芙蓉王|红塔山|紅塔山|和天下|中南海|娇子|嬌子|云烟|雲煙"
    r"|(?:中华|中華|白沙|泰山|熊猫|熊貓|红双喜|紅雙喜|双喜|雙喜|兰州|蘭州|长白山|長白山|黄山|黃山|南京|利群|玉溪|红梅|紅梅"
    rf"|钓鱼台|釣魚台|黄鹤楼|黃鶴樓){_CHINESE_SIGN}",
)
"""China Tobacco's brands written in Chinese (``restricted_brands`` reads Latin letters only): the names only
cigarettes carry (Furongwang 芙蓉王, Hongtashan 红塔山, Baisha's He Tian Xia 和天下, Zhongnanhai 中南海, Jiaozi 娇子,
Yunyan 云烟), and the names of places, landmarks and common words other goods carry too (中华 "China", 泰山 Mount
Tai, 熊猫 "panda", 双喜 "double happiness", 黄鹤楼 baijiu, 钓鱼台 baijiu) followed by a pack sign: soft or hard
pack, slim or mid-slim, crush ball, premium or collection line, or a number ("中华 软", "黄鹤楼 1916")."""

AMBIGUOUS_WORDS: Final = re.compile(
    r"\btobacc?o\b|\btabacc?o\b|\btabac\b|\btabak\b|\bcigars?\b|\bzigarren?\b|\bshisha\b|\bhookahs?\b|\bnarghil"
    r"|\bnargil|\bwasserpfeife|\bwaterpijp",
)
"""Words that name tobacco in a tobacco product ("Drum RYO Tobacco 250g", "Cohiba Corona (1 Pack of 3 Cigars)") and
a note or a name in a spirit or a fragrance ("Dalmore Cigar Malt", "Tom Ford Tobacco Vanille", "Tobacco and Oak
Scented Candle", Diptyque's "Narguilé Candle" named after the shisha pipe): a tobacco sign only without
``NON_TOBACCO_CONTEXT``."""

LABEL_WORDS: Final = re.compile(r"\btobac|\btabac|\btabak|\bcigar|\bzigarr|\bsmok(?:ing|ers?)\b|\bheated\b")
"""Tobacco words of a brand or category ("Agio Cigars", "Chinese tobacco", "Tobacco Products", "Smoking accessories"),
read like ``AMBIGUOUS_WORDS``."""

NON_TOBACCO_CONTEXT: Final = re.compile(
    r"\bwhisk(?:e?y|ies)\b|\bscotch\b|\bbourbon\b|\brh?um\b|\bcognac\b|\bbrandy\b|\barmagnac\b|\bcalvados\b|\bgin\b"
    r"|\bvodka\b|\btequila\b|\bmezcal\b|\bliqueur\b|\blikor\b|\bport\b|\bsherry\b|\bwines?\b|\bchampagne\b|\bmalt\b"
    r"|\bbeer\b|\bspirits\b|\bliquor\b|\b\d+(?:[.,]\d+)?\s?%\s?(?:vol|abv|alc)|\b\d+(?:[.,]\d+)?\s?(?:cl|l|ltr|ml)\b"
    r"|\beau de\b|\bed[ptc]\b|\bparfums?\b|\bperfumes?\b|\bprofumo\b|\bcologne\b|\bfragrances?\b|\bextrait\b"
    r"|\bscent(?:ed|s)?\b|\bcandles?\b|\bkerze\b|\bdiffus[eo]r\b|\broom spray\b|\bbody (?:mist|lotion|wash)\b|\boud\b"
    r"|\bvanille\b|\bmusk\b|\baftershave\b|\bafter shave\b|\bdeodorant\b|\bshower gel\b|\bsoap\b|\bskin-?care\b"
    r"|\bmake-?up\b|\bbeauty\b|\bheadphones?\b|\bearphones?\b|\bspeakers?\b|\bchargers?\b|\busb\b|\bbluetooth\b"
    r"|\btissues?\b|\bwipes\b|\bcotton\b|\blighters?\b|\bfeuerzeug\b|\bbriquet\b|\bashtrays?\b|\baschenbecher\b",
)
"""A spirit, wine, fragrance, home scent, cosmetic, electronic device, tissue, lighter or ashtray, or a volume (tobacco
is sold by weight and count: "Tom Ford Tobacco Chocolat 50ml" is a fragrance), named in the title. It overrides the
weaker readings only (``AMBIGUOUS_WORDS``, ``LABEL_WORDS``, ``CONTEXT_SIGNS``, ``DUAL_SIGNS``; "Lark Single Malt 43%
gift box" is whisky, "Sennheiser HD 400S Headphones" no carton), never a tobacco-only format or an exclusive brand
("Cohiba Cognac 70cl" is withheld by its brand). The category is not read for it: the catalogue files tobacco under
liquor, cognac, champagne and fragrance ("Winston cabin red 8 box" in "liquor", "Davidoff Sign Exquisitos 3x10s" in
"fragrance")."""

TAX_STAMP: Final = re.compile(
    rf"\b{_MARKETS}\s(?:tt|tts|tp|tpd2?|dts|plp)\b|\b(?:tt|tts|tp|plp)\s{_MARKETS}\b|\b(?:tts|dts|tpd2?|plp)\b"
    r"|\b(?:de|at|dk)\*",
)
"""The tax stamp and market codes duty-free shops write on tobacco only: "MARLBORO RED TREX 200s DE TTS", "Mac Baren
Plumcake 100g DE TT", "BMS Churchill AT 3s TPD2 TT DE", "VEEV ONE BlueMint 2x2ml DE TP", the EU Tobacco Products
Directive mark ("RELX 2-Pod Menthol Plus TPD2*"), the plain-pack mark ("MARLBORO ONE 200s PLP DK TTS"), and
Heinemann's market footnote on nicotine ("VUSE GO 1K Mint Ice 20mg DE*"; spirits carry the footnote as "1L*")."""

PACK: Final = re.compile(
    r"\b\d{1,3}\s?(?:cigarettes|cigarillos|cigars|cigs|zigaretten|zigarillos)\b"
    r"|\b\d{1,2}\s?x\s?\(?\d{1,3}\)?\s?(?:'?s|er|stk|sticks|cigars|cigarillos)\b|\b(?:box|pack) carton\b"
    r"|\bcarton packs?\b|\bcarton \d+/\d+|\b(?:hard|soft) ?pack\b(?!.*\b(?:tissues?|wipes)\b)"
    r"|\bks\b(?=.*\b(?:box|pack|soft|hard|carton|fi|ff|pcs)\b)"
    r"|\bking ?size\b(?=.*\b(?:cigarettes|box|pack|carton|slims?|filters?|papers?|blattchen|tips)\b)"
    r"|\bsuper ?kings\b|\bsuperking\b|\bsuper ?slims\b|\bcrush ?ball\b"
    rf"|{_VITOLA}.*{_COUNT}|{_COUNT}.*{_VITOLA}",
)
"""Cigarette and cigar packs: a count of cigars or cigarillos, a multipack ("Al Capon PoFil. Sun 10x10s", "Davidoff
Primeros 3 x 6er"; not "Elizabeth Arden Ceramide Capsules 3x30 pcs"), "Box Carton", "Carton Packs", soft and hard
packs ("Chunghwa Soft Pack"), king size packs ("Lark mild ks box", "Mayfair ff ks fi box 200 pcs"), Superkings, super
slims, crushball filters ("L&B Blue Crushball Ks Box 200"), a cigar shape with a pack count whatever the flavour
("Dipped cognac toro-torpedo humi 6x52 pcs" in "cognac"; "Corona" beer and "Churchill" sweets carry no shape name)."""

NICOTINE_FORMAT: Final = re.compile(
    r"\b\d+(?:[.,]\d+)?\s?mg\s?/\s?(?:ml|g)\b|\b\d{3,5}\s?(?:puffs?|zuge)\b|\b\d+(?:[.,]\d+)?\s?mg\b(?=.*\b(?:pods?"
    r"|pouch(?:es)?|bags|portions?|mini|slim|strong|intense|x\d)\b)|\bpods?\b.*\b\d(?:[.,]\d)?\s?ml\b|\b\d(?:[.,]\d)?"
    r"\s?ml\b.*\bpods?\b|\bpods?\b.*\b\d(?:[.,]\d)?\s?%|\b\d+\s?x\s?\d+\s?x\s?\d+(?:[.,]\d+)?\s?mg\b"
    r"|\b\d{1,2}\s?x\s?\d{1,2}(?:[.,]\d{1,2})?\s?(?:g|gr|gram)\b(?=.*(?:\bs[1-6]\b|\b\d{1,2}\s?%|\bmg\b|\bmini\b"
    rf"|\bslim\b|\bstrong\b|\b{_MARKETS}$))"
    r"|(?:\bs[1-6]\b|\b\d{1,2}\s?%).*\b\d{1,2}\s?x\s?\d{1,2}(?:[.,]\d{1,2})?\s?(?:g|gr|gram)\b"
    r"|\b\d{1,2}\s?x\s?\d{2,3}\s?g\b.*\bryo\b|\bryo\b.*\b\d{1,2}\s?x\s?\d{2,3}|\b(?:ryo|myo)\b",
)
"""Nicotine strengths and formats: e-liquid strength ("20mg/ml"), disposable puffs ("600 puffs"), a strength on a pod
or pouch ("VELO Blue Storm X-Intense 20mg" with "Mini"/"x"), pods with their fill or strength ("Elfa Pod Purple Mix
2x2ml", "VEEV one Vape Kit + Coral Wave Pod 1,8%"), pouch cans with a strength or market ("THUNDER FROSTED S4 5x17g
AT", "White Fox Double Mint 25% 5x15gr", "ZYN Cool Mint S3 Mini 5x8g AT"; chocolate multipacks such as "Läkerol
4x25g" carry none), roll-your-own packs ("American Spirit RYO 8x30g")."""

SMOKING_ACCESSORY: Final = re.compile(
    r"\brolling papers?\b|\bblattchen\b|\bfilter ?tips?\b|\bfilter ?tubes?\b|\bhulsen\b|\bhumidors?\b|\bcigar cutter"
    r"|\bpapers?\b.*\b(?:king ?size|booklets?|leaves|blattchen)\b|\bking ?size\b.*\b(?:papers?|sheets)\b"
    r"|\b\d+\s?sheets\b.*\b(?:slim|king)\b|\b(?:slim|king)\b.*\b\d+\s?sheets\b",
)
"""Smoking accessories made for tobacco: rolling papers ("GIZEH BLACK King Size Slim, 34 sheets."), filter tips and
tubes, cigarette tubes ("Hülsen"), humidors, cigar cutters (not "Montblanc Paper Slim Notebook"). Lighters and
ashtrays are not tobacco or nicotine products (they light candles and stoves, and hold anything): they are shown."""

CONTEXT_SIGNS: Final = re.compile(
    r"(?<![a-z\d]-)(?:\b(?:200|400|600|800|1000)\s?(?:'?s|sticks?|stk|stuck|cigarettes|cigs|zigaretten)\b"
    r"|\b(?:400|600|800|1000)\s?(?:pcs|pieces?)\b|\b100'?s\b"
    rf"|\b{_PACK_COUNT}\s?'?s\b(?!\s?(?:style|edition|collection))"
    r"|\b[1-9]\d{1,2}\s?sticks\b|\b\d{1,3}\s?stk\b)(?!-[a-z\d])|\bcarton\b(?!.*\b\d+\s?g\b)",
)
"""Pack counts that are tobacco on their own unless the title names other goods (``NON_TOBACCO_CONTEXT``, or
``restricted_description.OTHER_GOODS_TITLE``: "9 Image 1000 Piece Jigsaw Puzzle"): cartons ("Marlboro Red 100's 200s
Deutschland", "Sterling superkings 400 pcs", "Gauloises Blondes Red 200 Sticks"; not "Sennheiser HD 400S
Headphones"), the 100 mm length ("Kent s-series 1 100s box"), cigar packs ("Hoyo de Monterrey Petit Robusto 3s",
"Davidoff 2000 5s", "Bolivar Royal Coronas 25 Sticks", "Quintero Brevas 25 stk"), "Camel Crush Carton" (not "Walkers
Shortbread Camels Carton 175g"). A count inside a hyphenated model code is none ("Casio G-Shock G-Lide Men Watch
GBX-100S-1DR Black")."""

DUAL_SIGNS: Final = re.compile(
    rf"\b{_PACK_COUNT}\s?'?s\b|\b\d{{1,2}}\s?x\s?\d{{1,3}}\b(?!\s?(?:ml|cl|l|g|kg|oz)\b)"
    r"|\b(?:[5-9]|10)\s?x\s?[2-9]\dg\b"
    r"|\b\d{1,3}\s?(?:er|stk|pcs|pieces)\b|\b\d+\s?sticks?\b|\bcarton\b|\bbox\b|(?<!gift )(?<!travel )(?<!multi)"
    r"\bpacks?\b|\bks\b|\bking ?(?:size|box)\b|\bslims?\b|\bmenthol\b|\blights\b|\bmild\b|\bfilters?\b|\bfine cut\b"
    r"|\b\d+(?:[.,]\d+)?\s?mg\b|\bpods?\b|\bdevice\b|\bstarter ?kit\b|\(\d{1,2}\)|\bportions?\b"
    r"|\b(?:x-?|extra |super |ultra )?(?:strong|intense)\b|\bpapers?\b|\b(?:robusto|coronas?|churchill|toro|belicoso"
    r"|torpedo|puritos?|panetelas?|panatelas?|lonsdale|perfecto|tubos?|brevas|gigante)\b",
)
"""Weaker signs that read as tobacco on a product of a ``restricted_brands.DUAL_BRANDS`` name ("Kool mild", "Kent 1
ks box", "Hope(10)", "Ripple+ Dream 2x PODs", "Nordic Spirit Icy Peppermint X-Strong", "Amber Leaf 5x50g") and not
on its other goods ("Mayfair Bag", "Lark Single Malt")."""

TAR_STRENGTH: Final = re.compile(r"\b\d{1,2}(?:[.,]\d{1,2})?\s?mg\b")
"""A tar or nicotine strength: on a product of a dual brand it reads as tobacco even where the title names other
goods ("Dunhill champagne 3mg" is a cigarette; no Dunhill fragrance or Davidoff coffee states milligrams)."""

_VARIANTS: Final = (
    "blue sky red gold golden silver white black green purple yellow orange grey gray bronze amber turquoise russet "
    "teak sienna ruby aqua platinum navy original originals classic classics menthol fresh smooth light lights mild "
    "super extra ultra one ks box pack soft hard slim slims superslims 100s filter international int label deluxe "
    "signature premium special full flavour flavor rich regular double ice boost option the "
    "classico clasico classique originale antico rosso nero oro argento azzurro blu bianco blanc rouge noir bleu vert "
    "rot blau gelb schwarz weiss silber ruan ying huangjin jin hong hei lan bai xizhi zhongzhi baozhu jingpin "
    "zhenpin diancang 1 2 3 4 5 6 7 8 9 10 12 14 20"
)
VARIANT_WORDS: Final = frozenset(_VARIANTS.split())
"""The words of a cigarette or cigar variant, in English, Italian, Spanish, French, German and the pinyin of Chinese
packs (ruan soft, ying hard, huangjin gold, xizhi slim, baozhu crush ball, jingpin premium): a product of a dual
brand named only by them reads as tobacco ("Mayfair Sky Blue", "State Express 555 gold", "Lark Mild", "Toscano
Classico", "Zhonghua Soft", "Taishan Huangjin"), not one named by an object ("Mayfair Bag", "Panda Licorice")."""

STRENGTH_ENDINGS: Final = frozenset((*(str(strength) for strength in range(1, 15)), "ks", "100", "100s"))
"""The last word of a Japanese shop's cigarette title: its tar strength (1 to 14 mg), King Size or the 100 mm length.
JT, PMI and BAT Japan name a cigarette "<brand> <sub-line> <colour or flavour> <strength>" ("Winston caster white 5",
"Mevius option purple 5", "Camel craft menthol 5", "Philip Morris purple 5"): a title of that shape led by the dual
brand its brand field names, with at most one word that is no variant (the sub-line) and at least one variant before
the strength, reads as tobacco outside a ``NON_TOBACCO_CONTEXT`` (not "Camel bag 5": no colour or flavour)."""

DESCRIPTION_SIGNS: Final = re.compile(
    r"\btar\s?:?\s?\d+(?:[.,]\d+)?\s?mg\b|\bnicotine?\s?:?\s?\d+(?:[.,]\d+)?\s?mg\b|\bnikotin\b|\bnikotiini\b"
    r"|\b\d+(?:[.,]\d+)?\s?mg (?:of )?nicotine\b"
    r"|\bcontains nicotine\b|\bnicotine is (?:a )?highly addictive|\bsmoking (?:kills|causes|seriously harms)"
    r"|\bsmoking is (?:highly )?addictive|\brauchen (?:ist todlich|kann todlich sein|fugt|verursacht)"
    r"|\bfumer tue\b|\bfumar mata\b|\bil fumo uccide\b|\broken is dodelijk\b|\brokning dodar\b|\bpalenie zabija\b"
    r"|(?:タール|ニコチン|焦油量?|尼古丁量?|타르|니코틴)\s?:?\s?\d",
)
"""Tobacco and nicotine signs of a product's own description: tar and nicotine yields ("Tar: 5mg Nicotine:0.4mg"
of "Winston caster white 5", "6 mg nicotine per pouch"), "nicotine" in German, Swedish and Finnish, the EU nicotine
warning ("This product contains nicotine which is a highly addictive substance"), the health warnings of cigarette
packs in English, German, French, Spanish, Italian, Dutch, Swedish and Polish, and tar and nicotine yields in
Japanese, Chinese and Korean ("タール 14mg"; not "タール色素不使用", tar-dye free, or "ニコチン酸アミド",
niacinamide, of cosmetics). These read as tobacco whatever the product; a description's tobacco and nicotine
vocabulary, which fragrances and spirits share ("a cigar-box finish"), is read by ``restricted_description``."""
