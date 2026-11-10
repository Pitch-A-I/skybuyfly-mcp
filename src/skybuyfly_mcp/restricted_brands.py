# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""Tobacco and nicotine brands, for the restricted-goods screen (``restricted``).

Sources (read 9 Nov 2026): Wikipedia "List of cigarette brands" (the 424 rows of its table) and "List of cigar
brands" (160 rows); the Wikipedia articles "Snus", "Nicotine pouch", "Heated tobacco product", "Rolling paper" and
"Electronic cigarette"; and the brand portfolios the makers publish (Philip Morris International and Swedish Match,
British American Tobacco, Japan Tobacco International, Imperial Brands, Altria, Scandinavian Tobacco Group, Mac
Baren, Fiedler & Lundgren, GN Tobacco), for the pouch, heated-tobacco, vape and pipe brands those lists lack.
The Japanese portfolios (read 9 Nov 2026; JT's own pages refuse automated reading, so the product lists of Smokio,
which mirror the makers' lineups: https://smokio-navi.com/manufacturers/jt/, .../philip-morris-japan/ and
.../bat-japan/, with JT's Winston family page https://www.jti.co.jp/tobacco/products/winston/index.html) give the
Japanese brands (Hi-lite, Short Hope, Wakaba, Echo, Virginia S., EVO, virto, Luckies) and the Japanese sub-lines of
``SUB_LINES``; the other markets' sub-lines are the ones duty-free shops list (ANA Duty Free's Parliament Aqua Blue and
Night Blue; the Davidoff of Geneva cigar collections, us.davidoffgeneva.com; Imperial's Davidoff Reach and Evolve,
JTI's Winston XStyle, Compact and XSence, Camel Activate and LD Autograph Impulse, BAT's Kent Nanotek, iSwitch,
Surround and Dunhill Master Blend and Top Leaf, as their retail listings name them).
China Tobacco's brands (read 9 Nov 2026: Wikipedia "List of cigarette brands", "Shanghai Tobacco Group",
"Zhongnanhai (cigarette)", "Chunghwa (cigarette)"; https://travelchinawith.me/china-facts/chinese-cigarettes/ for
Baisha, Yunyan, Panda, Nanjing, Hongmei and Diaoyutai and the provincial makers of Taishan (Shandong), Lanzhou
(Gansu), Changbaishan (Jilin) and Jiaozi (Sichuan)), with the pinyin sub-lines duty-free shops translate ("Baisha
harmonization" is 白沙 和天下, He Tian Xia). Shisha tobacco brands (read 9 Nov 2026: https://hookahtrends.com/
best-shisha-tobacco-brands/, https://worldhookahmarket.com/reviews-of-popular-hookah-tobacco-brands/ and
https://gthookah.com/al-fakher-vs-starbuzz-vs-tangiers/: Al Fakher, Adalya, Starbuzz, Tangiers, Nakhla, Fumari,
Darkside, Serbetli, Al Waha, Mazaya, Afzal, Social Smoke). The catalogue's other goods decided which are shared: Panda
is a licorice, a WWF toy and a gin (``restricted_heldout.json``, ``restricted_design.json``); Zhonghua a toothpaste,
Taishan, Lanzhou, Nanjing, Huangshan and Changbaishan places (mineral water, ginseng), Diaoyutai and Huanghelou a
baijiu (Huanghelou stays exclusive in Latin letters: the catalogue's baijiu is written in Chinese), Shuangxi and
Hongmei common words, Jiaozi dumplings, and Darkside, Tangiers, Al Waha, Mazaya and Afzal words and names.
Brands no duty-free shop sells (regional brands of a single country without an airport in the catalogue) are left
out; brands the catalogue has shown are in.

``EXCLUSIVE_BRANDS`` are names only tobacco and nicotine products carry. ``DUAL_BRANDS`` are names other goods carry
too (a fragrance, coffee, a whisky, clothing, a common word: Davidoff, Dunhill, Lark whisky, Sterling silver, Mayfair
bags, "Hope", "West", "More"): a product of theirs is restricted only on a tobacco-reading title
(``restricted_rules.DUAL_SIGNS`` or a bare variant name such as "Mayfair Sky Blue"). Names are written as the
screen reads them (``restricted.name_words``: case and accents folded, apostrophes dropped, "&" joining the letters
of "L & M", other punctuation splitting words).
"""

from __future__ import annotations

from typing import Final


def _names(listed: str) -> frozenset[str]:
    """Return the ``;``-separated names of a listing (spaces around them and line breaks dropped).

    Returns:
        The names.
    """
    return frozenset(name.strip() for name in listed.replace("\n", " ").split(";") if name.strip())


EXCLUSIVE_BRANDS: Final = _names("""
    american spirit; amber leaf; belomorkanal; benson&hedges; craven a; djarum; dji sam soe; ducados; ernte 23;
    esse; gauloises; gitanes; gold flake; golden bat; gudang garam; hongtashan; huanghelou; jin ling; john player;
    jps; kensitas; l&b; l&m; lambert&butler; liqun; lucky strike; marlboro; mevius; mild seven; muratti;
    multifilter; natural american spirit; american sprit; american sprits; natural american sprit; parisienne;
    peter stuyvesant; philip morris; pianissimo; reval; roth handle; rothmans; sampoerna; sobranie; state express;
    superkings; superking; tareyton; virginia slims; winfield; wismilak; yuxi; zhongnanhai; furongwang; chunghwa;
    batton; petteroes; sopiane; elixyr; bastos; cohiba; montecristo; romeo y julieta; partagas; h upmann;
    hoyo de monterrey; cuaba; ramon allones; por larranaga; juan lopez; vegas robaina; la gloria cubana;
    el rey del mundo; vegueros; quintero; diplomaticos; saint luis rey; jose l piedra; arturo fuente; rocky patel;
    macanudo; alec bradley; dannemann; agio; meharis; handelsgold; henri wintermans; ritmeester; swisher sweets;
    swisher; black&mild; garcia y vega; hav a tampa; toscanello; joya de nicaragua; aj fernandez; cusano;
    drew estate; cuesta rey; aganorsa; la flor dominicana; e p carrillo; a j fernandez; mac baren; borkum riff;
    captain black; samuel gawith; gawith hoggarth; erinmore; golden virginia; golden virgina; old holborn;
    cutters choice; van nelle; bali shag; javaanse jongens; brandaris; orlik; rattrays; sutliff; w o larsen; rizla;
    ocb; gizeh; juicy jay; efka; purize; actitube; zyn; lyft; epok; goteborgs rape; ettan; odens; killa; skruf; xqs;
    zonnic; nicorette; nicotinell; niquitin; skoal; helwit; iqos; iluma; heets; terea; ploom; neostiks; pulze; fiit;
    veev; vuse; vype; juul; elf bar; elfbar; lost mary; geek bar; geekvape; vozol; hqd; smok; vaporesso; voopoo;
    uwell; innokin; relx; kubik; oxva; ske crystal; ivg; njoy; puff bar; nasty juice; lost vape; freemax; eleaf;
    joyetech; slix; yunyan; hongshuangxi; al fakher; adalya; starbuzz; nakhla; fumari; serbetli; social smoke;
""")
"""Names only tobacco and nicotine products carry (cigarettes; cigars and cigarillos; pipe and roll-your-own
tobacco; rolling papers and filters; snus, pouches and nicotine replacement; heated tobacco; vapes)."""

DUAL_BRANDS: Final = _names("""
    lark; kool; mayfair; sterling; prince; hope; peace; raison; this; double happiness; nanjing; huangshan; regal;
    embassy; vogue; glamour; more; kiss; assos; alain delon; west; r1; f6; memphis; ronson; cabinet; fine; viceroy;
    belmont; derby; hollywood; popular; fortuna; nobel; ld; merit; caro; petra; start; symphonia; fecske; camel;
    kent; winston; davidoff; dunhill; salem; newport; doral; eve; misty; capri; karelia; sheriff; karo; basic;
    richmond; manchester; monte carlo; black devil; lambert; benson; lucky; 555; mine; salt; bolivar; trinidad;
    punch; fonseca; quai dorsay; guantanamera; san cristobal; sancho panza; oliva; ashton; avo; my father; game;
    phillies; acid; balmoral; al capone; cafe creme; moods; backwoods; white owl; king edward; la aurora; toscano;
    chesterfield; pall mall; parliament; silk cut; du maurier; seven stars; zino; padron; perdomo; plasencia;
    villiger; nub; camacho; drum; peterson; amphora; stanwell; riverstone; pueblo; clan; condor; smoking; raw;
    elements; job; swan; mascotte; energy; general; grov; kronan; catch; siberia; pablo; knox; white fox; thunder;
    kapten; loop; nordic spirit; nordic; lundgrens; fumi; iceberg; cuba; grizzly; copenhagen; kodiak; rogue; ace;
    velo; bambu; glo; neo; lil; hyper; bonds; sentia; delia; levia; blu; aspire; logic; dinner lady; pod salt;
    ripple; ands; elfa; hayati; clubmaster; bond street; zig zag; pure hemp; tatuaje; dutch masters; bori;
    amsterdamer; hi lite; short hope; wakaba; echo; virginia s; evo; virto; luckies; zhonghua; baisha; taishan; panda;
    shuangxi; lanzhou; changbaishan; jiaozi; hongmei; diaoyutai; darkside; tangiers; al waha; mazaya; afzal;
""")
"""Tobacco and nicotine names other goods carry too (restricted only on a tobacco-reading title)."""

_SUB_LINE_LISTS: Final = {
    "winston": "caster; cabin; xstyle; x style; xs; xsence; compact; ssl; inazuma; impulse",
    "camel": "activate; crush; craft; turkish; natural flavor",
    "kent": "nanotek; neo; s series; spark; iswitch; infina; futura; surround; i boost; convertibles",
    "kool": "looped; minty; fk; filter king",
    "lark": "hybrid; smart plus; ice mint; menthol x",
    "parliament": "reserve; carat; night blue; aqua blue; silver blue; hybrid",
    "pall mall": "fk; nightfall",
    "peace": "aroma; infinity",
    "seven stars": "real smooth; revo",
    "davidoff": (
        "magnum; evolve; reach; aniversario; escurio; yamasa; primeros; exquisitos; winston churchill; "
        "late hour; millennium; puro d oro; nicaragua; 702"
    ),
    "dunhill": "master blend; top leaf",
    "ld": "autograph; impulse",
    "virginia s": "sophia; rose; duo",
    "baisha": "harmonization; he tian xia; hetianxia",
    "zhonghua": "shuang zhongzhi; jin zhongzhi",
    "taishan": "hongjiangjun; xinyue; foguang; wangyue; huagui",
    "lanzhou": "feitian; jixiang",
    "changbaishan": "777; renshen",
    "nanjing": "xuanhemen; jiuwu; yuhuashi",
    "huangshan": "hongfangyin; tiandu; huishang; yipin",
    "jiaozi": "kuanzhai",
}.items()
SUB_LINES: Final = {brand: _names(listed) for brand, listed in _SUB_LINE_LISTS}
"""Cigarette sub-lines and variant names, read beside their ``DUAL_BRANDS`` name as a tobacco sign ("Winston caster
white 5", "Camel activate purple", "Kent nanotek 4", "Peace infinity", "Parliament Reserve"): the lines of JT's
Winston (Caster, Cabin, XStyle, Inazuma), Camel (Craft, Activate, Crush), Peace (Aroma, Infinity) and Seven Stars,
PMI's Parliament (Reserve, Carat, Night Blue), Lark and Virginia S. (Sophia, Rose, Duo), BAT's Kent (Nanotek, S-Series,
Spark, iSwitch), Kool (Looped, FK), Pall Mall and Dunhill (Master Blend, Top Leaf), JTI's LD, and the Davidoff cigar
and cigarette lines (Magnum, Evolve, Aniversario, Escurio, Primeros), and China Tobacco's lines in pinyin (Baisha He
Tian Xia, Taishan Hongjiangjun and Xinyue, Lanzhou Feitian, Changbaishan 777, Nanjing Xuanhemen and Jiuwu, Huangshan
Hongfangyin, Jiaozi Kuanzhai). Brands only tobacco carries need none."""
