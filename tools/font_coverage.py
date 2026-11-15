"""Regenerate src/terradoc/font_coverage.json (run after changing the bundled fonts).

A character renders in a bundled font only if it is in the font file AND inside that
@font-face's unicode-range, so coverage = union over faces of (cmap ∩ unicode-range).
Needs fontTools and brotli (dev only): python tools/font_coverage.py
"""

import json
import re
from pathlib import Path

from fontTools.ttLib import TTFont

PKG = Path(__file__).resolve().parent.parent / "src" / "terradoc"
CSS = PKG / "static" / "css" / "fonts.css"


def parse_ranges(text: str) -> set[int]:
    cps = set()
    for part in text.replace("\n", " ").split(","):
        part = part.strip().upper().removeprefix("U+")
        if not part:
            continue
        lo, _, hi = part.partition("-")
        cps.update(range(int(lo, 16), int(hi or lo, 16) + 1))
    return cps


def to_ranges(cps: set[int]) -> list[list[int]]:
    out = []
    for cp in sorted(cps):
        if out and cp == out[-1][1] + 1:
            out[-1][1] = cp
        else:
            out.append([cp, cp])
    return out


def main() -> None:
    families: dict[str, set[int]] = {}
    for face in re.findall(r"@font-face\s*\{(.*?)\}", CSS.read_text(), re.S):
        family = re.search(r"font-family:\s*'([^']+)'", face)[1]
        src = re.search(r"url\('\.\./fonts/([^']+)'\)", face)[1]
        rng = re.search(r"unicode-range:\s*([^;]+);", face)
        cmap = set(TTFont(PKG / "static" / "fonts" / src).getBestCmap())
        cps = cmap & parse_ranges(rng[1]) if rng else cmap
        families.setdefault(family, set()).update(cps)
    data = {name: to_ranges(cps) for name, cps in sorted(families.items())}
    (PKG / "font_coverage.json").write_text(json.dumps(data, separators=(",", ":")) + "\n")
    for name, cps in sorted(families.items()):
        print(f"{name}: {len(cps)} code points")


if __name__ == "__main__":
    main()
