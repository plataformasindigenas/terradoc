"""Tests for terradoc converters."""

import tempfile
from pathlib import Path

import pytest

from terradoc.config import TerradocConfig
from terradoc.convert import (
    _build_encyclopedia_graph,
    _format_citation,
    _normalize_records,
    _print_completeness_report,
    _resolve_references,
    _select_featured,
    _select_highlights,
    _validate_bib_keys,
    convert_encyclopedia,
    convert_module,
    SPECIAL_CONVERTERS,
    run_all_converters,
)


def test_special_converters_only_for_nongeneric_modules():
    """SPECIAL_CONVERTERS contains only modules that need custom conversion."""
    assert set(SPECIAL_CONVERTERS.keys()) == {"encyclopedia", "bibliography"}


def test_normalize_records_dicts():
    """_normalize_records handles plain dicts."""
    records = [{"a": 1, "b": 2}]
    result = _normalize_records(records)
    assert result == [{"a": 1, "b": 2}]


def test_format_citation_article():
    """_format_citation formats article type correctly."""
    entry = {
        "ENTRYTYPE": "article",
        "author": "Smith, J.",
        "year": "2020",
        "title": "A Study",
        "journal": "Nature",
        "volume": "10",
        "pages": "1-5",
        "doi": "10.1234/test",
    }
    result = _format_citation(entry)
    assert "Smith, J." in result
    assert "(2020)" in result
    assert "*A Study*" in result
    assert "Nature" in result
    assert "10" in result
    assert "1-5" in result
    assert "doi:10.1234/test" in result


def test_format_citation_book():
    """_format_citation formats book type correctly."""
    entry = {
        "ENTRYTYPE": "book",
        "author": "Doe, A.",
        "year": "2019",
        "title": "My Book",
        "publisher": "Press",
        "address": "City",
    }
    result = _format_citation(entry)
    assert "Doe, A." in result
    assert "(2019)" in result
    assert "*My Book*" in result
    assert "Press" in result
    assert "City" in result


def test_format_citation_phdthesis():
    """_format_citation formats phdthesis type correctly."""
    entry = {
        "ENTRYTYPE": "phdthesis",
        "author": "Lee, B.",
        "year": "2021",
        "title": "Thesis Title",
        "school": "University",
    }
    result = _format_citation(entry)
    assert "PhD thesis" in result
    assert "University" in result


def test_format_citation_misc():
    """_format_citation handles unknown types gracefully."""
    entry = {
        "ENTRYTYPE": "misc",
        "author": "Author",
        "year": "2022",
        "title": "Something",
    }
    result = _format_citation(entry)
    assert "Author" in result
    assert "(2022)" in result
    assert "*Something*" in result


def test_resolve_references_found():
    """_resolve_references resolves known BibTeX keys."""
    bib_data = {
        "key1": {
            "ENTRYTYPE": "book",
            "author": "Auth",
            "year": "2020",
            "title": "Title",
        }
    }
    result = _resolve_references(["key1"], bib_data)
    assert len(result) == 1
    assert result[0]["key"] == "key1"
    assert "Auth" in result[0]["formatted"]
    assert result[0]["author"] == "Auth"


def test_resolve_references_not_found():
    """_resolve_references marks missing keys with error."""
    result = _resolve_references(["missing-key"], {})
    assert len(result) == 1
    assert result[0]["key"] == "missing-key"
    assert result[0]["error"] is True
    assert "not found" in result[0]["formatted"]


# ── Bibliography key validation ──


def test_convert_encyclopedia_rejects_bad_bib_key():
    """convert_encyclopedia fails when an entry references a nonexistent bib key."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        enc_dir = data_dir / "encyclopedia"
        enc_dir.mkdir()

        (enc_dir / "test-entry.md").write_text("""---
id: test-entry
title: Test Entry
references:
  - nonexistent-key
---
Body text.
""", encoding="utf-8")

        # Create a minimal bib file with a different key
        (data_dir / "references.bib").write_text("""@article{real-key,
  author = {Smith},
  title = {Title},
  year = {2020},
}
""", encoding="utf-8")

        config = TerradocConfig(base_dir=tmp_path)

        with pytest.raises(ValueError, match="Unresolved bibliography references"):
            convert_encyclopedia(config)


def test_convert_encyclopedia_rejects_refs_without_bib_file():
    """convert_encyclopedia fails when entries have references but no bib file exists."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        enc_dir = data_dir / "encyclopedia"
        enc_dir.mkdir()

        (enc_dir / "test-entry.md").write_text("""---
id: test-entry
title: Test Entry
references:
  - some-key
---
Body text.
""", encoding="utf-8")

        # No bib file created
        config = TerradocConfig(base_dir=tmp_path)

        with pytest.raises(ValueError, match="Unresolved bibliography references"):
            convert_encyclopedia(config)


def test_convert_encyclopedia_accepts_valid_bib_keys():
    """convert_encyclopedia succeeds when all bib keys resolve."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        enc_dir = data_dir / "encyclopedia"
        enc_dir.mkdir()

        (enc_dir / "test-entry.md").write_text("""---
id: test-entry
title: Test Entry
references:
  - real-key
---
Body text.
""", encoding="utf-8")

        (data_dir / "references.bib").write_text("""@article{real-key,
  author = {Smith},
  title = {Title},
  year = {2020},
}
""", encoding="utf-8")

        config = TerradocConfig(base_dir=tmp_path)
        count = convert_encyclopedia(config)
        assert count == 1


# ── Dead schema fields removed ──


def test_encyclopedia_schema_no_dead_fields():
    """Encyclopedia schema no longer has dictionary_ids or fauna_ids."""
    import aptoro
    from terradoc.config import TerradocConfig

    cfg = TerradocConfig()
    schema = aptoro.load_schema(str(cfg.resolve_schema("encyclopedia")))
    field_names = [f.name for f in schema.fields]
    assert "dictionary_ids" not in field_names
    assert "fauna_ids" not in field_names


def test_dictionary_schema_no_dead_fields():
    """Dictionary schema no longer has fauna_ids or encyclopedia_ids."""
    import aptoro
    from terradoc.config import TerradocConfig

    cfg = TerradocConfig()
    schema = aptoro.load_schema(str(cfg.resolve_schema("dictionary")))
    field_names = [f.name for f in schema.fields]
    assert "fauna_ids" not in field_names
    assert "encyclopedia_ids" not in field_names


def test_fauna_schema_no_dead_fields():
    """Fauna schema no longer has dictionary_ids."""
    import aptoro
    from terradoc.config import TerradocConfig

    cfg = TerradocConfig()
    schema = aptoro.load_schema(str(cfg.resolve_schema("fauna")))
    field_names = [f.name for f in schema.fields]
    assert "dictionary_ids" not in field_names


def test_videos_schema_is_packaged_and_loadable():
    """Videos schema is bundled and can be loaded via resolve_schema."""
    import aptoro

    cfg = TerradocConfig()
    schema_path = cfg.resolve_schema("videos")
    assert schema_path.exists()
    schema = aptoro.load_schema(str(schema_path))
    field_names = [f.name for f in schema.fields]
    assert "youtube_id" in field_names
    assert "title" in field_names


def test_convert_module_videos_happy_path():
    """convert_module validates and exports videos.yaml."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (tmp_path / "docs").mkdir()

        (data_dir / "videos.yaml").write_text("""- youtube_id: abc123
  title: Video A
  category: ritual
  duration: "10:00"
  thumbnail: images/video-a.jpg
""", encoding="utf-8")

        config = TerradocConfig(base_dir=tmp_path)
        count = convert_module(config, "videos")
        assert count == 1

        exported = data_dir / "videos.json"
        assert exported.exists()
        text = exported.read_text(encoding="utf-8")
        assert '"youtube_id": "abc123"' in text
        assert '"title": "Video A"' in text


def test_run_all_converters_preflight_fails_on_missing_enabled_schema(monkeypatch):
    """Preflight fails early when an enabled module schema cannot be resolved."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "encyclopedia").mkdir()
        (tmp_path / "docs").mkdir()

        config = TerradocConfig(base_dir=tmp_path)
        for mod_name in list(config.modules):
            config.modules[mod_name].enabled = False
        config.modules["videos"].enabled = True

        original_resolve_schema = config.resolve_schema

        def fake_resolve_schema(module_slug: str) -> Path:
            if module_slug == "videos":
                return tmp_path / "data" / "videos_schema.yaml"
            return original_resolve_schema(module_slug)

        monkeypatch.setattr(config, "resolve_schema", fake_resolve_schema)

        with pytest.raises(FileNotFoundError, match="videos: missing schema file"):
            run_all_converters(config)


# ── Completeness report ──


# ── Validate bib keys ──


def test_validate_bib_keys_passes_on_valid():
    """_validate_bib_keys does not raise when all keys resolve."""
    records = [{"id": "a", "references": ["k1"]}, {"id": "b", "references": ["k2"]}]
    bib = {"k1": {}, "k2": {}}
    _validate_bib_keys(records, bib)


def test_validate_bib_keys_raises_on_missing():
    """_validate_bib_keys raises ValueError listing unresolved keys."""
    records = [{"id": "a", "references": ["missing"]}]
    with pytest.raises(ValueError, match="unresolved bib key 'missing'"):
        _validate_bib_keys(records, {})


def test_validate_bib_keys_ignores_entries_without_refs():
    """_validate_bib_keys skips entries with no references field."""
    records = [{"id": "a"}, {"id": "b", "references": []}]
    _validate_bib_keys(records, {})


# ── Featured article selection ──


def test_select_featured_by_config_id():
    """_select_featured picks the entry matching featured_id."""
    records = [
        {"id": "x", "title": "X", "images": ["img.jpg"], "content_html": "<p>ok</p>", "content_text": "ok"},
        {"id": "y", "title": "Y", "images": ["img2.jpg"], "content_html": "<p>ok</p>", "content_text": "ok"},
    ]
    result = _select_featured(records, "y")
    assert result["id"] == "y"
    assert result["title"] == "Y"


def test_select_featured_falls_back_to_first_with_images():
    """_select_featured picks first entry with images when no featured_id."""
    records = [
        {"id": "a", "title": "A", "content_html": "<p>hi</p>", "content_text": "hi"},
        {"id": "b", "title": "B", "images": ["img.jpg"], "content_html": "<p>hi</p>", "content_text": "hi"},
    ]
    result = _select_featured(records, "")
    assert result["id"] == "b"


def test_select_featured_returns_none_when_nothing_qualifies():
    """_select_featured returns None if no entry has images + content."""
    records = [{"id": "a", "title": "A", "content_html": "", "content_text": ""}]
    assert _select_featured(records, "") is None


# ── Highlights selection ──


def test_select_highlights_excludes_featured():
    """_select_highlights skips the featured article."""
    records = [
        {"id": "f", "images": ["a.jpg"]},
        {"id": "h1", "images": ["b.jpg"]},
        {"id": "h2", "images": ["c.jpg"]},
    ]
    featured = {"id": "f"}
    result = _select_highlights(records, featured)
    assert [h["id"] for h in result] == ["h1", "h2"]


def test_select_highlights_respects_limit():
    """_select_highlights returns at most *limit* entries."""
    records = [{"id": f"e{i}", "images": [f"{i}.jpg"]} for i in range(20)]
    result = _select_highlights(records, None, limit=3)
    assert len(result) == 3


def test_select_highlights_skips_entries_without_images():
    """_select_highlights only includes entries with images."""
    records = [
        {"id": "no-img"},
        {"id": "has-img", "images": ["x.jpg"]},
    ]
    result = _select_highlights(records, None)
    assert len(result) == 1
    assert result[0]["id"] == "has-img"


# ── Encyclopedia graph ──


def test_build_encyclopedia_graph_nodes_and_edges():
    """_build_encyclopedia_graph creates nodes, category edges, and see_also edges."""
    index_records = [{
        "id": "jaguar",
        "title": "Jaguar",
        "abstract": "Big cat",
        "categories": ["natureza/fauna"],
        "has_content": True,
        "see_also": ["onca"],
        "wikilink_targets": ["floresta"],
    }]
    graph = _build_encyclopedia_graph(index_records)
    node_ids = [n["id"] for n in graph["nodes"]]
    assert "jaguar" in node_ids
    assert "cat:natureza" in node_ids
    edge_types = {(e["source"], e["type"]) for e in graph["edges"]}
    assert ("jaguar", "category") in edge_types
    assert ("jaguar", "see_also") in edge_types
    assert ("jaguar", "wikilink") in edge_types


def test_build_encyclopedia_graph_empty():
    """_build_encyclopedia_graph handles empty input."""
    graph = _build_encyclopedia_graph([])
    assert graph == {"nodes": [], "edges": [], "categories": []}


# ── Completeness report ──


def test_completeness_report_all_complete(capsys):
    """Report shows zeros for complete entries."""
    records = [{
        "id": "test",
        "abstract": "Has abstract",
        "categories": ["cat"],
        "content_html": "<p>Has content</p>",
        "resolved_references": [],
    }]
    _print_completeness_report(records)
    out = capsys.readouterr().out
    assert "Without abstract:    0" in out
    assert "Without categories:  0" in out
    assert "Without body:        0" in out


def test_completeness_report_missing_fields(capsys):
    """Report counts entries missing abstract, categories, body."""
    records = [
        {"id": "a", "abstract": "", "categories": [], "content_html": "", "resolved_references": []},
        {"id": "b", "abstract": "OK", "categories": ["c"], "content_html": "<p>OK</p>", "resolved_references": []},
    ]
    _print_completeness_report(records)
    out = capsys.readouterr().out
    assert "Without abstract:    1" in out
    assert "Without categories:  1" in out
    assert "Without body:        1" in out


def test_completeness_report_broken_links(capsys):
    """Report shows broken links count."""
    records = [{
        "id": "test",
        "abstract": "OK",
        "categories": ["c"],
        "content_html": '<span class="broken-link">missing</span>',
        "resolved_references": [],
    }]
    _print_completeness_report(records)
    out = capsys.readouterr().out
    assert "With broken links:   1" in out


def test_completeness_report_empty_records(capsys):
    """Report prints nothing for empty record list."""
    _print_completeness_report([])
    out = capsys.readouterr().out
    assert out == ""
