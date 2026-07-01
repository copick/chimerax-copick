#!/usr/bin/env python3
"""Regenerate the bundled OpenMoji subset used for emoji rendering on Linux.

Why subset at all: we install OpenMoji as a *fallback* font family on Qt widgets
(see ``ui/emoji_font.py``). Qt's family list is a per-character fallback chain with
no "emoji-only" mode before Qt 6.9's emoji-segmenter (which ChimeraX does not yet
ship). The full OpenMoji font contains glyphs for ordinary text characters too
(letters, digits, ``-``, ``#`` ...), so as a fallback it hijacks normal text —
throwing off spacing and turning ``-`` into OpenMoji's dash. Subsetting the font
down to *emoji codepoints only* makes that impossible: the font physically cannot
render those text characters, so Qt keeps using the UI font for them.

What we keep: every codepoint OpenMoji supports that has the Unicode ``Emoji``
property (so any pictographic emoji you use later just works), plus the emoji
mechanism codepoints (ZWJ, variation selectors, keycap combiner, regional
indicators, tags), plus ``✕`` (U+2715, used by the clear button and not an emoji).

What we drop: the "special character" emoji — codepoints that are also ordinary
text characters and would collide with real text (keycap bases ``#`` ``*``
``0``-``9``, ``©`` ``®`` ``™`` ``‼`` ``⁉``). Their keycap emoji sequences are the
price of not corrupting normal digits/text; that is an accepted limitation.

Run: ``python tools/regenerate_font_subset.py`` (downloads inputs, pinned below),
or pass ``--font <full-openmoji.ttf>`` and/or ``--emoji-data <emoji-data.txt>`` to
use local copies. Overwrites ``src/fonts/OpenMoji-color-glyf_colr_0.ttf``.
"""

import argparse
import os
import tempfile
import urllib.request

from fontTools import subset
from fontTools.ttLib import TTFont

# Pinned sources for reproducibility.
OPENMOJI_VERSION = "17.0.0"
FULL_FONT_URL = (
    f"https://raw.githubusercontent.com/hfg-gmuend/openmoji/{OPENMOJI_VERSION}"
    "/font/OpenMoji-color-glyf_colr_0/OpenMoji-color-glyf_colr_0.ttf"
)
EMOJI_DATA_URL = "https://www.unicode.org/Public/UCD/latest/ucd/emoji/emoji-data.txt"

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.normpath(os.path.join(HERE, "..", "src", "fonts", "OpenMoji-color-glyf_colr_0.ttf"))

# "Special character" emoji to drop — Emoji-property codepoints that are also
# ordinary text characters and would hijack normal text via the fallback font.
SPECIAL_CHARACTER_EMOJI = (
    {0x23, 0x2A}                 # # *  (keycap bases)
    | set(range(0x30, 0x3A))     # 0-9  (keycap bases)
    | {0xA9, 0xAE}               # © ®
    | {0x2122}                   # ™
    | {0x203C, 0x2049}           # ‼ ⁉
)

# Emoji sequence "mechanism" codepoints to keep (invisible / combining; never
# collide with text) so ZWJ sequences, variation selectors and flags keep working.
EMOJI_MECHANISM = (
    {0x200D, 0xFE0E, 0xFE0F, 0x20E3}
    | set(range(0x1F1E6, 0x1F200))   # regional indicator symbols (flags)
    | set(range(0xE0020, 0xE0080))   # tag characters (subdivision flags)
)

# Non-emoji symbols used verbatim in the UI that we still want the font to cover.
EXTRA_KEEP = {0x2715}  # ✕ clear button


def _download(url):
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


def load_emoji_codepoints(emoji_data_path=None):
    """Return the set of codepoints with the Unicode ``Emoji`` property."""
    if emoji_data_path:
        with open(emoji_data_path, "rb") as fh:
            data = fh.read()
    else:
        data = _download(EMOJI_DATA_URL)
    codepoints = set()
    for raw in data.decode("utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        cps, _, prop = (p.strip() for p in line.partition(";"))
        if prop != "Emoji":  # ignore Emoji_Presentation / Extended_Pictographic / ...
            continue
        if ".." in cps:
            lo, hi = cps.split("..")
            codepoints.update(range(int(lo, 16), int(hi, 16) + 1))
        else:
            codepoints.add(int(cps, 16))
    return codepoints


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", help="Path to the full OpenMoji COLRv0 TTF (else downloaded)")
    parser.add_argument("--emoji-data", help="Path to emoji-data.txt (else downloaded)")
    args = parser.parse_args()

    emoji_cps = load_emoji_codepoints(args.emoji_data)

    if args.font:
        font_path = args.font
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".ttf", delete=False)
        tmp.write(_download(FULL_FONT_URL))
        tmp.close()
        font_path = tmp.name

    supported = set(TTFont(font_path).getBestCmap().keys())

    keep = ((emoji_cps & supported) - SPECIAL_CHARACTER_EMOJI) | (EMOJI_MECHANISM & supported) | (
        EXTRA_KEEP & supported
    )

    options = subset.Options()
    options.name_IDs = ["*"]  # keep name table (family name must survive)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=sorted(keep))
    font = TTFont(font_path)
    subsetter.subset(font)
    font.save(OUTPUT)

    print(f"Kept {len(keep)} codepoints -> {OUTPUT} ({os.path.getsize(OUTPUT)} bytes)")


if __name__ == "__main__":
    main()
