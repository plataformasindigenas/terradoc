"""`terradoc export`: sources → normalised, cross-linked JSON bundle.

The bundle (``config.bundle_dir``) holds one JSON file per enabled module plus
``index.json`` and ``manifest.json``. `terradoc render` reads only the bundle.

The bundle layout is EXPERIMENTAL (``bundle_schema: "0-experimental"``): it is
the intended contract for a future, non-Jinja renderer, but it is not frozen
until such a renderer actually consumes it.
"""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from terradoc.config import TerradocConfig

BUNDLE_SCHEMA = "0-experimental"


def terradoc_version() -> str:
    try:
        return version("terradoc")
    except PackageNotFoundError:  # running from a source tree
        return "unknown"


def export_bundle(config: TerradocConfig, *, run_checks: bool = True) -> dict[str, int]:
    """Write the bundle and return per-module record counts.

    With ``run_checks`` the historic encyclopedia entry check runs first (the
    behaviour of `terradoc build` before 0.11); `terradoc check` performs the
    full rule set separately.
    """
    if run_checks and config.is_module_enabled("encyclopedia"):
        from terradoc.check_entries import check_entries

        if check_entries(config.data_dir) != 0:
            raise SystemExit(1)
        print()

    from terradoc.convert import run_all_converters
    from terradoc.cross_linker import (
        attach_audio_to_dictionary,
        attach_recordings_to_dictionary,
        cross_link_datasets,
    )
    from terradoc.index_builder import generate_index

    counts = run_all_converters(config)

    if config.is_module_enabled("recordings") and config.is_module_enabled("dictionary"):
        attach_recordings_to_dictionary(config)
        print()
    if config.is_module_enabled("dictionary"):
        attach_audio_to_dictionary(config)
        print()
    cross_link_datasets(config)
    print()

    generate_index(counts, config)
    print()

    write_manifest(config, counts)
    return counts


def write_manifest(config: TerradocConfig, counts: dict[str, int]) -> Path:
    files = sorted(
        p.name for p in config.bundle_dir.glob("*.json") if p.name != "manifest.json"
    ) if config.bundle_dir != config.data_dir else sorted(
        f"{name}.json" for name in counts
    )
    manifest = {
        "bundle_schema": BUNDLE_SCHEMA,
        "terradoc_version": terradoc_version(),
        "project": config.meta_prefix,
        "modules": counts,
        "files": files,
    }
    path = config.bundle_dir / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_manifest(config: TerradocConfig) -> dict:
    path = config.bundle_dir / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No export bundle at {config.bundle_dir} (manifest.json missing); "
            "run `terradoc export` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))
