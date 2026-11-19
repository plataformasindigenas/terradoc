"""v2 responsive images: WebP copies at a few widths, never upscaled.

Only images a v2 page references are processed. Output names carry a hash of the source
bytes and the settings, so the same input gives the same bytes and name on every build
(sitepull hardlinks unchanged files between releases).
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

WIDTHS = (480, 960, 1600)        # the home photo
CONTENT_WIDTHS = (160, 480, 960)  # list thumbnails and detail pages
QUALITY = 72
SETTINGS = f"webp-q{QUALITY}-m6-v1"


@dataclass
class Derived:
    src: str                 # the original, relative to the site root (fallback src)
    width: int
    height: int
    webp: list[tuple[str, int]] = field(default_factory=list)  # (path from site root, width)

    def srcset(self, prefix: str) -> str:
        from urllib.parse import quote
        return ", ".join(f"{prefix}{quote(p)} {w}w" for p, w in self.webp)


def derive(source: Path, rel: str, out_root: Path, sub: str = "assets/img",
           widths: tuple[int, ...] = WIDTHS) -> Derived:
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
        sizes = [w for w in widths if w < im.width] + [min(im.width, widths[-1])]
        for w in sorted(set(sizes)):
            name = f"{sub}/{stem}-{w}.{key}.webp"
            target = out_root / name
            if not target.exists():
                h = round(im.height * w / im.width)
                copy = im if w == im.width else im.resize((w, h), Image.LANCZOS)
                partial = target.with_name(f"{target.name}.{os.getpid()}.part")
                copy.save(partial, "WEBP", quality=QUALITY, method=6)
                partial.replace(target)  # never leave a half-written file under the final name
            result.webp.append((name, w))
    return result


def _derive_job(args):
    source, rel, out_root, widths = args
    try:
        return rel, derive(Path(source), rel, Path(out_root), widths=widths), ""
    except Exception as exc:  # noqa: BLE001 — any unreadable image (also decompression bombs) is skipped, not fatal
        return rel, None, f"{type(exc).__name__}: {exc}"


def derive_many(jobs: list[tuple[Path, str]], out_root: Path, widths: tuple[int, ...] = CONTENT_WIDTHS,
                workers: int | None = None) -> tuple[dict[str, Derived], dict[str, str]]:
    """derive() for many images in parallel (WebP encoding is slow and the sites have
    hundreds). Returns ({rel: Derived}, {rel: error}); the output does not depend on the
    order in which the workers finish."""
    from concurrent.futures import ProcessPoolExecutor

    done: dict[str, Derived] = {}
    failed: dict[str, str] = {}
    args = [(str(src), rel, str(out_root), widths) for src, rel in sorted(set(jobs), key=lambda j: j[1])]
    if not args:
        return done, failed
    workers = workers or min(8, os.cpu_count() or 1)
    if workers == 1 or len(args) < 8:
        results = map(_derive_job, args)
    else:
        pool = ProcessPoolExecutor(max_workers=workers)
        try:
            results = list(pool.map(_derive_job, args, chunksize=4))
        finally:
            pool.shutdown()
    for rel, derived, error in results:
        if derived is None:
            failed[rel] = error
        else:
            done[rel] = derived
    return done, failed
