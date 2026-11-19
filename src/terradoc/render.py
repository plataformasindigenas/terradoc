"""The render step (export bundle → site): static/, the site itself (build_v2), audio,
robots.txt and .release.json, and the guard around --clean. Until 0.23.0 this lived in
build_site.py next to the v1 renderer."""

import json
import shutil
from pathlib import Path

from terradoc.config import TerradocConfig


def copy_audio_files(config: TerradocConfig):
    """Mirror data/audio/*.webm → docs/audio/. Files starting with '_' (reports
    like _import_report.md) are skipped. With data/audio/manifest.tsv, only the
    files it lists with consent are published."""
    from terradoc.checks import CONSENT_VALUES
    from terradoc.cross_linker import read_audio_manifest

    src_dir = config.data_dir / "audio"
    if not src_dir.exists():
        return
    manifest = read_audio_manifest(src_dir)
    allowed = None if manifest is None else {
        row["file"] for row in manifest if row["consent"] in CONSENT_VALUES}
    dest_dir = config.docs_dir / "audio"
    dest_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for src_file in sorted(src_dir.iterdir()):
        if not src_file.is_file() or src_file.name.startswith("_"):
            continue
        if src_file.suffix.lower() != ".webm":
            continue
        if allowed is not None and src_file.name not in allowed:
            continue
        shutil.copy2(str(src_file), str(dest_dir / src_file.name))
        n += 1
    if n:
        print(f"  Copied {n} audio files to docs/audio/")


def write_robots_txt(docs_dir: Path, base_url: str = ""):
    """Write a robots.txt file to the docs directory (Sitemap only with an absolute URL)."""
    content = "User-agent: *\nAllow: /\n"
    if base_url:
        content += f"Sitemap: {base_url.rstrip('/')}/sitemap.xml\n"
    (docs_dir / "robots.txt").write_text(content, encoding="utf-8")
    print("  Generated robots.txt")


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_project_static(config: TerradocConfig) -> dict[str, str]:
    """Copy <project>/static/ verbatim into the site root.

    Returns {relative path: sha256} so the caller can prove afterwards that
    no generated file overwrote a static one. Symlinks are refused: the site
    must be plain files.
    """
    src_root = config.static_dir
    copied: dict[str, str] = {}
    if src_root.is_symlink():
        raise ValueError("static/ is a symlink; it must be a real directory")
    if not src_root.is_dir():
        return copied
    for src in sorted(src_root.rglob("*")):
        rel = src.relative_to(src_root).as_posix()
        if src.is_symlink():
            raise ValueError(f"static/{rel} is a symlink; only regular files are allowed")
        if src.is_dir():
            continue
        dest = config.docs_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied[rel] = _sha256(src)
    print(f"  Copied {len(copied)} files from static/")
    return copied


def verify_static_untouched(config: TerradocConfig, copied: dict[str, str]) -> None:
    clobbered = [rel for rel, digest in copied.items()
                 if _sha256(config.docs_dir / rel) != digest]
    if clobbered:
        raise ValueError(
            "generated files overwrote files from static/ (rename them): "
            + ", ".join(sorted(clobbered)[:10])
        )


def _git(config: TerradocConfig, *args: str) -> str:
    import subprocess

    try:
        out = subprocess.run(["git", "-C", str(config.base_dir), *args],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def write_release_info(config: TerradocConfig, *, owned: bool = False) -> Path:
    """Write .release.json: what this site was built from (no timestamps, so
    identical inputs give an identical file)."""
    import os

    from terradoc.export import read_manifest, terradoc_version

    files = [p for p in config.docs_dir.rglob("*") if p.is_file() and p.name != ".release.json"]
    try:
        modules = read_manifest(config).get("modules", {})
    except FileNotFoundError:
        modules = {}
    info = {
        "project": config.meta_prefix,
        "terradoc_version": terradoc_version(),
        "source_commit": os.environ.get("GITHUB_SHA") or _git(config, "rev-parse", "HEAD"),
        "source_ref": os.environ.get("GITHUB_REF_NAME") or _git(config, "rev-parse", "--abbrev-ref", "HEAD"),
        "files": len(files),
        "bytes": sum(p.stat().st_size for p in files),
        "modules": modules,  # record counts, compared by `terradoc guard`
        # True only if every render into this directory started from an empty
        # one, i.e. everything in it came from terradoc. --clean requires it.
        "owned_by_terradoc": owned,
    }
    path = config.docs_dir / ".release.json"
    path.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    return path


def _overlaps(a: Path, b: Path) -> bool:
    """True if a and b are the same directory or one contains the other."""
    return a == b or a in b.parents or b in a.parents


def assert_safe_to_clean(config: TerradocConfig) -> None:
    """Refuse to empty an output directory unless it is plainly ours.

    `--clean` deletes the output directory, so it must not be (or contain, or
    sit inside) the project, its sources, its templates or the bundle, and a
    non-empty directory is only deleted if a previous render marked it with
    .release.json.
    """
    if config.output_dir is None:
        raise ValueError("--clean needs --out (refusing to delete the project's docs/)")
    out = config.docs_dir.resolve()
    base = config.base_dir.resolve()
    if out == base or out in base.parents:
        raise ValueError(f"--clean refused: --out {out} is the project directory or contains it")
    protected = {
        "data/": config.data_dir, "config/": config.config_dir, "static/": config.static_dir,
        "locales/": config.locales_dir, "the bundle": config.bundle_dir,
        "the templates": config.local_template_dir,
    }
    for label, path in protected.items():
        if _overlaps(out, path.resolve()):
            raise ValueError(f"--clean refused: --out {out} overlaps {label} ({path})")
    if out.exists() and any(out.iterdir()) and not _dir_owned(out):
        raise ValueError(
            f"--clean refused: {out} holds files terradoc did not create (it was not built "
            "into an empty directory by terradoc >= 0.11). Check it, delete it yourself once, "
            "and --clean will work from then on."
        )


def _dir_owned(out: Path) -> bool:
    """Did every render into `out` start from an empty directory?"""
    marker = out / ".release.json"
    if not marker.is_file():
        return False
    try:
        return json.loads(marker.read_text(encoding="utf-8")).get("owned_by_terradoc") is True
    except (OSError, ValueError):
        return False


def render_site(config: TerradocConfig, *, clean: bool = False) -> None:
    """Render the site from the export bundle into config.docs_dir."""
    from terradoc.export import read_manifest

    read_manifest(config)  # fail early, clearly, if export has not run

    # The bundle may be older than the sources: re-check what must never be
    # published from a stale bundle (consent revoked since the export), and
    # static/ (symlinks, collisions with generated files).
    from terradoc.checks import format_issues, render_preflight

    issues = render_preflight(config)
    if issues:
        raise ValueError("render refused:\n" + format_issues(issues))

    if clean:
        assert_safe_to_clean(config)
        if config.docs_dir.exists():
            shutil.rmtree(config.docs_dir)
    config.docs_dir.mkdir(parents=True, exist_ok=True)
    started_empty = not any(config.docs_dir.iterdir())
    owned = started_empty or _dir_owned(config.docs_dir)

    copied = copy_project_static(config)
    from terradoc.build_v2 import build_site_v2

    build_site_v2(config)
    write_release_info(config, owned=owned)
    verify_static_untouched(config, copied)

