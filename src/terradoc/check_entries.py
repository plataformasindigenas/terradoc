"""Validate encyclopedia markdown entries."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

HTML_TAG_RE = re.compile(r"<\s*[a-zA-Z][^>]*>")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def load_categories_vocabulary(data_dir: Path) -> set[str] | None:
    """Load optional categories vocabulary from data/categories.yaml.

    Returns a set of valid category paths, or None if no vocabulary file exists.
    """
    vocab_file = data_dir / "categories.yaml"
    if not vocab_file.exists():
        return None

    with open(vocab_file, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, list):
        print(
            f"WARNING: {vocab_file} must be a YAML list of category paths, ignoring",
            file=sys.stderr,
        )
        return None

    return {str(c) for c in raw}


def _parse_front_matter(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        raise ValueError("missing front matter start (---)")

    parts = raw.split("\n---\n", 1)
    if len(parts) != 2:
        raise ValueError("missing front matter end (---)")

    front_matter = yaml.safe_load(parts[0][4:]) or {}
    if not isinstance(front_matter, dict):
        raise ValueError("front matter must be a mapping")

    body = parts[1].lstrip("\n")
    return front_matter, body


def check_entries(data_dir: Path) -> int:
    """Check all encyclopedia entries in data_dir/encyclopedia/.

    Returns 0 on success, 1 on failure.
    """
    entries_dir = data_dir / "encyclopedia"
    if not entries_dir.exists():
        print(f"Missing encyclopedia directory: {entries_dir}", file=sys.stderr)
        return 1

    md_files = sorted(entries_dir.rglob("*.md"))
    if not md_files:
        print(f"Checked 0 entries in {entries_dir}: OK")
        return 0

    errors: list[str] = []
    seen_ids: set[str] = set()
    see_also_map: dict[str, list[str]] = {}  # entry_id -> see_also targets
    valid_categories = load_categories_vocabulary(data_dir)

    for path in md_files:
        if path.name == "README.md":
            continue

        try:
            front_matter, body = _parse_front_matter(path)
        except Exception as exc:
            errors.append(f"{path}: {exc}")
            continue

        entry_id = front_matter.get("id")
        title = front_matter.get("title") or front_matter.get("headword")
        if not entry_id:
            errors.append(f"{path}: missing 'id'")
        elif not ID_RE.match(str(entry_id)):
            errors.append(
                f"{path.name}: id '{entry_id}' must match [a-z0-9][a-z0-9-]* "
                "(lowercase, no spaces/underscores/accents)"
            )
        if not title:
            errors.append(f"{path}: missing 'title'")

        if entry_id and entry_id != path.stem:
            errors.append(
                f"{path.name}: filename stem '{path.stem}' doesn't match id '{entry_id}'"
            )

        if entry_id in seen_ids:
            errors.append(f"{path}: duplicate id '{entry_id}'")
        if entry_id:
            seen_ids.add(entry_id)

        date = front_matter.get("date") or front_matter.get("updated_at")
        if date and not DATE_RE.match(str(date)):
            errors.append(f"{path}: date must be YYYY-MM-DD")

        for key in ("variants", "categories", "keywords", "images", "examples",
                     "references", "see_also"):
            val = front_matter.get(key)
            if val is not None and not isinstance(val, list):
                errors.append(f"{path}: '{key}' must be a list")

        infobox = front_matter.get("infobox")
        if infobox is not None and not isinstance(infobox, (dict, str)):
            errors.append(f"{path}: 'infobox' must be a dict or string")

        if HTML_TAG_RE.search(body):
            errors.append(f"{path}: HTML tags found in body (not allowed)")

        # Validate categories against vocabulary
        if valid_categories:
            cats = front_matter.get("categories") or front_matter.get("keywords") or []
            if isinstance(cats, list):
                for cat in cats:
                    if cat not in valid_categories:
                        errors.append(
                            f"{path.name}: category '{cat}' not in categories.yaml"
                        )

        # Collect see_also for cross-entry validation
        see_also = front_matter.get("see_also")
        if entry_id and see_also and isinstance(see_also, list):
            see_also_map[entry_id] = see_also

    # Cross-entry validation: see_also referential integrity
    for source_id, targets in see_also_map.items():
        for target in targets:
            if target not in seen_ids:
                errors.append(
                    f"{source_id}: see_also target '{target}' does not exist"
                )

    if errors:
        print("Encyclopedia entry check failed:", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    # Subtract 1 for skipped README.md if present
    count = len([f for f in md_files if f.name != "README.md"])
    print(f"Checked {count} entries: OK")
    return 0
