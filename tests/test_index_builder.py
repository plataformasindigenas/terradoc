"""Tests for terradoc index_builder module."""

import json
import tempfile
from pathlib import Path

from terradoc.config import TerradocConfig
from terradoc.index_builder import generate_index


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


