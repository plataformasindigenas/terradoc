"""Tests for terradoc index_builder module."""

import json
import tempfile
from pathlib import Path

from terradoc.config import ModuleConfig, TerradocConfig
from terradoc.index_builder import copy_data_to_docs, generate_index


# ── generate_index ──


def test_generate_index_writes_json():
    """generate_index creates index.json with correct structure."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        config = TerradocConfig(project_name="Test Project", base_dir=tmp_path)
        counts = {"dictionary": 42, "encyclopedia": 10}

        generate_index(counts, config)

        output = data_dir / "index.json"
        assert output.exists()

        index_data = json.loads(output.read_text(encoding="utf-8"))
        assert index_data["meta"]["description"] == "Test Project - Index data"
        assert len(index_data["data"]) == 1
        assert index_data["data"][0]["dictionary_count"] == 42
        assert index_data["data"][0]["encyclopedia_count"] == 10


def test_generate_index_empty_counts():
    """generate_index handles empty counts dict."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        config = TerradocConfig(project_name="Empty", base_dir=tmp_path)
        generate_index({}, config)

        output = data_dir / "index.json"
        assert output.exists()

        index_data = json.loads(output.read_text(encoding="utf-8"))
        assert index_data["meta"]["description"] == "Empty - Index data"
        assert index_data["data"] == [{}]


def test_generate_index_single_module():
    """generate_index works with a single module count."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        config = TerradocConfig(base_dir=tmp_path)
        generate_index({"corpus": 5}, config)

        index_data = json.loads(
            (data_dir / "index.json").read_text(encoding="utf-8")
        )
        assert index_data["data"][0] == {"corpus_count": 5}


def test_generate_index_overwrites_existing():
    """generate_index overwrites a pre-existing index.json."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        output = data_dir / "index.json"
        output.write_text('{"old": true}', encoding="utf-8")

        config = TerradocConfig(base_dir=tmp_path)
        generate_index({"dictionary": 1}, config)

        index_data = json.loads(output.read_text(encoding="utf-8"))
        assert "old" not in index_data
        assert index_data["data"][0]["dictionary_count"] == 1


# ── copy_data_to_docs ──


def _make_project(tmp_path, modules, files):
    """Helper: create a project directory with given modules and data files."""
    data_dir = tmp_path / "data"
    docs_dir = tmp_path / "docs"
    data_dir.mkdir()
    docs_dir.mkdir()

    config = TerradocConfig(
        base_dir=tmp_path,
        modules={name: ModuleConfig(**opts) for name, opts in modules.items()},
    )

    for filename, content in files.items():
        (data_dir / filename).write_text(
            json.dumps(content), encoding="utf-8"
        )

    return config


def test_copy_data_dictionary():
    """copy_data_to_docs copies dictionary.json when module is enabled."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_project(
            tmp_path,
            modules={"dictionary": {"enabled": True}},
            files={"dictionary.json": {"entries": []}},
        )

        copy_data_to_docs(config)

        dst = tmp_path / "docs" / "dictionary-data.json"
        assert dst.exists()
        assert json.loads(dst.read_text(encoding="utf-8")) == {"entries": []}


def test_copy_data_corpus():
    """copy_data_to_docs copies corpus.json when module is enabled."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_project(
            tmp_path,
            modules={"corpus": {"enabled": True}},
            files={"corpus.json": {"texts": [1, 2]}},
        )

        copy_data_to_docs(config)

        dst = tmp_path / "docs" / "corpus-data.json"
        assert dst.exists()
        assert json.loads(dst.read_text(encoding="utf-8")) == {"texts": [1, 2]}


def test_copy_data_encyclopedia_index():
    """copy_data_to_docs copies encyclopedia_index.json when enabled."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_project(
            tmp_path,
            modules={"encyclopedia": {"enabled": True}},
            files={"encyclopedia_index.json": {"articles": []}},
        )

        copy_data_to_docs(config)

        dst = tmp_path / "docs" / "encyclopedia-data.json"
        assert dst.exists()


def test_copy_data_encyclopedia_graph():
    """copy_data_to_docs copies encyclopedia graph when graph is enabled."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_project(
            tmp_path,
            modules={"encyclopedia": {"enabled": True, "graph": True}},
            files={
                "encyclopedia_index.json": {"articles": []},
                "encyclopedia_graph.json": {"nodes": [], "edges": []},
            },
        )

        copy_data_to_docs(config)

        assert (tmp_path / "docs" / "encyclopedia-data.json").exists()
        assert (tmp_path / "docs" / "encyclopedia-graph.json").exists()


def test_copy_data_encyclopedia_graph_disabled():
    """Graph file is NOT copied when graph is disabled."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_project(
            tmp_path,
            modules={"encyclopedia": {"enabled": True, "graph": False}},
            files={
                "encyclopedia_index.json": {"articles": []},
                "encyclopedia_graph.json": {"nodes": []},
            },
        )

        copy_data_to_docs(config)

        assert (tmp_path / "docs" / "encyclopedia-data.json").exists()
        assert not (tmp_path / "docs" / "encyclopedia-graph.json").exists()


def test_copy_data_disabled_module_skipped():
    """Disabled modules are not copied even if source files exist."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_project(
            tmp_path,
            modules={"dictionary": {"enabled": False}},
            files={"dictionary.json": {"entries": []}},
        )

        copy_data_to_docs(config)

        assert not (tmp_path / "docs" / "dictionary-data.json").exists()


def test_copy_data_missing_source_file():
    """Enabled module with missing source file does not create dest."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_project(
            tmp_path,
            modules={"dictionary": {"enabled": True}},
            files={},  # no dictionary.json
        )

        copy_data_to_docs(config)

        assert not (tmp_path / "docs" / "dictionary-data.json").exists()


def test_copy_data_all_modules():
    """All three module types are copied when enabled and source exists."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_project(
            tmp_path,
            modules={
                "dictionary": {"enabled": True},
                "corpus": {"enabled": True},
                "encyclopedia": {"enabled": True, "graph": True},
            },
            files={
                "dictionary.json": {"d": 1},
                "corpus.json": {"c": 2},
                "encyclopedia_index.json": {"e": 3},
                "encyclopedia_graph.json": {"g": 4},
            },
        )

        copy_data_to_docs(config)

        docs = tmp_path / "docs"
        assert (docs / "dictionary-data.json").exists()
        assert (docs / "corpus-data.json").exists()
        assert (docs / "encyclopedia-data.json").exists()
        assert (docs / "encyclopedia-graph.json").exists()


def test_copy_data_no_modules_enabled():
    """When no relevant modules are enabled, docs stays empty."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_project(
            tmp_path,
            modules={
                "dictionary": {"enabled": False},
                "corpus": {"enabled": False},
                "encyclopedia": {"enabled": False},
            },
            files={
                "dictionary.json": {},
                "corpus.json": {},
                "encyclopedia_index.json": {},
            },
        )

        copy_data_to_docs(config)

        docs = tmp_path / "docs"
        assert list(docs.iterdir()) == []


def test_copy_data_preserves_content():
    """Copied file content matches the original exactly."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        original = {"entries": [{"id": "a", "gloss": "test"}]}
        config = _make_project(
            tmp_path,
            modules={"dictionary": {"enabled": True}},
            files={"dictionary.json": original},
        )

        copy_data_to_docs(config)

        dst = tmp_path / "docs" / "dictionary-data.json"
        assert json.loads(dst.read_text(encoding="utf-8")) == original
