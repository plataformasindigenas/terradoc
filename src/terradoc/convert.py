"""Data converters for terradoc projects."""

import csv
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import aptoro
from bibtexparser import bparser  # type: ignore[import-untyped]
import yaml

from terradoc.config import TerradocConfig
from terradoc.markdown_utils import (
    assert_no_html,
    build_category_tree,
    build_markdown_renderer,
    extract_wikilink_targets,
    html_to_text,
    process_wikilinks,
)

csv.field_size_limit(sys.maxsize)


def _dataset_meta(config: TerradocConfig, module_slug: str, description: str, count: int, version: str) -> dict:
    """Build standard metadata for exported datasets."""
    return {
        "name": f"{config.meta_prefix}_{module_slug}",
        "description": description,
        "version": version,
        "record_count": count,
    }


def _write_dataset(config: TerradocConfig, output_name: str, module_slug: str, description: str,
                   records: list[dict], version: str = "1.0") -> Path:
    """Write a normalized dataset JSON file and return its path."""
    output_data = {
        "meta": _dataset_meta(config, module_slug, description, len(records), version),
        "data": records,
    }
    output_file = config.data_dir / output_name
    output_file.write_text(
        json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_file


def _record_to_dict(record: object) -> dict:
    """Convert a single aptoro record (dataclass or dict) to a plain dict."""
    if is_dataclass(record):
        return asdict(record)  # type: ignore[arg-type]
    return dict(record)  # type: ignore[call-overload]


def _normalize_records(records: list) -> list[dict]:
    """Convert aptoro records to plain dicts."""
    return [_record_to_dict(r) for r in records]


def _load_schema(config: TerradocConfig, module_slug: str):
    """Load schema for a module, failing with a clear path if missing."""
    schema_path = config.resolve_schema(module_slug)
    if not schema_path.exists():
        raise FileNotFoundError(
            f"Schema for module '{module_slug}' not found: {schema_path}. "
            f"Expected '{module_slug}_schema.yaml' in package schemas or data/."
        )
    return aptoro.load_schema(str(schema_path))


def convert_dictionary(config: TerradocConfig) -> int:
    """Convert dictionary TSV to JSON."""
    print("=== Converting Dictionary ===")

    dictionary_file = config.data_dir / "dictionary.tsv"
    if not dictionary_file.exists():
        output_file = _write_dataset(
            config,
            "dictionary.json",
            "dictionary",
            f"{config.culture_name} Dictionary Entries",
            [],
        )
        print(f"  Dictionary file not found: {dictionary_file}")
        print(f"  Exported 0 entries to {output_file}")
        return 0

    schema = _load_schema(config, "dictionary")
    data = aptoro.read(str(dictionary_file), format="csv", delimiter="\t")

    print(f"  Validating {len(data)} entries...")
    try:
        records = aptoro.validate(data, schema, collect_errors=True)
    except aptoro.ValidationError as e:
        print(e.summary())
        raise

    normalized_records = _normalize_records(records)

    output_file = _write_dataset(
        config,
        "dictionary.json",
        "dictionary",
        f"{config.culture_name} Dictionary Entries",
        normalized_records,
    )

    print(f"  Exported {len(normalized_records)} entries to {output_file}")
    return len(normalized_records)


def convert_fauna(config: TerradocConfig) -> int:
    """Convert fauna YAML to JSON."""
    print("=== Converting Fauna ===")

    fauna_file = config.data_dir / "fauna.yaml"
    if not fauna_file.exists():
        output_file = _write_dataset(
            config,
            "fauna.json",
            "fauna",
            f"{config.culture_name} Fauna Dictionary",
            [],
        )
        print(f"  Fauna file not found: {fauna_file}")
        print(f"  Exported 0 entries to {output_file}")
        return 0

    schema = _load_schema(config, "fauna")
    data = aptoro.read(str(fauna_file), format="yaml")

    print(f"  Validating {len(data)} entries...")
    try:
        records = aptoro.validate(data, schema, collect_errors=True)
    except aptoro.ValidationError as e:
        print(e.summary())
        raise

    normalized_records = _normalize_records(records)

    output_file = _write_dataset(
        config,
        "fauna.json",
        "fauna",
        f"{config.culture_name} Fauna Dictionary",
        normalized_records,
    )

    print(f"  Exported {len(normalized_records)} entries to {output_file}")
    return len(normalized_records)


def convert_ethnobotany(config: TerradocConfig) -> int:
    """Convert ethnobotany YAML to JSON."""
    print("=== Converting Ethnobotany ===")

    ethnobotany_file = config.data_dir / "ethnobotany.yaml"
    if not ethnobotany_file.exists():
        output_file = _write_dataset(
            config,
            "ethnobotany.json",
            "ethnobotany",
            f"{config.culture_name} Ethnobotany Entries",
            [],
        )
        print(f"  Ethnobotany file not found: {ethnobotany_file}")
        print(f"  Exported 0 entries to {output_file}")
        return 0

    schema = _load_schema(config, "ethnobotany")
    data = aptoro.read(str(ethnobotany_file), format="yaml")

    print(f"  Validating {len(data)} entries...")
    try:
        records = aptoro.validate(data, schema, collect_errors=True)
    except aptoro.ValidationError as e:
        print(e.summary())
        raise

    normalized_records = _normalize_records(records)

    output_file = _write_dataset(
        config,
        "ethnobotany.json",
        "ethnobotany",
        f"{config.culture_name} Ethnobotany Entries",
        normalized_records,
    )

    print(f"  Exported {len(normalized_records)} entries to {output_file}")
    return len(normalized_records)


def convert_bibliography(config: TerradocConfig) -> int:
    """Convert bibliography BibTeX to JSON."""
    print("=== Converting Bibliography ===")

    bib_file = config.data_dir / config.bib_file
    if not bib_file.exists():
        print(f"  BibTeX file not found: {bib_file}")
        return 0

    with open(bib_file, "r", encoding="utf-8") as f:
        bib_database = bparser.parse(f.read())

    schema = _load_schema(config, "bibliography")

    data = []
    for entry in bib_database.entries:
        record = {"id": entry.get("ID", "")}
        bibtex_type = entry.get("ENTRYTYPE", "misc")
        if bibtex_type.startswith("@"):
            bibtex_type = bibtex_type[1:]
        record["type"] = bibtex_type

        field_mapping = {
            "author": "author", "title": "title", "year": "year",
            "journal": "journal", "volume": "volume", "number": "number",
            "pages": "pages", "doi": "doi", "url": "url",
            "publisher": "publisher", "address": "address", "school": "school",
            "note": "note", "editor": "editor", "booktitle": "booktitle",
        }

        for bib_field, schema_field in field_mapping.items():
            if bib_field in entry:
                record[schema_field] = entry[bib_field]

        data.append(record)

    print(f"  Validating {len(data)} entries...")
    try:
        records = aptoro.validate(data, schema, collect_errors=True)
    except aptoro.ValidationError as e:
        print(e.summary())
        raise

    normalized_records = _normalize_records(records)

    output_file = _write_dataset(
        config,
        "bibliography.json",
        "bibliography",
        f"{config.culture_name} Bibliography References",
        normalized_records,
    )

    print(f"  Exported {len(normalized_records)} entries to {output_file}")
    return len(normalized_records)


def _load_encyclopedia_entries(data_dir: Path) -> list[dict]:
    """Load and normalize encyclopedia markdown entries."""
    entries_dir = data_dir / "encyclopedia"
    if not entries_dir.exists():
        raise FileNotFoundError(f"Missing encyclopedia directory: {entries_dir}")

    md_files = sorted(
        p for p in entries_dir.rglob("*.md") if p.name != "README.md"
    )
    if not md_files:
        return []

    raw_entries = []
    for path in md_files:
        raw_entries.extend(
            aptoro.read(str(path), format="frontmatter", body_key="content_md")
        )

    entries: list[dict] = []
    seen_ids: set[str] = set()

    field_renames = {
        "headword": "title",
        "summary": "abstract",
        "updated_at": "date",
        "keywords": "categories",
    }

    for entry in raw_entries:
        for old_name, new_name in field_renames.items():
            if old_name in entry and new_name not in entry:
                entry[new_name] = entry.pop(old_name)

        entry_id = entry.get("id")
        if not entry_id:
            raise ValueError("Missing required front matter field 'id'")
        if entry_id in seen_ids:
            raise ValueError(f"Duplicate encyclopedia id: {entry_id}")
        seen_ids.add(entry_id)

        entries.append(entry)

    return entries


def _load_bib_data(data_dir: Path, bib_filename: str) -> dict:
    """Load BibTeX data and return {bib_key: entry_dict}."""
    bib_file = data_dir / bib_filename
    if not bib_file.exists():
        return {}

    with open(bib_file, "r", encoding="utf-8") as f:
        bib_database = bparser.parse(f.read())

    bib_data = {}
    for entry in bib_database.entries:
        key = entry.get("ID", "")
        if key:
            bib_data[key] = entry
    return bib_data


def _format_citation(entry: dict) -> str:
    """Format a BibTeX entry as a readable citation string."""
    bib_type = entry.get("ENTRYTYPE", "misc")
    author = entry.get("author", "")
    year = entry.get("year", "")
    title = entry.get("title", "")

    if bib_type == "article":
        journal = entry.get("journal", "")
        volume = entry.get("volume", "")
        pages = entry.get("pages", "")
        doi = entry.get("doi", "")
        cite = f"{author} ({year}). *{title}*."
        if journal:
            cite += f" {journal}"
        if volume:
            cite += f", {volume}"
        if pages:
            cite += f": {pages}"
        cite += "."
        if doi:
            cite += f" doi:{doi}"
    elif bib_type == "book":
        publisher = entry.get("publisher", "")
        address = entry.get("address", "")
        cite = f"{author} ({year}). *{title}*."
        if publisher:
            cite += f" {publisher}"
        if address:
            cite += f", {address}"
        cite += "."
    elif bib_type in ("incollection", "inbook"):
        booktitle = entry.get("booktitle", "")
        editor = entry.get("editor", "")
        publisher = entry.get("publisher", "")
        cite = f"{author} ({year}). *{title}*."
        if booktitle:
            cite += f" In: *{booktitle}*"
        if editor:
            cite += f" (ed. {editor})"
        if publisher:
            cite += f". {publisher}"
        cite += "."
    elif bib_type == "phdthesis":
        school = entry.get("school", "")
        cite = f"{author} ({year}). *{title}*. PhD thesis"
        if school:
            cite += f", {school}"
        cite += "."
    else:
        cite = f"{author} ({year}). *{title}*."
        publisher = entry.get("publisher", "")
        if publisher:
            cite += f" {publisher}."

    return cite


def _resolve_references(refs: list, bib_data: dict) -> list[dict]:
    """Resolve BibTeX keys to formatted citation dicts."""
    resolved = []
    for key in refs:
        if key in bib_data:
            entry = bib_data[key]
            resolved.append({
                "key": key,
                "formatted": _format_citation(entry),
                "author": entry.get("author", ""),
                "year": entry.get("year", ""),
                "title": entry.get("title", ""),
            })
        else:
            resolved.append({
                "key": key,
                "formatted": f"[{key}] — reference not found",
                "error": True,
            })
    return resolved


def _print_completeness_report(records: list[dict]) -> None:
    """Print a data completeness summary to stdout."""
    total = len(records)
    if total == 0:
        return

    no_abstract = [e["id"] for e in records if not e.get("abstract")]
    no_categories = [e["id"] for e in records if not e.get("categories")]
    no_content = [e["id"] for e in records if not e.get("content_html")]
    broken_refs = [
        e["id"] for e in records
        if any(r.get("error") for r in e.get("resolved_references", []))
    ]
    broken_links = [
        e["id"] for e in records
        if 'class="broken-link"' in (e.get("content_html") or "")
    ]

    print(f"\n  Data completeness ({total} entries):")
    print(f"    Without abstract:    {len(no_abstract)}")
    print(f"    Without categories:  {len(no_categories)}")
    print(f"    Without body:        {len(no_content)}")
    if broken_links:
        print(f"    With broken links:   {len(broken_links)}")
    if broken_refs:
        print(f"    With broken refs:    {len(broken_refs)}")


def convert_encyclopedia(config: TerradocConfig) -> int:
    """Convert encyclopedia markdown to JSON."""
    print("=== Converting Encyclopedia ===")

    schema = _load_schema(config, "encyclopedia")
    data = _load_encyclopedia_entries(config.data_dir)

    print(f"  Validating {len(data)} entries...")
    try:
        records = aptoro.validate(data, schema, collect_errors=True)
    except aptoro.ValidationError as e:
        print(e.summary())
        raise

    all_ids = set()
    for record in records:
        entry = _record_to_dict(record)
        eid = entry.get("id", "")
        if eid:
            all_ids.add(eid)

    bib_data = _load_bib_data(config.data_dir, config.bib_file)

    # Validate bibliography keys upfront
    bib_errors: list[str] = []
    for record in records:
        entry = _record_to_dict(record)
        refs = entry.get("references") or []
        for key in refs:
            if key not in bib_data:
                bib_errors.append(
                    f"  {entry.get('id', '<unknown>')}: unresolved bib key '{key}'"
                )
    if bib_errors:
        msg = "Unresolved bibliography references:\n" + "\n".join(bib_errors)
        raise ValueError(msg)

    md = build_markdown_renderer()
    normalized_records = []
    index_records = []

    for record in records:
        entry = _record_to_dict(record)

        if not entry.get("infobox"):
            entry["infobox"] = {}

        content_md = entry.get("content_md") or ""
        assert_no_html(content_md, entry.get("id", "<unknown>"))

        # Extract wikilink targets before converting to HTML
        wikilink_targets = []
        if "[[" in content_md:
            wikilink_targets = extract_wikilink_targets(content_md, all_ids)
            content_md = process_wikilinks(content_md, all_ids)

        content_html = md.render(content_md) if content_md else ""
        entry["content_html"] = content_html
        entry["content_text"] = html_to_text(content_html)
        entry["content_md"] = content_md

        refs = entry.get("references") or []
        if refs and bib_data:
            entry["resolved_references"] = _resolve_references(refs, bib_data)
        else:
            entry["resolved_references"] = []

        entry["_wikilink_targets"] = wikilink_targets
        normalized_records.append(entry)

        index_records.append({
            "id": entry.get("id", ""),
            "title": entry.get("title", ""),
            "abstract": entry.get("abstract", ""),
            "categories": entry.get("categories", []),
            "variants": entry.get("variants", []),
            "entry_type": entry.get("entry_type", ""),
            "has_content": bool(content_html),
            "see_also": entry.get("see_also", []),
            "wikilink_targets": wikilink_targets,
        })

    output_file = _write_dataset(
        config,
        "encyclopedia.json",
        "encyclopedia",
        f"{config.culture_name} Encyclopedia Entries",
        normalized_records,
        version="2.0",
    )

    category_tree = build_category_tree(normalized_records)

    index_data: dict[str, Any] = {
        "meta": _dataset_meta(
            config,
            "encyclopedia",
            f"{config.culture_name} Encyclopedia Entries",
            len(index_records),
            "2.0",
        ),
        "data": index_records,
        "category_tree": category_tree,
    }

    # Select featured article
    featured = None
    featured_id = config.featured_article_id
    if featured_id:
        for entry in normalized_records:
            if entry.get("id") == featured_id:
                images = entry.get("images") or []
                text = (entry.get("content_text") or "")[:400]
                if text and " " in text:
                    text = text.rsplit(" ", 1)[0]
                featured = {
                    "id": entry["id"],
                    "title": entry.get("title", ""),
                    "abstract": entry.get("abstract", ""),
                    "image": images[0] if images else None,
                    "content_excerpt": (text + "...") if text else "",
                }
                break

    if not featured:
        for entry in normalized_records:
            if entry.get("images") and entry.get("content_html"):
                images = entry.get("images") or []
                text = (entry.get("content_text") or "")[:400]
                if text and " " in text:
                    text = text.rsplit(" ", 1)[0]
                featured = {
                    "id": entry["id"],
                    "title": entry.get("title", ""),
                    "abstract": entry.get("abstract", ""),
                    "image": images[0] if images else None,
                    "content_excerpt": (text + "...") if text else "",
                }
                break

    highlights = []
    for entry in normalized_records:
        images = entry.get("images") or []
        if images and (not featured or entry.get("id") != featured.get("id")):
            highlights.append({
                "id": entry["id"],
                "title": entry.get("title", ""),
                "image": images[0],
            })
            if len(highlights) >= 8:
                break

    index_data["featured"] = featured
    index_data["highlights"] = highlights

    index_file = config.data_dir / "encyclopedia_index.json"
    index_file.write_text(
        json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # --- Generate graph data (opt-in) ---
    if config.is_graph_enabled("encyclopedia"):
        graph_nodes = []
        graph_edges = []
        category_set = set()

        for rec in index_records:
            eid = rec["id"]
            graph_nodes.append({
                "id": eid,
                "title": rec["title"],
                "abstract": rec.get("abstract", ""),
                "categories": rec["categories"],
                "has_content": rec["has_content"],
                "type": "entry",
            })

            # Edges: entry → category (star topology)
            for cat in rec["categories"]:
                top_cat = cat.split("/")[0]
                category_set.add(top_cat)
                graph_edges.append({
                    "source": eid,
                    "target": f"cat:{top_cat}",
                    "type": "category",
                })

            # Edges: see_also
            for target in rec.get("see_also") or []:
                graph_edges.append({
                    "source": eid,
                    "target": target,
                    "type": "see_also",
                })

            # Edges: wikilinks
            for target in rec.get("wikilink_targets") or []:
                graph_edges.append({
                    "source": eid,
                    "target": target,
                    "type": "wikilink",
                })

        # Add category nodes
        for cat in sorted(category_set):
            graph_nodes.append({
                "id": f"cat:{cat}",
                "title": cat,
                "type": "category",
            })

        graph_data = {
            "nodes": graph_nodes,
            "edges": graph_edges,
            "categories": sorted(category_set),
        }

        graph_file = config.data_dir / "encyclopedia_graph.json"
        graph_file.write_text(
            json.dumps(graph_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  Exported graph ({len(graph_nodes)} nodes, {len(graph_edges)} edges) to {graph_file}")

    print(f"  Exported {len(normalized_records)} entries to {output_file}")
    print(f"  Exported index ({len(index_records)} entries) to {index_file}")

    _print_completeness_report(normalized_records)

    return len(normalized_records)


def convert_recordings(config: TerradocConfig) -> int:
    """Convert recordings YAML to JSON."""
    print("=== Converting Recordings ===")

    recordings_file = config.data_dir / "recordings.yaml"
    if not recordings_file.exists():
        print(f"  Recordings file not found: {recordings_file}")
        return 0

    schema = _load_schema(config, "recordings")

    with open(recordings_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []

    print(f"  Validating {len(data)} entries...")
    try:
        records = aptoro.validate(data, schema, collect_errors=True)
    except aptoro.ValidationError as e:
        print(e.summary())
        raise

    normalized_records = _normalize_records(records)

    output_file = _write_dataset(
        config,
        "recordings.json",
        "recordings",
        f"{config.culture_name} Language Audio Recordings",
        normalized_records,
    )

    print(f"  Exported {len(normalized_records)} entries to {output_file}")
    return len(normalized_records)


def convert_corpus(config: TerradocConfig) -> int:
    """Convert corpus YAML to JSON."""
    print("=== Converting Corpus ===")

    corpus_file = config.data_dir / "corpus.yaml"
    if not corpus_file.exists():
        print(f"  Corpus file not found: {corpus_file}")
        return 0

    schema = _load_schema(config, "corpus")

    with open(corpus_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []

    print(f"  Validating {len(data)} entries...")
    try:
        records = aptoro.validate(data, schema, collect_errors=True)
    except aptoro.ValidationError as e:
        print(e.summary())
        raise

    normalized_records = _normalize_records(records)

    output_file = _write_dataset(
        config,
        "corpus.json",
        "corpus",
        f"{config.culture_name} Corpus Text Entries",
        normalized_records,
    )

    print(f"  Exported {len(normalized_records)} entries to {output_file}")
    return len(normalized_records)


def convert_videos(config: TerradocConfig) -> int:
    """Convert videos YAML to JSON."""
    print("=== Converting Videos ===")

    videos_file = config.data_dir / "videos.yaml"
    if not videos_file.exists():
        print(f"  Videos file not found: {videos_file}")
        return 0

    schema = _load_schema(config, "videos")

    with open(videos_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []

    print(f"  Validating {len(data)} entries...")
    try:
        records = aptoro.validate(data, schema, collect_errors=True)
    except aptoro.ValidationError as e:
        print(e.summary())
        raise

    normalized_records = _normalize_records(records)

    output_file = _write_dataset(
        config,
        "videos.json",
        "videos",
        f"{config.culture_name} Cultural Videos",
        normalized_records,
    )

    print(f"  Exported {len(normalized_records)} entries to {output_file}")
    return len(normalized_records)


# Registry of converters
CONVERTERS = {
    "dictionary": convert_dictionary,
    "fauna": convert_fauna,
    "ethnobotany": convert_ethnobotany,
    "encyclopedia": convert_encyclopedia,
    "bibliography": convert_bibliography,
    "recordings": convert_recordings,
    "corpus": convert_corpus,
    "videos": convert_videos,
}


REQUIRED_DATA_PATHS: dict[str, tuple[str, ...]] = {
    "encyclopedia": ("encyclopedia",),
}


def _run_enabled_module_preflight(config: TerradocConfig) -> None:
    """Fail early if enabled built-in modules are missing required resources."""
    problems: list[str] = []

    for name in CONVERTERS:
        if not config.is_module_enabled(name):
            continue

        schema_path = config.resolve_schema(name)
        if not schema_path.exists():
            problems.append(
                f"  - {name}: missing schema file at {schema_path}"
            )

        for rel_path in REQUIRED_DATA_PATHS.get(name, ()):
            required_path = config.data_dir / rel_path
            if not required_path.exists():
                problems.append(
                    f"  - {name}: missing required data path {required_path}"
                )

    if problems:
        raise FileNotFoundError(
            "Preflight validation failed for enabled modules:\n"
            + "\n".join(problems)
        )


def run_all_converters(config: TerradocConfig) -> dict[str, int]:
    """Run all enabled converters and return counts."""
    _run_enabled_module_preflight(config)

    counts = {}
    for name, converter in CONVERTERS.items():
        if config.is_module_enabled(name):
            counts[name] = converter(config)
            print()
        else:
            print(f"=== Skipping {name} (disabled) ===\n")
    return counts
