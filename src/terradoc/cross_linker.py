"""Cross-link datasets (dictionary, fauna, ethnobotany, encyclopedia) by shared fields."""

import json

import yaml

from terradoc.config import TerradocConfig


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


def cross_link_datasets(config: TerradocConfig):
    """Cross-link dictionary, fauna, ethnobotany, and encyclopedia entries by shared fields."""
    print("=== Cross-linking Datasets ===")

    dict_file = config.data_dir / "dictionary.json"
    fauna_file = config.data_dir / "fauna.json"
    ethnobotany_file = config.data_dir / "ethnobotany.json"
    enc_file = config.data_dir / "encyclopedia.json"

    files_to_check = []
    if config.is_module_enabled("dictionary"):
        files_to_check.append(dict_file)
    if config.is_module_enabled("fauna"):
        files_to_check.append(fauna_file)
    if config.is_module_enabled("ethnobotany"):
        files_to_check.append(ethnobotany_file)
    if config.is_module_enabled("encyclopedia"):
        files_to_check.append(enc_file)

    if not all(f.exists() for f in files_to_check):
        print("  Missing JSON files, skipping cross-linking.")
        return

    dictionary = fauna = ethnobotany = encyclopedia = None

    if config.is_module_enabled("dictionary") and dict_file.exists():
        with open(dict_file, "r", encoding="utf-8") as f:
            dictionary = json.load(f)

    if config.is_module_enabled("fauna") and fauna_file.exists():
        with open(fauna_file, "r", encoding="utf-8") as f:
            fauna = json.load(f)

    if config.is_module_enabled("ethnobotany") and ethnobotany_file.exists():
        with open(ethnobotany_file, "r", encoding="utf-8") as f:
            ethnobotany = json.load(f)

    if config.is_module_enabled("encyclopedia") and enc_file.exists():
        with open(enc_file, "r", encoding="utf-8") as f:
            encyclopedia = json.load(f)

    link_count = 0
    enc_link_count = 0
    ethno_link_count = 0
    ethno_enc_link_count = 0

    # Dictionary ↔ Fauna cross-links
    if dictionary and fauna:
        fauna_by_sci: dict[str, list[dict]] = {}
        for entry in fauna["data"]:
            sci = (entry.get("scientific_name") or "").strip().lower()
            if sci:
                fauna_by_sci.setdefault(sci, []).append(entry)

        dict_by_sci: dict[str, list[dict]] = {}
        for entry in dictionary["data"]:
            sci = (entry.get("scientific_name") or "").strip().lower()
            if sci:
                dict_by_sci.setdefault(sci, []).append(entry)

        for entry in dictionary["data"]:
            sci = (entry.get("scientific_name") or "").strip().lower()
            if sci and sci in fauna_by_sci:
                linked = []
                for f_entry in fauna_by_sci[sci]:
                    linked.append({
                        "id": f_entry["id"],
                        "name_bororo": f_entry.get("name_bororo", ""),
                        "name_portuguese": f_entry.get("name_portuguese", ""),
                    })
                entry["_linked_fauna"] = linked
                link_count += 1

        for entry in fauna["data"]:
            sci = (entry.get("scientific_name") or "").strip().lower()
            if sci and sci in dict_by_sci:
                linked = []
                for d_entry in dict_by_sci[sci]:
                    linked.append({
                        "id": d_entry["id"],
                        "entry": d_entry.get("entry", ""),
                        "definition": d_entry.get("definition", ""),
                    })
                entry["_linked_dictionary"] = linked

    # Dictionary ↔ Ethnobotany cross-links (by scientific_name)
    if dictionary and ethnobotany:
        ethno_by_sci: dict[str, list[dict]] = {}
        for entry in ethnobotany["data"]:
            sci = (entry.get("scientific_name") or "").strip().lower()
            if sci:
                ethno_by_sci.setdefault(sci, []).append(entry)

        # Build dict_by_sci if not already built above
        if not fauna:
            dict_by_sci = {}
            for entry in dictionary["data"]:
                sci = (entry.get("scientific_name") or "").strip().lower()
                if sci:
                    dict_by_sci.setdefault(sci, []).append(entry)

        for entry in dictionary["data"]:
            sci = (entry.get("scientific_name") or "").strip().lower()
            if sci and sci in ethno_by_sci:
                linked = []
                for e_entry in ethno_by_sci[sci]:
                    linked.append({
                        "id": e_entry["id"],
                        "name_bororo": e_entry.get("name_bororo", ""),
                        "name_portuguese": e_entry.get("name_portuguese", ""),
                    })
                entry.setdefault("_linked_ethnobotany", []).extend(linked)
                ethno_link_count += 1

        for entry in ethnobotany["data"]:
            sci = (entry.get("scientific_name") or "").strip().lower()
            if sci and sci in dict_by_sci:
                linked = []
                for d_entry in dict_by_sci[sci]:
                    linked.append({
                        "id": d_entry["id"],
                        "entry": d_entry.get("entry", ""),
                        "definition": d_entry.get("definition", ""),
                    })
                entry["_linked_dictionary"] = linked

    # Ethnobotany ↔ Encyclopedia cross-links (entries tagged natureza/flora)
    if ethnobotany and encyclopedia:
        flora_entries: dict[str, dict] = {}
        for entry in encyclopedia["data"]:
            cats = entry.get("categories") or []
            if any("natureza/flora" in (c or "").lower() for c in cats):
                title = (entry.get("title") or "").strip().lower()
                if title:
                    flora_entries[title] = entry

        for entry in ethnobotany["data"]:
            for field_name in ("name_bororo", "name_portuguese", "scientific_name"):
                val = (entry.get(field_name) or "").strip().lower()
                if val and val in flora_entries:
                    enc_entry = flora_entries[val]
                    entry.setdefault("_linked_encyclopedia", []).append({
                        "id": enc_entry["id"],
                        "title": enc_entry.get("title", ""),
                    })
                    ethno_enc_link_count += 1
                    break

    # Dictionary → Encyclopedia cross-links
    if dictionary and encyclopedia:
        enc_by_title = {}
        for entry in encyclopedia["data"]:
            title = (entry.get("title") or "").strip().lower().replace(" ", "-")
            if title:
                enc_by_title[title] = entry

        for entry in dictionary["data"]:
            raw_entry = (entry.get("entry") or "").strip().lower().lstrip("-").replace(" ", "-")
            if raw_entry and raw_entry in enc_by_title:
                enc_entry = enc_by_title[raw_entry]
                entry.setdefault("_linked_encyclopedia", []).append({
                    "id": enc_entry["id"],
                    "title": enc_entry.get("title", ""),
                })
                enc_link_count += 1

    # Write updated files
    if dictionary:
        dict_file.write_text(
            json.dumps(dictionary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if fauna:
        fauna_file.write_text(
            json.dumps(fauna, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if ethnobotany:
        ethnobotany_file.write_text(
            json.dumps(ethnobotany, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"  Cross-linked {link_count} dictionary\u2194fauna entries by scientific name")
    print(f"  Cross-linked {ethno_link_count} dictionary\u2194ethnobotany entries by scientific name")
    print(f"  Cross-linked {ethno_enc_link_count} ethnobotany\u2194encyclopedia entries")
    print(f"  Cross-linked {enc_link_count} dictionary\u2192encyclopedia entries by title")
