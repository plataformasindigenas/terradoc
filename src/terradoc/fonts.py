"""v2 fonts: subset the vendored faces to the characters one site uses.

The vendored files (fonts_v2/, made by scripts/vendor_fonts.py) hold the Latin, IPA, Greek
and combining-mark ranges. A site needs a small part of that, so each build subsets them to
the characters in the site's data, interface strings and alphabet (measured 2026-11-18: about
9 KB per style). IPA stays in the same file: the IPA-only characters added 0.4–1.2 KB, less
than a second request would cost.

Coverage: a character in the covered ranges that the text face lacks is an error, so a new
letter in the data cannot fall back to another font unnoticed. Characters outside those
ranges (other scripts, emoji) are left to the browser's fallback fonts.
"""
from __future__ import annotations

import hashlib
import importlib.resources
import io
import logging
import unicodedata
from dataclasses import dataclass
from pathlib import Path

# Same list as scripts/vendor_fonts.py RANGES (tests/test_v2.py keeps them in step).
COVERED = (
    (0x0020, 0x007E), (0x00A0, 0x024F), (0x0250, 0x02FF), (0x0300, 0x036F),
    (0x0370, 0x03FF), (0x1AB0, 0x1AFF), (0x1D00, 0x1DFF), (0x1E00, 0x1EFF),
    (0x2000, 0x206F), (0x20A0, 0x20CF), (0x2100, 0x214F), (0x2190, 0x2193),
    (0x2C60, 0x2C7F), (0xA720, 0xA7FF), (0xAB30, 0xAB6F), (0xFB00, 0xFB06),
)
# Kept OpenType features: mark placement (stacked diacritics), kerning, ligatures. Small
# caps and figure styles are dropped (measured: 15 KB with every feature, 10.8 KB without).
LAYOUT_FEATURES = ["ccmp", "locl", "mark", "mkmk", "kern", "liga", "calt"]
# Format and layout characters a font need not have.
IGNORED_CATEGORIES = ("Cc", "Cf", "Zl", "Zp")


@dataclass(frozen=True)
class Face:
    file: str       # vendored file in fonts_v2/
    family: str     # CSS family
    weight: int
    style: str      # normal | italic
    critical: bool  # preloaded on every page

    @property
    def stem(self) -> str:
        """Name of the shipped file before its hash: td-text-400, td-ui-400."""
        suffix = f"{self.weight}{'i' if self.style == 'italic' else ''}"
        return f"{self.family}-{suffix}"


# The text face (td-text) is chosen per site with theme.font_vernacular; Gentium by default.
# Charis was the first choice (D16), but its tilde is so flat that ã õ ũ read as ā ō ū at
# text sizes (2026-11-18, screenshots at 17–24 px); Gentium and Andika draw a clear tilde.
TEXT_FACES = ("charis", "gentium", "andika")


def faces(text: str = "gentium") -> tuple[Face, ...]:
    if text not in TEXT_FACES:
        raise ValueError(f"theme.font_vernacular: '{text}' is not available (v2 has: {', '.join(TEXT_FACES)})")
    return (
        Face(f"td-{text}-400.woff2", "td-text", 400, "normal", True),
        Face(f"td-{text}-400i.woff2", "td-text", 400, "italic", False),
        Face(f"td-{text}-700.woff2", "td-text", 700, "normal", False),
        Face("td-ui-400.woff2", "td-ui", 400, "normal", True),
    )


FACES = faces("gentium")
# The interface uses one weight, so a page needs at most two font files before its content
# (the text face 400 and Source Sans 400).


@dataclass(frozen=True)
class BuiltFace:
    face: Face
    name: str   # file name written, e.g. td-text-400.3f2a1b9c9d.woff2
    size: int


def covered(ch: str) -> bool:
    cp = ord(ch)
    return any(a <= cp <= b for a, b in COVERED)


def _vendored(name: str) -> Path:
    return Path(str(importlib.resources.files("terradoc.fonts_v2") / name))


def collect(strings) -> set[str]:
    """Every character in `strings` (an iterable of str), NFC and NFD forms both, so a
    precomposed letter and its base + combining mark are both available."""
    chars: set[str] = set()
    for s in strings:
        chars.update(unicodedata.normalize("NFC", s))
        chars.update(unicodedata.normalize("NFD", s))
    return {c for c in chars if unicodedata.category(c) not in IGNORED_CATEGORIES}


def strings_in(obj):
    """Every string inside a JSON-like value."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from strings_in(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from strings_in(v)


def missing(chars: set[str], text: str = "gentium") -> list[str]:
    """Covered-range characters the text face lacks (sorted)."""
    from fontTools.ttLib import TTFont

    cmap = TTFont(_vendored(faces(text)[0].file)).getBestCmap()
    return sorted(c for c in chars if covered(c) and ord(c) not in cmap)


def missing_in_built(chars: set[str], built: list["BuiltFace"], out_dir: Path) -> dict[str, list[str]]:
    """Covered-range characters each shipped text-face subset lacks ({file: chars}). The
    interface face may lack some (IPA, rare letters): the browser then uses td-text."""
    from fontTools.ttLib import TTFont

    out = {}
    for b in built:
        if b.face.family != "td-text":
            continue
        cmap = TTFont(out_dir / b.name).getBestCmap()
        lacking = sorted(c for c in chars if covered(c) and ord(c) not in cmap)
        if lacking:
            out[b.name] = lacking
    return out


def build(chars: set[str], out_dir: Path, text: str = "gentium") -> list[BuiltFace]:
    """Subset every face to `chars` (the covered ones) into out_dir; names carry a content
    hash, so a changed subset never meets a cached old one."""
    from fontTools import subset
    from fontTools.ttLib import TTFont

    logging.getLogger("fontTools").setLevel(logging.ERROR)
    unicodes = sorted({ord(c) for c in chars if covered(c)} | {0x20, 0xA0})
    out_dir.mkdir(parents=True, exist_ok=True)
    built = []
    for face in faces(text):
        # recalcTimestamp=False: saving must not write the current time into head.modified,
        # or every build gives new bytes, new names and new pages (sitepull hardlinks).
        font = TTFont(_vendored(face.file), recalcTimestamp=False)
        opts = subset.Options()
        opts.layout_features = LAYOUT_FEATURES
        opts.name_IDs = ["*"]
        opts.notdef_outline = True
        opts.hinting = False
        opts.flavor = "woff2"
        sub = subset.Subsetter(opts)
        sub.populate(unicodes=unicodes)
        sub.subset(font)
        font.flavor = "woff2"
        buf = io.BytesIO()
        font.save(buf)
        data = buf.getvalue()
        stem = face.stem
        name = f"{stem}.{hashlib.sha256(data).hexdigest()[:10]}.woff2"
        (out_dir / name).write_bytes(data)
        built.append(BuiltFace(face, name, len(data)))
    return built


def font_face_css(built: list[BuiltFace], url_prefix: str) -> str:
    rules = []
    for b in built:
        rules.append(
            "@font-face{font-family:%s;font-style:%s;font-weight:%d;font-display:swap;"
            "src:url(%s%s) format('woff2')}" % (b.face.family, b.face.style, b.face.weight,
                                                url_prefix, b.name))
    return "\n".join(rules) + "\n"


def licence_text() -> str:
    return _vendored("LICENSES.md").read_text(encoding="utf-8")
