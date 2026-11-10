# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The restricted-goods screen's reading of a product's own description (``restricted``, layer 5).

The shop's description is the most reliable sign of tobacco a product carries: its title can be opaque ("Baisha
harmonization", a Chinese cigarette: "...hand-selected tobacco. Hollowed filter to improve flow of smoke."), its
brand misspelt and its category wrong. A description that names a tobacco or nicotine product withholds it, unless
the product is plainly other goods: fragrances describe tobacco notes ("a deep masculine base of tobacco"), whiskies
and wines smoke and cigar boxes ("an antique cedarwood cigar box"), cognacs a cigar to pair them with, and lighters
cigarettes. ``describes_tobacco`` reads, in this order:

1. ``OTHER_GOODS_TITLE``: a title naming goods no tobacco product is (food, clothing, accessories, oral care, toys,
   a lighter or ashtray, a grape or a spirit) clears the description.
2. ``VAPOUR_TERMS``: nicotine, e-cigarettes, vapes, e-liquids, snus and heated tobacco withhold the product whatever
   else the title or description says (no fragrance, spirit or volume describes them; an e-liquid is sold by volume).
3. ``restricted_rules.NON_TOBACCO_CONTEXT`` in the title (a spirit, wine, fragrance, cosmetic or volume) or
   ``OTHER_GOODS_DESCRIPTION`` in the description (a perfume's notes, a spirit's strength or distillery, a wine's
   grapes, a candle's wax, an air freshener's odours) clears the remaining terms.
4. ``TOBACCO_TERMS`` (tobacco, cigarettes, cigars, shisha, rolling papers in thirteen languages) and
   ``SMOKING_USE`` (a cigarette's filter, draw, pack or capsule) withhold it.

The category is never read: the catalogue files tobacco under whiskey, liquor, champagne and fragrance ("State
express original" in "whiskey", "Davidoff Sign Exquisitos 3x10s" in "fragrance"). Every pattern reads text folded by
``restricted.folded``. The examples are real catalogue descriptions (``skybuyfly_mcp_tests/fixtures/restricted_*``).
"""

from __future__ import annotations

import re
from typing import Final

from skybuyfly_mcp.restricted_rules import NON_TOBACCO_CONTEXT

OTHER_GOODS_TITLE: Final = re.compile(
    r"\blighters?\b|\bfeuerzeug|\bbriquet\b|\baccendino\b|\bmechero\b|\bashtrays?\b|\baschenbecher\b"
    r"|\bchoco|\bpralin|\btruffles?\b|\bli(?:c|qu)orice\b|\blakrit|\bcand(?:y|ies)\b|\bsweets\b|\bgums?\b|\btoffee"
    r"|\bfudge\b|\bcaramels?\b|\bmarzipan\b|\bnougat\b|\bbiscuits?\b|\bcookies?\b|\bwafers?\b|\bcakes?\b|\bteas?\b"
    r"|\bcoffee\b|\bhoney\b|\bjam\b|\bnuts\b|\bsnacks?\b"
    r"|\btrousers\b|\bpants\b|\bjeans\b|\bchinos\b|\bleggings\b|\bdress(?:es)?\b|\bskirts?\b|\b(?:t-)?shirts?\b"
    r"|\bhoodie|\bsweat(?:er|shirt)s?\b|\bjumpers?\b|\bcardigans?\b|\bjackets?\b|\bblazers?\b|\bcoats?\b|\bsocks\b"
    r"|\bhats?\b|\bbeanies?\b|\bscarf|\bgloves\b|\bties?\b|\bshoes\b|\bsneakers\b|\bboots\b|\bsandals\b|\bbags?\b"
    r"|\bhandbags?\b|\bbackpacks?\b|\bwallets?\b|\bpurses?\b|\bbelts?\b|\bwatch(?:es)?\b|\bsunglasses\b"
    r"|\bnecklaces?\b|\bbracelets?\b|\bearrings?\b|\bpendants?\b|\bcufflinks\b|\bkey ?rings?\b|\bbrooch"
    r"|\btooth(?:paste|brush)|\bmouthwash\b|\bwhitening\b|\bdental\b|\btoys?\b|\bplush\b|\bteddy\b|\bpuzzles?\b"
    r"|\bjigsaws?\b|\blego\b|\bboard ?games?\b"
    r"|\bfigur(?:e|ine)s?\b|\bmagnets?\b|\bpostcards?\b|\bbooks?\b|\bmugs?\b|\bcreams?\b|\bserums?\b|\blotions?\b"
    r"|\bbalms?\b|\bmasks?\b|\bcleans(?:er|ing)\b|\bfoundation\b|\blipsticks?\b|\bmascara\b|\beyeliner\b|\bshampoo\b"
    r"|\bconditioner\b|\bemulsion\b|\btoner\b|\b(?:day|night|face|skin|body|hair) care\b"
    r"|\bcabernet\b|\bsauvignon\b|\bmerlot\b|\bshiraz\b|\bsyrah\b|\bpinot\b|\bchardonnay\b|\briesling\b|\bmalbec\b"
    r"|\btempranillo\b|\bgrenache\b|\bzinfandel\b|\bsangiovese\b|\bnebbiolo\b|\brioja\b|\bbordeaux\b|\bchianti\b"
    r"|\bprosecco\b|\bcava\b|\bbrut\b|\bbaijiu\b|\bsake\b|\bsoju\b|\baquavit\b|\bgrappa\b|\bschnapps\b|\bvermouth\b"
    r"|ライター|灰皿|打火机|烟灰缸|라이터|재떨이|ウイスキー|ウィスキー|威士忌|ブランデー|白兰地|干邑|ワイン|葡萄酒|红酒|紅酒"
    r"|焼酎|日本酒|白酒|위스키|와인|香水|향수|チョコ|巧克力|초콜릿",
)
"""Goods no tobacco or nicotine product is, named in the title: food and sweets ("Panda Soft & Fresh Licorice"),
clothing and accessories ("Winston Flag Bucket Hat"), cosmetics ("Sisley Ecological Compound Day Care": "pollution,
tabac"), oral care (toothpaste "removes nicotine stains"), toys, puzzles, board games and books (not "game" alone:
Swisher's Game cigarillos), lighters and ashtrays (they light and hold cigarettes), and the grapes and spirits
``NON_TOBACCO_CONTEXT`` does not name ("Penfolds Bin 707 Cabernet Sauvignon Gift Box": "rolled cigar-leaf cabernet"),
also in Japanese, Chinese and Korean (ライター, 打火机, 라이터 lighters; ウイスキー, 威士忌, 위스키 whisky; 香水, 향수
perfume). The title's pack counts read it too (``restricted_rules.CONTEXT_SIGNS``: "9 Image 1000 Piece Jigsaw
Puzzle", "Casio G-Shock ... Men Watch")."""

VAPOUR_TERMS: Final = re.compile(
    r"\bnicotine?\b|\be-?cig|\be-?zig|\belectronic cigarett|\be-?liquid|\be-?juice|\bvap(?:e|es|er|ers|ing)\b"
    r"|\bnic ?salts?\b|\bsnus\b|\bheat ?sticks?\b|\bheets\b|\bterea\b|\biqos\b|\bploom\b|\bheated tobacco"
    r"|ニコチン(?!酸)|尼古丁|니코틴|电子烟|電子煙|電子たばこ|電子タバコ|加熱式|전자담배",
)
"""Nicotine and its smoke-free products: "nicotine" ("6 mg nicotine per pouch"; not "nicotinamide", niacinamide, nor
"ニコチン酸アミド"), e-cigarettes ("...prohibit e-cigarette imports", "electronic cigarettes"), vapes, e-liquids and
nicotine salts, snus, heated tobacco and its sticks and devices ("This product is only for IQOS tobacco")."""

TOBACCO_TERMS: Final = re.compile(
    r"\btobacc?o|\btabacc?o|\btabac|\btabak|\btobak|\btyton|\bdohany|\btutun|\btupak"
    r"|\bcigar|\bzigar|\bsigar|\bsigaar|\bcygar|\bsikari|\bsavuke|\bpapieros|\bc'llos\b"
    r"|\bshisha|\bhookah|\bnarghil|\bnargil|\bnarguil|\bmoassel|\bmaassel|\bmu'?assel|\bwasserpfeife|\bwaterpijp"
    r"|\bwater ?pipes?\b|\bcachimba|\brolling papers?\b|\broll-your-own\b|\bsnuff\b"
    r"|烟草|烟丝|烟叶|烟支|香烟|卷烟|细支|雪茄|水烟|煙草|香煙|捲煙|たばこ|タバコ|紙巻|葉巻|喫煙|담배|궐련"
    r"|табак|сигар|папирос|кальян",
)
"""Tobacco and its smoked products in English, German, French, Spanish, Italian, Dutch, Polish, Finnish, Swedish,
Hungarian, Turkish, Japanese, Chinese, Korean and Russian: tobacco ("Tabak", "tytoń", "dohány", "tütün", "tupakka",
"烟草", "たばこ", "담배"), cigarettes and cigars ("Zigaretten", "sigaretten", "papierosy", "savukkeet", "cygara",
"香烟", "紙巻", "궐련"), shisha and its pipes ("Shisha tobacco molasses", "moassel", "narghilè"), rolling papers and
snuff. Fragrances, spirits and wines use the same words for notes: ``OTHER_GOODS_DESCRIPTION`` clears them."""

SMOKING_USE: Final = re.compile(
    r"\b(?:flow|draw) of (?:the )?smoke\b|\bsmoke flow\b|\bsmoking (?:experience|pleasure|sensation|satisfaction"
    r"|enjoyment|moment)\b|\b(?:hollow(?:ed)?|recessed|acetate|cavity|capsule|cork-?tipped) filters?\b"
    r"|\bfilter tips?\b|\bdraw resistance\b|\bdraw and (?:an? )?(?:\w+ )?burn\b|\bburn and (?:the )?draw\b"
    r"|\b\d{1,2} (?:sticks|cigarettes|pieces) (?:per|in each|in a) pack\b|\b\d+ ?cartons? ?\(\d+ ?packs?\)"
    r"|\bcrush(?:able)? (?:balls?|capsules?|beads?)\b|\bclick (?:capsules?|balls?|beads?)\b|\b\d{3,5} puffs\b"
    r"|\bpuffs? per\b",
)
"""How a cigarette is used, read where it names no product: its filter ("Hollowed filter to improve flow of smoke"),
its draw ("an even draw and burn"; not a game's "even draw posts"), its pack ("20 pieces per pack", "1 carton (10
packs)"), its flavour capsule ("crush ball", "click capsule") and a disposable's puffs. Not a whisky's "smoky" or
"peat smoke", nor a powder "puff" or a headphone's noise "filter"."""

OTHER_GOODS_DESCRIPTION: Final = re.compile(
    r"\beaux? de\b|\bparfum|\bperfum|\bprofum|\bfragranz|\bfraganc|\bduft|\bcologne\b|\baftershave"
    r"|\bfragrance (?:family|notes?|for (?:men|women|him|her))|\bnot(?:es?|a|as|e) (?:de|di|du) (?:tete|coeur|fond"
    r"|testa|cuore|fondo|salida|corazon)\b|\b(?:kopf|herz|basis)noten?\b"
    r"|\b(?:top|head|heart|middle|base|dry ?down) notes?\b|\bolfact|\bsillage\b|\baccords?\b|\bcandles?\b|\bwick\b"
    r"|\bburn time\b|\b(?:soy|beeswax|paraffin) wax\b|\bdiffuser|\b\d+(?:[.,]\d+)? ?% ?(?:vol|abv|alc)|\babv\b"
    r"|\bdistill|\bsingle malt\b|\bblended malt\b|\bmatured (?:in|for)\b|\bbottled (?:at|in)\b|\bcask strength\b"
    r"|\bwinemak|\bvineyards?\b|\bgrapes?\b|\btannins?\b|\bcabernet\b|\bshiraz\b|\bmerlot\b|\bpinot\b"
    r"|\b(?:removes?|eliminat\w*|neutrali[sz]\w*|absorb\w*) (?:\w+ ){0,3}(?:odou?rs?|smells?)\b|消臭|냄새 제거"
    r"|\b(?:windproof|refillable|butane|jet|torch|pocket|electric|plasma|arc|flint|petrol) lighters?\b|\bbutane\b"
    r"|\bskin(?:care)?\b|\bcomplexion\b|\bmoisturi[sz]|\bspf ?\d|\banti-?pollution\b|\bwrinkles?\b|\bpores\b",
)
"""What only other goods say of themselves: a perfume's family, notes, accords and sillage, also in Italian, French,
Spanish and German ("...base notes of Tonka Bean, Tobacco, and Leather"; "foglie di tabacco ... un profumo caldo" of
Diptyque's Narguilé), a cosmetic's skin ("fight environmental stress (pollution, tabac,...)"), a candle's wick and
wax, a spirit's strength, distillery, maturation and bottling ("an antique cedarwood cigar box" of a single malt), a
wine's grapes and tannins ("notes of liquorice, violets and tobacco" of a cabernet), an air freshener's odours
("eliminates tobacco smells") and a lighter's kind ("windproof lighter for cigarettes and cigars"; not "a lighter
taste"). Not tasting words a cigar shares ("notes of cedar", "aged", "cask"), nor "ingredients" (a shisha's are
tobacco and molasses)."""


def describes_tobacco(title: str, description: str) -> bool:
    """Return whether a product's own description names a tobacco or nicotine product (module docstring).

    ``title`` and ``description`` are folded (``restricted.folded``).

    Returns:
        ``True`` on a nicotine or vapour term, or a tobacco term or a cigarette's use outside other goods.
    """
    if not description or OTHER_GOODS_TITLE.search(title):
        return False
    if VAPOUR_TERMS.search(description):
        return True
    if NON_TOBACCO_CONTEXT.search(title) or OTHER_GOODS_DESCRIPTION.search(description):
        return False
    return TOBACCO_TERMS.search(description) is not None or SMOKING_USE.search(description) is not None
