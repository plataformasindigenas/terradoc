"""Data converters for terradoc projects."""

import csv
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import aptoro
import bibtexparser
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


def _parse_bibtex(text: str) -> list[dict]:
    """Parse BibTeX text and return entries as plain dicts (v1-compatible format).

    Uses bibtexparser v2 API: ``bibtexparser.parse()`` returns a Library whose
    ``.entries`` are Entry objects with ``.key``, ``.entry_type``, and
    ``.fields_dict`` (mapping field names to Field objects with ``.value``).
    """
    library = bibtexparser.parse_string(text)
    entries: list[dict] = []
    for entry in library.entries:
        d: dict[str, str] = {"ID": entry.key, "ENTRYTYPE": entry.entry_type}
        for name, field in entry.fields_dict.items():
            d[name] = field.value
        entries.append(d)
    return entries


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


_SOURCE_EXTENSIONS = (".yaml", ".yml", ".tsv")


def convert_module(config: TerradocConfig, slug: str) -> int:
    """Convert a data module from its source file to JSON."""
    label = config.module_label(slug)
    print(f"=== Converting {label} ===")

    source_file = None
    for ext in _SOURCE_EXTENSIONS:
        candidate = config.data_dir / f"{slug}{ext}"
        if candidate.exists():
            source_file = candidate
            break

    description = f"{config.culture_name} {label}"

    if source_file is None:
        output_file = _write_dataset(config, f"{slug}.json", slug, description, [])
        print(f"  Source file not found for {slug}")
        print(f"  Exported 0 entries to {output_file}")
        return 0

    schema = _load_schema(config, slug)
    data = aptoro.read(str(source_file))

    print(f"  Validating {len(data)} entries...")
    try:
        records = aptoro.validate(data, schema, collect_errors=True)
    except aptoro.ValidationError as e:
        print(e.summary())
        raise

    normalized_records = _normalize_records(records)

    output_file = _write_dataset(
        config, f"{slug}.json", slug, description, normalized_records,
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
        bib_entries = _parse_bibtex(f.read())

    schema = _load_schema(config, "bibliography")

    data = []
    for entry in bib_entries:
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
        bib_entries = _parse_bibtex(f.read())

    bib_data = {}
    for entry in bib_entries:
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


def _validate_bib_keys(records: list, bib_data: dict) -> None:
    """Raise if any record references a bibliography key not in bib_data."""
    errors: list[str] = []
    for record in records:
        entry = _record_to_dict(record)
        for key in entry.get("references") or []:
            if key not in bib_data:
                errors.append(
                    f"  {entry.get('id', '<unknown>')}: unresolved bib key '{key}'"
                )
    if errors:
        raise ValueError(
            "Unresolved bibliography references:\n" + "\n".join(errors)
        )


def _render_encyclopedia_entries(
    records: list, all_ids: set[str], bib_data: dict,
) -> tuple[list[dict], list[dict]]:
    """Render validated records into full entries and lightweight index entries."""
    md = build_markdown_renderer()
    normalized: list[dict] = []
    index: list[dict] = []

    for record in records:
        entry = _record_to_dict(record)

        if not entry.get("infobox"):
            entry["infobox"] = {}

        content_md = entry.get("content_md") or ""
        assert_no_html(content_md, entry.get("id", "<unknown>"))

        wikilink_targets: list[str] = []
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
        normalized.append(entry)

        index.append({
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

    return normalized, index


def _make_featured_summary(entry: dict) -> dict:
    """Build a featured-article summary dict from a full encyclopedia entry."""
    images = entry.get("images") or []
    text = (entry.get("content_text") or "")[:400]
    if text and " " in text:
        text = text.rsplit(" ", 1)[0]
    return {
        "id": entry["id"],
        "title": entry.get("title", ""),
        "abstract": entry.get("abstract", ""),
        "image": images[0] if images else None,
        "content_excerpt": (text + "...") if text else "",
    }


def _select_featured(records: list[dict], featured_id: str) -> dict | None:
    """Pick the featured article: explicit config id, then first entry with images."""
    if featured_id:
        for entry in records:
            if entry.get("id") == featured_id:
                return _make_featured_summary(entry)
    for entry in records:
        if entry.get("images") and entry.get("content_html"):
            return _make_featured_summary(entry)
    return None


def _select_highlights(
    records: list[dict], featured: dict | None, limit: int = 8,
) -> list[dict]:
    """Pick up to *limit* entries with images, excluding the featured article."""
    featured_id = featured.get("id") if featured else None
    highlights: list[dict] = []
    for entry in records:
        images = entry.get("images") or []
        if images and entry.get("id") != featured_id:
            highlights.append({
                "id": entry["id"],
                "title": entry.get("title", ""),
                "image": images[0],
            })
            if len(highlights) >= limit:
                break
    return highlights


def _build_encyclopedia_graph(index_records: list[dict]) -> dict:
    """Build a knowledge-graph structure from index records."""
    nodes: list[dict] = []
    edges: list[dict] = []
    category_set: set[str] = set()

    for rec in index_records:
        eid = rec["id"]
        nodes.append({
            "id": eid,
            "title": rec["title"],
            "abstract": rec.get("abstract", ""),
            "categories": rec["categories"],
            "has_content": rec["has_content"],
            "type": "entry",
        })

        for cat in rec["categories"]:
            top_cat = cat.split("/")[0]
            category_set.add(top_cat)
            edges.append({
                "source": eid,
                "target": f"cat:{top_cat}",
                "type": "category",
            })

        for target in rec.get("see_also") or []:
            edges.append({
                "source": eid, "target": target, "type": "see_also",
            })

        for target in rec.get("wikilink_targets") or []:
            edges.append({
                "source": eid, "target": target, "type": "wikilink",
            })

    for cat in sorted(category_set):
        nodes.append({"id": f"cat:{cat}", "title": cat, "type": "category"})

    return {
        "nodes": nodes,
        "edges": edges,
        "categories": sorted(category_set),
    }


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

    all_ids = {
        _record_to_dict(r).get("id", "") for r in records
    } - {""}

    bib_data = _load_bib_data(config.data_dir, config.bib_file)
    _validate_bib_keys(records, bib_data)

    normalized_records, index_records = _render_encyclopedia_entries(
        records, all_ids, bib_data,
    )

    output_file = _write_dataset(
        config, "encyclopedia.json", "encyclopedia",
        f"{config.culture_name} Encyclopedia Entries",
        normalized_records, version="2.0",
    )

    featured = _select_featured(normalized_records, config.featured_article_id)
    highlights = _select_highlights(normalized_records, featured)

    index_data: dict[str, Any] = {
        "meta": _dataset_meta(
            config, "encyclopedia",
            f"{config.culture_name} Encyclopedia Entries",
            len(index_records), "2.0",
        ),
        "data": index_records,
        "category_tree": build_category_tree(normalized_records),
        "featured": featured,
        "highlights": highlights,
    }

    index_file = config.data_dir / "encyclopedia_index.json"
    index_file.write_text(
        json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if config.is_graph_enabled("encyclopedia"):
        graph_data = _build_encyclopedia_graph(index_records)
        graph_file = config.data_dir / "encyclopedia_graph.json"
        graph_file.write_text(
            json.dumps(graph_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  Exported graph ({len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges) to {graph_file}")

    print(f"  Exported {len(normalized_records)} entries to {output_file}")
    print(f"  Exported index ({len(index_records)} entries) to {index_file}")

    _print_completeness_report(normalized_records)

    return len(normalized_records)


SPECIAL_CONVERTERS = {
    "encyclopedia": convert_encyclopedia,
    "bibliography": convert_bibliography,
}


REQUIRED_DATA_PATHS: dict[str, tuple[str, ...]] = {
    "encyclopedia": ("encyclopedia",),
}


def _run_enabled_module_preflight(config: TerradocConfig) -> None:
    """Fail early if enabled built-in modules are missing required resources."""
    problems: list[str] = []

    for name in config.modules:
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
    for name in config.modules:
        if not config.is_module_enabled(name):
            print(f"=== Skipping {name} (disabled) ===\n")
            continue
        converter = SPECIAL_CONVERTERS.get(name)
        if converter:
            counts[name] = converter(config)
        else:
            counts[name] = convert_module(config, name)
        print()
    return counts
