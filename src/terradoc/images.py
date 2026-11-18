"""v2 responsive images: WebP copies at a few widths, never upscaled.

Only images a v2 page references are processed. Output names carry a hash of the source
bytes and the settings, so the same input gives the same bytes and name on every build
(sitepull hardlinks unchanged files between releases).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

WIDTHS = (480, 960, 1600)
QUALITY = 72
SETTINGS = f"webp-q{QUALITY}-m6-v1"


@dataclass
class Derived:
    src: str                 # the original, relative to the site root (fallback src)
    width: int
    height: int
    webp: list[tuple[str, int]] = field(default_factory=list)  # (path from site root, width)

    def srcset(self, prefix: str) -> str:
        return ", ".join(f"{prefix}{p} {w}w" for p, w in self.webp)


def derive(source: Path, rel: str, out_root: Path, sub: str = "assets/img") -> Derived:
    """WebP copies of `source` (served at `rel`) into out_root/sub/."""
    import PIL
    from PIL import Image, ImageOps

    data = source.read_bytes()
    # The encoder version is part of the name: a Pillow/libwebp upgrade may change the bytes.
    key = hashlib.sha256(data + f"{SETTINGS}-pil{PIL.__version__}".encode()).hexdigest()[:10]
    with Image.open(source) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "transparency" in im.info else "RGB")
        result = Derived(rel, im.width, im.height)
        stem = Path(rel).stem
        (out_root / sub).mkdir(parents=True, exist_ok=True)
        widths = [w for w in WIDTHS if w < im.width] + [min(im.width, WIDTHS[-1])]
        for w in sorted(set(widths)):
            name = f"{sub}/{stem}-{w}.{key}.webp"
            target = out_root / name
            if not target.exists():
                h = round(im.height * w / im.width)
                copy = im if w == im.width else im.resize((w, h), Image.LANCZOS)
                partial = target.with_suffix(".part")
                copy.save(partial, "WEBP", quality=QUALITY, method=6)
                partial.replace(target)  # never leave a half-written file under the final name
            result.webp.append((name, w))
    return result
