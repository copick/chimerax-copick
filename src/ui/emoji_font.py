"""Bundled color-emoji font support.

Several toolbar/table buttons use emoji characters as their labels (🔄, 🔍, 🧊,
📸, ⚙, ❌ ...). On Linux, ChimeraX's Qt has no color-emoji system font to fall
back on, so these render as "tofu" boxes or ugly monochrome glyphs. To get
consistent rendering across platforms we ship OpenMoji and register it at runtime
via ``QFontDatabase``.

IMPORTANT: the bundled font is **subsetted to emoji codepoints only** (see
``tools/regenerate_font_subset.py``). We install it as a fallback *family*, and Qt's
family list is a per-character fallback chain with no emoji-only mode before Qt
6.9's emoji-segmenter (which ChimeraX does not yet ship). The full OpenMoji covers
ordinary characters too (letters, digits, ``-`` ...), so it would hijack normal
text — breaking spacing and turning ``-`` into OpenMoji's dash. The subset removes
those glyphs, so only emoji route to OpenMoji. Do NOT replace it with the full
font; regenerate via ``regenerate_subset.py`` instead.

We bundle the **COLRv0** build (``glyf_colr_0``), not COLRv1: ChimeraX's bundled
FreeType fails to rasterize COLRv1 color glyphs (``render glyph failed err=9e``),
producing blank buttons. COLRv0 renders in color on the Qt versions ChimeraX
ships (verified on Qt 6.8.2). COLRv0 is also ~4x smaller than the COLRv1 build.

OpenMoji is licensed CC BY-SA 4.0 (see ``fonts/OpenMoji-LICENSE.txt``).
"""

import os
import sys

from Qt.QtGui import QFontDatabase

_FONT_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "fonts", "OpenMoji-color-glyf_colr_0.ttf"),
)

# Cache: None once resolved-and-failed, the family string once resolved-and-loaded.
_family = None
_resolved = False

# Guard so the attribution is logged at most once per session.
_attribution_logged = False


def emoji_font_family():
    """Register the bundled emoji font (once) and return its family name.

    Returns ``None`` if the font file is missing or fails to load, so callers can
    degrade gracefully to the platform's default emoji rendering. Requires a
    ``QApplication`` to exist, so only call from GUI construction code.
    """
    global _family, _resolved
    if _resolved:
        return _family
    _resolved = True
    if os.path.exists(_FONT_PATH):
        font_id = QFontDatabase.addApplicationFont(_FONT_PATH)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                _family = families[0]
    return _family


def apply_emoji_font(*widgets):
    """Add the bundled emoji font as a fallback family on each widget's font.

    The widget's current primary family and point size are preserved, so Latin
    text keeps using the UI font and only characters the UI font lacks (the
    emoji) fall back to OpenMoji. No-op if the font could not be loaded.

    Only applied on Linux: macOS and Windows already ship good color-emoji fonts
    (Apple Color Emoji / Segoe UI Emoji), so we leave their native rendering
    alone and only substitute OpenMoji where the platform falls short.

    Call this *after* ``setStyleSheet`` on the widget: a stylesheet that sets a
    font property re-resolves the widget font, which can drop a family set
    beforehand.
    """
    if not sys.platform.startswith("linux"):
        return
    family = emoji_font_family()
    if not family:
        return
    for widget in widgets:
        font = widget.font()
        font.setFamilies([font.family(), family])
        widget.setFont(font)


def log_emoji_attribution(session):
    """Log a one-time OpenMoji attribution notice to the ChimeraX log.

    CC BY-SA 4.0 asks for attribution wherever the work is used. The bundled
    OpenMoji glyphs are only rendered on Linux (see ``apply_emoji_font``), so we
    surface the notice there — once per session, and only if the font actually
    loaded. The Log is used because it persists and renders the clickable
    license/project links. No-op on other platforms or if the font is absent.
    """
    global _attribution_logged
    if _attribution_logged or not sys.platform.startswith("linux"):
        return
    if not emoji_font_family():
        return
    _attribution_logged = True
    session.logger.info(
        "Emoji glyphs are rendered with "
        '<a href="https://openmoji.org">OpenMoji</a>, licensed under '
        '<a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>.',
        is_html=True,
    )
