"""Cross-link datasets (dictionary, fauna, ethnobotany, encyclopedia) by shared fields."""

import json
import re
import unicodedata
from collections import defaultdict

import yaml

from terradoc.config import TerradocConfig


def _slugify(text: str) -> str:
    """Lowercase, strip diacritics, collapse non-alnum runs to underscores."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def attach_audio_to_dictionary(config: TerradocConfig):
    """Attach audio files from data/audio/ to dictionary entries via slug match.

    Convention (Option 1D): for each dictionary entry, look up
        data/audio/<slug>.webm   (primary)
        data/audio/<slug>__*.webm (variants — usually per-speaker)
    where slug = _slugify(entry.entry). Attach each match as
    {file_path, speaker, format} on entry.audio so the existing dictionary
    template renders <audio> players.
    """
    print("=== Attaching Audio to Dictionary ===")

    audio_dir = config.data_dir / "audio"
    dictionary_file = config.data_dir / "dictionary.json"

    if not audio_dir.exists():
        print("  No data/audio/ directory found, skipping.")
        return
    if not dictionary_file.exists():
        print("  No dictionary.json found, skipping.")
        return

    # Index audio files by slug. For each slug, separate primary from variants.
    by_slug: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(audio_dir.glob("*.webm")):
        name = path.name
        stem = path.stem
        if "__" in stem:
            slug, _, variant = stem.partition("__")
            speaker = re.sub(r"\d+$", "", variant) or "unknown"
            sort_key = (1, variant)
        else:
            slug = stem
            speaker = "unknown"
            sort_key = (0, "")
        by_slug[slug].append({
            "file_path": name,
            "speaker": speaker,
            "format": "webm",
            "_sort": sort_key,
        })

    # Sort within each slug: primary first, then variants alphabetically by speaker
    for slug in by_slug:
        by_slug[slug].sort(key=lambda d: d["_sort"])
        for d in by_slug[slug]:
            d.pop("_sort", None)

    with open(dictionary_file, "r", encoding="utf-8") as f:
        dictionary = json.load(f)

    attached = 0
    files_attached = 0
    for entry in dictionary["data"]:
        slug = _slugify(entry.get("entry", ""))
        if slug and slug in by_slug:
            entry["audio"] = by_slug[slug]
            attached += 1
            files_attached += len(by_slug[slug])

    # Coverage stats — written into meta so the template can render a badge
    total = len(dictionary["data"])
    pct = (100.0 * attached / total) if total else 0.0
    dictionary.setdefault("meta", {})["audio_coverage"] = {
        "entries_with_audio": attached,
        "total_entries": total,
        "percent": round(pct, 1),
        "files": files_attached,
    }

    dictionary_file.write_text(
        json.dumps(dictionary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"  Attached audio to {attached}/{total} entries ({pct:.1f}%)")
    print(f"  Total audio files linked: {files_attached}")


def attach_recordings_to_dictionary(config: TerradocConfig):
    """Attach audio recordings to dictionary entries."""
    print("=== Attaching Recordings to Dictionary ===")

    recordings_file = config.data_dir / "recordings.yaml"
    dictionary_file = config.data_dir / "dictionary.json"

    if not recordings_file.exists():
        print("  No recordings.yaml found, skipping.")
        return
    if not dictionary_file.exists():
        print("  No dictionary.json found, skipping.")
        return

    with open(recordings_file, "r", encoding="utf-8") as f:
        recordings = yaml.safe_load(f) or []

    audio_map: dict[int, list[dict]] = {}
    for rec in recordings:
        dict_id = rec.get("dictionary_id")
        if dict_id is None:
            continue
        audio_map.setdefault(dict_id, []).append({
            "file_path": rec["file_path"],
            "speaker": rec["speaker"],
            "format": rec["format"],
        })

    with open(dictionary_file, "r", encoding="utf-8") as f:
        dictionary = json.load(f)

    attached_count = 0
    for entry in dictionary["data"]:
        entry_id = entry.get("id")
        if entry_id in audio_map:
            entry["audio"] = audio_map[entry_id]
            attached_count += 1

    dictionary_file.write_text(
        json.dumps(dictionary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"  Attached audio to {attached_count} dictionary entries")
    print(f"  Total audio files linked: {sum(len(v) for v in audio_map.values())}")


# ── Pure cross-linking strategies ──


def _index_by_scientific_name(entries: list[dict]) -> dict[str, list[dict]]:
    """Build a lookup from lowercased scientific_name to matching entries."""
    index: dict[str, list[dict]] = {}
    for entry in entries:
        sci = (entry.get("scientific_name") or "").strip().lower()
        if sci:
            index.setdefault(sci, []).append(entry)
    return index


def _link_dict_fauna(dict_entries: list[dict], fauna_entries: list[dict]) -> int:
    """Bidirectional dict↔fauna cross-links by scientific_name. Returns dict→fauna count."""
    fauna_by_sci = _index_by_scientific_name(fauna_entries)
    dict_by_sci = _index_by_scientific_name(dict_entries)
    count = 0

    for entry in dict_entries:
        sci = (entry.get("scientific_name") or "").strip().lower()
        if sci and sci in fauna_by_sci:
            entry["_linked_fauna"] = [
                {
                    "id": f["id"],
                    "name_indigenous": f.get("name_indigenous", ""),
                    "name_portuguese": f.get("name_portuguese", ""),
                }
                for f in fauna_by_sci[sci]
            ]
            count += 1

    for entry in fauna_entries:
        sci = (entry.get("scientific_name") or "").strip().lower()
        if sci and sci in dict_by_sci:
            entry["_linked_dictionary"] = [
                {
                    "id": d["id"],
                    "entry": d.get("entry", ""),
                    "definition": d.get("definition", ""),
                }
                for d in dict_by_sci[sci]
            ]

    return count


def _link_dict_ethnobotany(dict_entries: list[dict], ethno_entries: list[dict]) -> int:
    """Bidirectional dict↔ethnobotany cross-links by scientific_name. Returns dict→ethno count."""
    ethno_by_sci = _index_by_scientific_name(ethno_entries)
    dict_by_sci = _index_by_scientific_name(dict_entries)
    count = 0

    for entry in dict_entries:
        sci = (entry.get("scientific_name") or "").strip().lower()
        if sci and sci in ethno_by_sci:
            entry.setdefault("_linked_ethnobotany", []).extend(
                {
                    "id": e["id"],
                    "name_indigenous": e.get("name_indigenous", ""),
                    "name_portuguese": e.get("name_portuguese", ""),
                }
                for e in ethno_by_sci[sci]
            )
            count += 1

    for entry in ethno_entries:
        sci = (entry.get("scientific_name") or "").strip().lower()
        if sci and sci in dict_by_sci:
            entry["_linked_dictionary"] = [
                {
                    "id": d["id"],
                    "entry": d.get("entry", ""),
                    "definition": d.get("definition", ""),
                }
                for d in dict_by_sci[sci]
            ]

    return count


def _link_ethno_encyclopedia(
    ethno_entries: list[dict], enc_entries: list[dict], target_categories: list[str],
) -> int:
    """One-directional ethnobotany→encyclopedia links by name matching in target categories."""
    target_cats = [c.lower() for c in target_categories]
    flora_by_title: dict[str, dict] = {}
    for entry in enc_entries:
        cats = entry.get("categories") or []
        if any(
            any(tc in (c or "").lower() for tc in target_cats)
            for c in cats
        ):
            title = (entry.get("title") or "").strip().lower()
            if title:
                flora_by_title[title] = entry

    count = 0
    for entry in ethno_entries:
        for field_name in ("name_indigenous", "name_portuguese", "scientific_name"):
            val = (entry.get(field_name) or "").strip().lower()
            if val and val in flora_by_title:
                enc_entry = flora_by_title[val]
                entry.setdefault("_linked_encyclopedia", []).append({
                    "id": enc_entry["id"],
                    "title": enc_entry.get("title", ""),
                })
                count += 1
                break

    return count


def _link_dict_encyclopedia(dict_entries: list[dict], enc_entries: list[dict]) -> int:
    """One-directional dictionary→encyclopedia links by entry/title match."""
    enc_by_title: dict[str, dict] = {}
    for entry in enc_entries:
        title = (entry.get("title") or "").strip().lower().replace(" ", "-")
        if title:
            enc_by_title[title] = entry

    count = 0
    for entry in dict_entries:
        raw = (entry.get("entry") or "").strip().lower().lstrip("-").replace(" ", "-")
        if raw and raw in enc_by_title:
            enc_entry = enc_by_title[raw]
            entry.setdefault("_linked_encyclopedia", []).append({
                "id": enc_entry["id"],
                "title": enc_entry.get("title", ""),
            })
            count += 1

    return count


# ── I/O helpers ──


def _load_module_json(config: TerradocConfig, module: str) -> dict | None:
    """Load a module's JSON dataset if the module is enabled and the file exists."""
    if not config.is_module_enabled(module):
        return None
    path = config.data_dir / f"{module}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_module_json(config: TerradocConfig, module: str, data: dict) -> None:
    """Write a module's JSON dataset back to disk."""
    path = config.data_dir / f"{module}.json"
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Orchestrator ──


def cross_link_datasets(config: TerradocConfig):
    """Cross-link dictionary, fauna, ethnobotany, and encyclopedia entries by shared fields."""
    print("=== Cross-linking Datasets ===")

    dictionary = _load_module_json(config, "dictionary")
    fauna = _load_module_json(config, "fauna")
    ethnobotany = _load_module_json(config, "ethnobotany")
    encyclopedia = _load_module_json(config, "encyclopedia")

    modules = {"dictionary": dictionary, "fauna": fauna,
               "ethnobotany": ethnobotany, "encyclopedia": encyclopedia}
    if not any(v is not None for v in modules.values()):
        print("  No enabled modules with JSON files, skipping cross-linking.")
        return

    link_count = enc_link_count = ethno_link_count = ethno_enc_link_count = 0

    if dictionary and fauna:
        link_count = _link_dict_fauna(dictionary["data"], fauna["data"])
    if dictionary and ethnobotany:
        ethno_link_count = _link_dict_ethnobotany(dictionary["data"], ethnobotany["data"])
    if ethnobotany and encyclopedia:
        ethno_enc_link_count = _link_ethno_encyclopedia(
            ethnobotany["data"], encyclopedia["data"],
            config.ethnobotany_encyclopedia_categories,
        )
    if dictionary and encyclopedia:
        enc_link_count = _link_dict_encyclopedia(dictionary["data"], encyclopedia["data"])

    for module in ("dictionary", "fauna", "ethnobotany"):
        if modules[module] is not None:
            _write_module_json(config, module, modules[module])

    print(f"  Cross-linked {link_count} dictionary↔fauna entries by scientific name")
    print(f"  Cross-linked {ethno_link_count} dictionary↔ethnobotany entries by scientific name")
    print(f"  Cross-linked {ethno_enc_link_count} ethnobotany↔encyclopedia entries")
    print(f"  Cross-linked {enc_link_count} dictionary→encyclopedia entries by title")
