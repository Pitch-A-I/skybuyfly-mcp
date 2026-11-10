# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""Restricted goods: tobacco and nicotine products never appear in a result (the AI app directories' policy).

The catalogue miscategorises them ("Marlboro Red 100's 200s Deutschland" is a travel accessory, "State Express 555
gold" a whiskey, "White Fox Double Mint 25% 5x15gr" skin care) and misnames their brands ("VEEV ONE Mango 2 pods" has
the brand "VEE", "Dreh- & Pfeifentabak" the brand "Heinemann Shop | Mac Baren"), so a product is restricted by any
of these layered signals, read from its title, brand and category with case, accents and punctuation folded:

1. Kind (``restricted_rules.KIND_WORDS``): its title, brand or category names a tobacco or nicotine product in one
   of thirteen languages ("Zigaretten", "Pfeifentabak", "nicotine bags", "for glo hyper", "Tobacco Products", the
   brand "日本たばこ"), or a tobacco brand in katakana (``JAPANESE_BRANDS``: "セブンスター") or Chinese
   (``CHINESE_BRANDS``: "白沙 和天下", "中华 软").
2. Tobacco-only formats, whatever the brand: duty-free tax stamps and market codes (``TAX_STAMP``: "DE TT", "TTS",
   "TPD2"), cigarette and cigar packs (``PACK``: "5x20s", "ks box", "Soft Pack"), nicotine strengths and formats
   (``NICOTINE_FORMAT``: "20mg/ml", "S4 5x17g AT", "2x2ml" pods, "RYO"), smoking accessories
   (``SMOKING_ACCESSORY``: rolling papers, filter tips, humidors).
3. Words and counts that are tobacco unless the title names a spirit, wine, fragrance, home scent, cosmetic,
   electronic device, tissue, lighter, ashtray or a volume (``AMBIGUOUS_WORDS``, ``LABEL_WORDS``, ``CONTEXT_SIGNS``,
   ``NON_TOBACCO_CONTEXT``): "Drum RYO Tobacco 250g", "Sterling superkings 400 pcs" and "Quintero Brevas 25 stk" are
   withheld, "Dalmore Cigar Malt", "Tobacco Vanille Eau de Parfum" and "Sennheiser HD 400S Headphones" are shown.
   A count is also no sign on a title naming other goods (``restricted_description.OTHER_GOODS_TITLE``: "9 Image
   1000 Piece Jigsaw Puzzle") or inside a hyphenated model code ("Casio G-Shock Men Watch GBX-100S-1DR").
4. Brand (``restricted_brands``): a brand only tobacco carries (``EXCLUSIVE_BRANDS``) leading the title or any part
   of the brand ("Heinemann Shop | Mac Baren", "L+B" as "L&B"; also anywhere in the title when the brand field is
   empty or a tobacco brand: "Kent neostiks"); a brand other goods carry too (``DUAL_BRANDS``: Davidoff, Lark,
   Mayfair, Sterling, Thunder, ...) leading the brand field, or anywhere in a title without one ("Menthol newport"),
   only with a weaker tobacco sign (``DUAL_SIGNS``: "Kool mild", "Kent 1 ks box"; a tar strength, ``TAR_STRENGTH``,
   even beside other goods: "Dunhill champagne 3mg"), a title naming nothing but a variant ("Mayfair Sky Blue",
   "Toscano Classico") or nothing but the brand ("Lark" by Lark: a carton of cigarettes; a product named by nothing
   but a tobacco name is withheld). A dual name leading a title whose brand field names another brand is left to that
   brand ("Hollywood Filter" foundation by Charlotte Tilbury, "Winston Flag Bucket Hat" by Malbon). Placeholder brand
   fields ("Unknown", "Other brand") are read as no brand. The weaker signs of a dual brand include its cigarette
   sub-lines (``restricted_brands.SUB_LINES``: "Winston caster white", "Camel activate purple", "Parliament Reserve")
   and, on a title its brand field's dual brand leads, the Japanese shops' cigarette name: one sub-line word, a
   colour or flavour and a trailing tar strength, King Size or 100 mm (``STRENGTH_ENDINGS``: "Winston cabin red 8").
5. Description, where the answer carries one: tar and nicotine yields ("Tar: 5mg Nicotine:0.4mg"), "Nikotin", the
   EU nicotine warning and the packs' health warnings ("smoking kills", "Rauchen ist tödlich") whatever the product
   (``DESCRIPTION_SIGNS``); and tobacco and nicotine vocabulary ("hand-selected tobacco. Hollowed filter to improve
   flow of smoke", "20 cigarettes per pack", "Shisha tobacco molasses") unless the title or the description says
   the product is other goods: a perfume's tobacco notes, a whisky's cigar box (``restricted_description``).

Decisions (9 Nov 2026): smoking accessories made only for tobacco (rolling papers, filter tips and tubes, humidors,
cigar cutters, IQOS caps) are withheld. Lighters and ashtrays are not tobacco or nicotine products and are shown: the
directories' policy names tobacco and nicotine products, and a lighter is general goods. Nicotine replacement
(Nicorette, Nicotinell, NiQuitin, Zonnic) is a nicotine product and withheld. Goods named after a tobacco brand only
tobacco carries are withheld ("Cohiba Cognac" by Martell).

The rules are measured on hand-labelled production sweeps (``skybuyfly_mcp_tests/test_restricted_sweep.py``).
``is_restricted`` is the one predicate (a pure function of the four texts; the title, brand and category reading is
memoised for ``SCREENED_PRODUCTS`` products, a cached search page being screened again on every call, the description
search is a few regular expressions); ``screen`` is the one place it is applied.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from skybuyfly_mcp import restricted_rules as rules
from skybuyfly_mcp.restricted_brands import DUAL_BRANDS, EXCLUSIVE_BRANDS, SUB_LINES
from skybuyfly_mcp.restricted_description import OTHER_GOODS_TITLE, describes_tobacco

SCREENED_PRODUCTS = 16384
"""How many products' answers ``is_restricted`` remembers (least recently used first out; a few MB at most)."""
_MARKS = str.maketrans({"\u2019": "'", "\u2018": "'", "\u00b4": "'", "`": "'", "\u2122": " ", "\u00ae": " "})
"""Typographic apostrophes read as ``'``; trademark signs as spaces (NFKD would turn "neostiks™" into "neostikstm")."""
_KANA_VOICING = frozenset("\u3099\u309a")
"""The kana voicing marks: part of the letter (``ば`` is not ``は``), kept where accents are dropped."""
_PLACEHOLDER_BRANDS = frozenset(
    (("unknown",), ("brand",), ("other", "brand"), ("test", "brand"), ("string",), ("none",)),
)
"""Brand fields the catalogue fills with a placeholder: read as no brand ("Golden Virginia 250g" by "Unknown")."""
_BRAND_PARTS = re.compile(r"\s*\|\s*|\s*/\s*|\s+-\s+")
_LETTER_PAIR = re.compile(r"\b([a-z])\s*[&+]\s*([a-z])\b")
_NAME_WORD = re.compile(r"[a-z0-9]+(?:&[a-z0-9]+)*")
Name = tuple[str, ...]


def folded(text: str | None) -> str:
    """Return ``text`` case-folded, without accents and trademark signs, with single spaces and plain apostrophes.

    ``Blättchen`` is ``blattchen``, ``neostiks™`` is ``neostiks``, full-width letters are plain; Japanese kana keep
    their voicing marks and Korean syllables stay composed (``たばこ``, ``ﾀﾊﾞｺ`` as ``タバコ``, ``담배``); ``None`` is
    empty.

    Returns:
        The folded text.
    """
    decomposed = unicodedata.normalize("NFKD", (text or "").translate(_MARKS))
    without_marks = "".join(char for char in decomposed if char in _KANA_VOICING or not unicodedata.combining(char))
    return " ".join(unicodedata.normalize("NFC", without_marks).casefold().split())


def name_words(text: str) -> Name:
    """Return a name's words: folded, notes in parentheses and apostrophes dropped, other punctuation splitting words.

    ``L & M`` and ``L+B`` are joined to ``l&m`` and ``l&b``, ``Benson & Hedges`` to ``benson&hedges``.

    Returns:
        The words, in order.
    """
    plain = re.sub(r"\([^)]*\)", " ", folded(text)).replace("'", "")
    joined = re.sub(r"\s*&\s*", "&", _LETTER_PAIR.sub(r"\1&\2", plain))
    return tuple(_NAME_WORD.findall(joined))


_EXCLUSIVE = frozenset(name_words(brand) for brand in EXCLUSIVE_BRANDS)
_DUAL = frozenset(name_words(brand) for brand in DUAL_BRANDS)
_SUB_LINE_ITEMS = SUB_LINES.items()
_SUB_LINES = {name_words(brand): frozenset(name_words(line) for line in lines) for brand, lines in _SUB_LINE_ITEMS}
_LONGEST = max(len(name) for name in _EXCLUSIVE | _DUAL | frozenset[Name]().union(*_SUB_LINES.values()))


def _leading(words: Name, names: frozenset[Name]) -> Name | None:
    """Return the longest of ``names`` that ``words`` start with (whole words).

    Returns:
        The name, or ``None``.
    """
    lengths = range(1, _LONGEST + 1)
    prefixes = (words[:length] for length in lengths)
    found = [prefix for prefix in prefixes if prefix in names]
    return found[-1] if found else None


def _anywhere(words: Name, names: frozenset[Name]) -> Name | None:
    """Return the first of ``names`` found in ``words`` (whole words, any position).

    Returns:
        The name, or ``None``.
    """
    starts = range(len(words))
    tails = (words[start:] for start in starts)
    leading = (_leading(tail, names) for tail in tails)
    return next((name for name in leading if name), None)


def _signals_tobacco(text: str, labels: str, *, other_goods: bool) -> bool:
    """Return whether a folded title or its brand and category read as tobacco (module docstring, layers 1 to 3).

    ``other_goods``: the title names a non-tobacco context, which overrides layer 3.

    Returns:
        ``True`` on a kind word, a tobacco-only format, or an ambiguous word or count outside a non-tobacco context.
    """
    named = (rules.KIND_WORDS, rules.JAPANESE_BRANDS, rules.CHINESE_BRANDS)
    if any(rule.search(text) or rule.search(labels) for rule in named):
        return True
    formats = (rules.TAX_STAMP, rules.PACK, rules.NICOTINE_FORMAT, rules.SMOKING_ACCESSORY)
    if any(rule.search(text) for rule in formats):
        return True
    if other_goods:
        return False
    counted = rules.CONTEXT_SIGNS.search(text) is not None and OTHER_GOODS_TITLE.search(text) is None
    return rules.AMBIGUOUS_WORDS.search(text) is not None or rules.LABEL_WORDS.search(labels) is not None or counted


def _branded(title: str, brand: str | None, text: str, *, other_goods: bool) -> bool:
    """Return whether a product carries a tobacco brand (module docstring, layer 4).

    Returns:
        ``True`` on an exclusive brand, or a dual brand with a tobacco sign or a title of names only outside a
        non-tobacco context.
    """
    words = name_words(title)
    brand_pieces = _BRAND_PARTS.split(folded(brand))
    piece_words = (name_words(piece) for piece in brand_pieces)
    worded = (part for part in piece_words if part)
    parts = [part for part in worded if part not in _PLACEHOLDER_BRANDS]
    if _leading(words, _EXCLUSIVE) or any(_leading(part, _EXCLUSIVE) for part in parts):
        return True
    in_title = _anywhere(words, _EXCLUSIVE)
    duals = (_leading(part, _DUAL) for part in parts)
    dual = next((name for name in duals if name), None)
    if in_title and (dual or not parts):
        return True
    named = dual or (None if parts else _anywhere(words, _DUAL)) or in_title
    if named is None:
        return False
    if rules.TAR_STRENGTH.search(text):
        return True
    return not other_goods and _reads_as_tobacco(words, named, text, led_by_brand_field=dual is not None)


def _reads_as_tobacco(words: Name, named: Name, text: str, *, led_by_brand_field: bool) -> bool:
    """Return whether a title of the dual brand ``named`` reads as tobacco (module docstring, layer 4).

    ``led_by_brand_field``: the brand field names a dual brand (the trailing strength counts only on a title it
    leads).

    Returns:
        ``True`` on a weaker tobacco sign, a sub-line of the brand, a title of names only, or a trailing strength.
    """
    sub_lines = _SUB_LINES.get(named, frozenset())
    if rules.DUAL_SIGNS.search(text) or _anywhere(words, sub_lines):
        return True
    if bool(words) and all(word in named or word in rules.VARIANT_WORDS for word in words):
        return True
    if not (led_by_brand_field and words[: len(named)] == named and words[-1] in rules.STRENGTH_ENDINGS):
        return False
    middle = words[len(named) : -1]
    unnamed = [word for word in middle if word not in rules.VARIANT_WORDS]
    return len(unnamed) <= 1 and len(unnamed) < len(middle)


@lru_cache(maxsize=SCREENED_PRODUCTS)
def _named_restricted(title: str, brand: str | None, category: str | None) -> bool:
    """Return whether a product's title, brand or category signals tobacco or nicotine (layers 1 to 4).

    Returns:
        ``True`` on any of the module docstring's first four layers.
    """
    text = folded(title)
    labels = f"{folded(brand)} {folded(category)}".strip()
    other_goods = rules.NON_TOBACCO_CONTEXT.search(text) is not None
    return _signals_tobacco(text, labels, other_goods=other_goods) or _branded(
        title,
        brand,
        text,
        other_goods=other_goods,
    )


def is_restricted(title: str, brand: str | None, category: str | None, description: str | None = None) -> bool:
    """Return whether a product is tobacco or nicotine and must not appear in any result.

    ``description``: the product's own description, where the answer carries one (layer 5).

    Returns:
        ``True`` when its title, brand, category or description signals tobacco or nicotine (module docstring).
    """
    if _named_restricted(title, brand, category):
        return True
    text = folded(description)
    return rules.DESCRIPTION_SIGNS.search(text) is not None or describes_tobacco(folded(title), text)
