#!/usr/bin/env python3
"""Vendor the v2 fonts: Charis (text, vernacular, IPA) and Source Sans 3 (interface).

Downloads the pinned upstream releases, checks their sha256, keeps only the Latin, IPA,
Greek and combining-mark ranges (what any site can need; the build later subsets each
font to the site's own characters) and renames the families `td-text` and `td-ui`, since
"Charis", "SIL" and "Source" are Reserved Font Names under the SIL Open Font License and a
modified font may not carry them. Writes src/terradoc/fonts_v2/ (woff2 + licences).

Run it only to move to a new upstream release (update RELEASES first):

    python scripts/vendor_fonts.py
"""
import hashlib
import io
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

OUT = Path(__file__).resolve().parent.parent / "src" / "terradoc" / "fonts_v2"
UA = {"User-Agent": "terradoc-vendor-fonts/1.0 (python-urllib)"}

RELEASES = {
    "charis": {
        "url": "https://github.com/silnrsi/font-charis/releases/download/v7.000/Charis-7.000.zip",
        "sha256": "e3237b1303c5d31af8f59b1d1914886c5e873b77c71390e4742fb3bc1c187666",
        "licence": "Charis-7.000/OFL.txt",
    },
    "source-sans": {
        "url": "https://github.com/adobe-fonts/source-sans/releases/download/3.052R/TTF-source-sans-3.052R.zip",
        "sha256": "1b0dd1ec44b39f1dd98bbd153a1a3815f083639874ddee02c842bd601bad3d21",
        "licence_url": "https://raw.githubusercontent.com/adobe-fonts/source-sans/3.052R/LICENSE.md",
        "licence_sha256": "89ad2c4f66dd29127527493e729c31e731f111cf10faf5774c3db9275ed0c22c",
    },
}

# (release, file in the zip, family, style name, output name)
FONTS = [
    ("charis", "Charis-7.000/Charis-Regular.ttf", "td-text", "Regular", "td-text-400.woff2"),
    ("charis", "Charis-7.000/Charis-Italic.ttf", "td-text", "Italic", "td-text-400i.woff2"),
    ("charis", "Charis-7.000/Charis-Bold.ttf", "td-text", "Bold", "td-text-700.woff2"),
    ("source-sans", "TTF/SourceSans3-Regular.ttf", "td-ui", "Regular", "td-ui-400.woff2"),
    ("source-sans", "TTF/SourceSans3-Semibold.ttf", "td-ui", "Semibold", "td-ui-600.woff2"),
]

# Kept ranges; terradoc.fonts.COVERED is the same list (a test keeps them in step).
RANGES = [
    (0x0020, 0x007E), (0x00A0, 0x024F), (0x0250, 0x02FF), (0x0300, 0x036F),
    (0x0370, 0x03FF), (0x1AB0, 0x1AFF), (0x1D00, 0x1DFF), (0x1E00, 0x1EFF),
    (0x2000, 0x206F), (0x20A0, 0x20CF), (0x2100, 0x214F), (0x2190, 0x2193),
    (0x2C60, 0x2C7F), (0xA720, 0xA7FF), (0xAB30, 0xAB6F), (0xFB00, 0xFB06),
]
FEATURES = ["ccmp", "locl", "mark", "mkmk", "kern", "liga", "calt", "case", "onum", "lnum",
            "tnum", "pnum", "smcp", "c2sc", "ss01", "cv01"]


def fetch(url: str, sha: str | None = None) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        data = r.read()
    if sha and hashlib.sha256(data).hexdigest() != sha:
        sys.exit(f"{url}: sha256 mismatch")
    return data


def rename(font: TTFont, family: str, style: str) -> None:
    name = font["name"]
    keep = {0, 7, 8, 9, 11, 12, 13, 14}  # copyright, trademark, maker, licence, urls
    name.names = [n for n in name.names if n.nameID in keep]
    full = f"{family} {style}" if style != "Regular" else family
    for nid, value in {1: family if style in ("Regular", "Italic", "Bold") else f"{family} {style}",
                       2: style if style in ("Regular", "Italic", "Bold") else "Regular",
                       3: f"terradoc:{family}-{style}", 4: full,
                       5: "Version 1.000", 6: f"{family}-{style}".replace(" ", ""),
                       16: family, 17: style}.items():
        name.setName(value, nid, 3, 1, 0x409)
    name.setName("Modified (subset, renamed) by terradoc from an OFL font; see LICENSES.md.",
                 10, 3, 1, 0x409)


def main() -> None:
    zips = {}
    for key, rel in RELEASES.items():
        print("fetching", rel["url"])
        zips[key] = zipfile.ZipFile(io.BytesIO(fetch(rel["url"], rel["sha256"])))
    if OUT.exists():
        for p in OUT.glob("*.woff2"):
            p.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "__init__.py").write_text("")
    unicodes = [c for a, b in RANGES for c in range(a, b + 1)]
    for key, member, family, style, out in FONTS:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "f.ttf"
            path.write_bytes(zips[key].read(member))
            font = TTFont(path, recalcTimestamp=False)
            opts = subset.Options()
            opts.layout_features = FEATURES
            opts.name_IDs = ["*"]
            opts.name_languages = [0x409]
            opts.notdef_outline = True
            opts.glyph_names = False
            opts.drop_tables += ["Silf", "Glat", "Gloc", "Feat", "Sill", "DSIG"]  # Graphite
            sub = subset.Subsetter(opts)
            sub.populate(unicodes=unicodes)
            sub.subset(font)
            rename(font, family, style)
            font.flavor = "woff2"
            font.save(OUT / out)
        print(f"  {out}: {(OUT / out).stat().st_size / 1024:.0f} KB")
    licences = ["# Font licences\n",
                "The fonts here are modified (subset, renamed) versions of OFL fonts. "
                "`td-text` is Charis 7.000 by SIL Global; `td-ui` is Source Sans 3.052 by "
                "Adobe. Upstream releases and checksums: scripts/vendor_fonts.py.\n"]
    charis = zips["charis"].read(RELEASES["charis"]["licence"]).decode("utf-8")
    sans = fetch(RELEASES["source-sans"]["licence_url"], RELEASES["source-sans"]["licence_sha256"]).decode("utf-8")
    licences += ["\n## td-text (Charis)\n\n", charis, "\n\n## td-ui (Source Sans 3)\n\n", sans]
    (OUT / "LICENSES.md").write_text("".join(licences), encoding="utf-8")


if __name__ == "__main__":
    main()
