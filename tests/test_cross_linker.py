"""Tests for terradoc cross_linker module."""

import json
import tempfile
from pathlib import Path

import yaml

from terradoc.config import TerradocConfig, ModuleConfig
from terradoc.cross_linker import attach_recordings_to_dictionary, cross_link_datasets


def _make_config(tmp_path: Path, modules=None, ethno_enc_categories=None) -> TerradocConfig:
    """Create a TerradocConfig pointing at a temporary directory."""
    config = TerradocConfig(base_dir=tmp_path)
    if modules:
        for name, enabled in modules.items():
            config.modules[name] = ModuleConfig(enabled=enabled)
    if ethno_enc_categories is not None:
        config.ethnobotany_encyclopedia_categories = ethno_enc_categories
    return config


def _write_json(path: Path, data: dict):
    """Write a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict:
    """Read a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def _write_yaml(path: Path, data):
    """Write a YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")


# ── attach_recordings_to_dictionary ──


def test_attach_recordings_basic():
    """Recordings are attached to matching dictionary entries by dictionary_id."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [
            {"id": 1, "entry": "word-one", "definition": "def one"},
            {"id": 2, "entry": "word-two", "definition": "def two"},
            {"id": 3, "entry": "word-three", "definition": "def three"},
        ]}
        _write_json(data_dir / "dictionary.json", dictionary)

        recordings = [
            {"dictionary_id": 1, "file_path": "audio/w1.mp3", "speaker": "Ana", "format": "mp3"},
            {"dictionary_id": 1, "file_path": "audio/w1b.mp3", "speaker": "Beto", "format": "mp3"},
            {"dictionary_id": 3, "file_path": "audio/w3.wav", "speaker": "Carlos", "format": "wav"},
        ]
        _write_yaml(data_dir / "recordings.yaml", recordings)

        attach_recordings_to_dictionary(config)

        result = _read_json(data_dir / "dictionary.json")
        entry1 = result["data"][0]
        entry2 = result["data"][1]
        entry3 = result["data"][2]

        assert len(entry1["audio"]) == 2
        assert entry1["audio"][0]["speaker"] == "Ana"
        assert entry1["audio"][1]["speaker"] == "Beto"

        assert "audio" not in entry2

        assert len(entry3["audio"]) == 1
        assert entry3["audio"][0]["format"] == "wav"


def test_attach_recordings_no_recordings_file():
    """attach_recordings skips gracefully when recordings.yaml is missing."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [{"id": 1, "entry": "word"}]}
        _write_json(data_dir / "dictionary.json", dictionary)

        # No recordings.yaml -- should not raise
        attach_recordings_to_dictionary(config)

        result = _read_json(data_dir / "dictionary.json")
        assert "audio" not in result["data"][0]


def test_attach_recordings_no_dictionary_file():
    """attach_recordings skips gracefully when dictionary.json is missing."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        _write_yaml(data_dir / "recordings.yaml", [
            {"dictionary_id": 1, "file_path": "a.mp3", "speaker": "X", "format": "mp3"},
        ])

        # No dictionary.json -- should not raise
        attach_recordings_to_dictionary(config)


def test_attach_recordings_no_matching_ids():
    """Recordings with no matching dictionary_id leave entries unchanged."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [{"id": 10, "entry": "word"}]}
        _write_json(data_dir / "dictionary.json", dictionary)

        recordings = [
            {"dictionary_id": 99, "file_path": "a.mp3", "speaker": "X", "format": "mp3"},
        ]
        _write_yaml(data_dir / "recordings.yaml", recordings)

        attach_recordings_to_dictionary(config)

        result = _read_json(data_dir / "dictionary.json")
        assert "audio" not in result["data"][0]


def test_attach_recordings_skips_no_dictionary_id():
    """Recordings without a dictionary_id field are silently skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [{"id": 1, "entry": "word"}]}
        _write_json(data_dir / "dictionary.json", dictionary)

        recordings = [
            {"file_path": "orphan.mp3", "speaker": "X", "format": "mp3"},
        ]
        _write_yaml(data_dir / "recordings.yaml", recordings)

        attach_recordings_to_dictionary(config)

        result = _read_json(data_dir / "dictionary.json")
        assert "audio" not in result["data"][0]


def test_attach_recordings_empty_recordings_file():
    """An empty recordings.yaml (null) does not cause errors."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [{"id": 1, "entry": "word"}]}
        _write_json(data_dir / "dictionary.json", dictionary)
        _write_yaml(data_dir / "recordings.yaml", None)

        attach_recordings_to_dictionary(config)

        result = _read_json(data_dir / "dictionary.json")
        assert "audio" not in result["data"][0]


# ── cross_link_datasets: dictionary ↔ fauna ──


def test_cross_link_dictionary_fauna():
    """Dictionary and fauna entries are cross-linked by scientific_name."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path, modules={
            "dictionary": True, "fauna": True,
            "ethnobotany": False, "encyclopedia": False,
        })
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [
            {"id": 1, "entry": "araara", "scientific_name": "Ara ararauna", "definition": "blue macaw"},
            {"id": 2, "entry": "other", "scientific_name": "Unknown sp.", "definition": "unknown"},
        ]}
        fauna = {"data": [
            {"id": 101, "scientific_name": "Ara ararauna", "name_indigenous": "araara", "name_portuguese": "arara-azul"},
        ]}

        _write_json(data_dir / "dictionary.json", dictionary)
        _write_json(data_dir / "fauna.json", fauna)

        cross_link_datasets(config)

        dict_result = _read_json(data_dir / "dictionary.json")
        fauna_result = _read_json(data_dir / "fauna.json")

        # Dictionary entry 1 should link to fauna entry 101
        entry1 = dict_result["data"][0]
        assert "_linked_fauna" in entry1
        assert len(entry1["_linked_fauna"]) == 1
        assert entry1["_linked_fauna"][0]["id"] == 101
        assert entry1["_linked_fauna"][0]["name_indigenous"] == "araara"

        # Dictionary entry 2 should not have fauna links
        entry2 = dict_result["data"][1]
        assert "_linked_fauna" not in entry2

        # Fauna entry should link back to dictionary
        f_entry = fauna_result["data"][0]
        assert "_linked_dictionary" in f_entry
        assert len(f_entry["_linked_dictionary"]) == 1
        assert f_entry["_linked_dictionary"][0]["id"] == 1


def test_cross_link_dictionary_fauna_case_insensitive():
    """Cross-linking by scientific_name is case-insensitive."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path, modules={
            "dictionary": True, "fauna": True,
            "ethnobotany": False, "encyclopedia": False,
        })
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [
            {"id": 1, "entry": "bird", "scientific_name": "  ARA ARARAUNA  ", "definition": "macaw"},
        ]}
        fauna = {"data": [
            {"id": 101, "scientific_name": "ara ararauna", "name_indigenous": "araara", "name_portuguese": "arara"},
        ]}

        _write_json(data_dir / "dictionary.json", dictionary)
        _write_json(data_dir / "fauna.json", fauna)

        cross_link_datasets(config)

        dict_result = _read_json(data_dir / "dictionary.json")
        assert "_linked_fauna" in dict_result["data"][0]


def test_cross_link_dictionary_fauna_empty_scientific_name():
    """Entries with empty or missing scientific_name are skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path, modules={
            "dictionary": True, "fauna": True,
            "ethnobotany": False, "encyclopedia": False,
        })
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [
            {"id": 1, "entry": "word", "scientific_name": ""},
            {"id": 2, "entry": "word2"},
        ]}
        fauna = {"data": [
            {"id": 101, "scientific_name": "", "name_indigenous": "x", "name_portuguese": "y"},
        ]}

        _write_json(data_dir / "dictionary.json", dictionary)
        _write_json(data_dir / "fauna.json", fauna)

        cross_link_datasets(config)

        dict_result = _read_json(data_dir / "dictionary.json")
        for entry in dict_result["data"]:
            assert "_linked_fauna" not in entry


# ── cross_link_datasets: dictionary ↔ ethnobotany ──


def test_cross_link_dictionary_ethnobotany():
    """Dictionary and ethnobotany entries are cross-linked by scientific_name."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path, modules={
            "dictionary": True, "ethnobotany": True,
            "fauna": False, "encyclopedia": False,
        })
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [
            {"id": 1, "entry": "tree", "scientific_name": "Bertholletia excelsa", "definition": "brazil nut"},
        ]}
        ethnobotany = {"data": [
            {"id": 201, "scientific_name": "Bertholletia excelsa", "name_indigenous": "tahi", "name_portuguese": "castanha"},
        ]}

        _write_json(data_dir / "dictionary.json", dictionary)
        _write_json(data_dir / "ethnobotany.json", ethnobotany)

        cross_link_datasets(config)

        dict_result = _read_json(data_dir / "dictionary.json")
        ethno_result = _read_json(data_dir / "ethnobotany.json")

        entry = dict_result["data"][0]
        assert "_linked_ethnobotany" in entry
        assert len(entry["_linked_ethnobotany"]) == 1
        assert entry["_linked_ethnobotany"][0]["id"] == 201

        e_entry = ethno_result["data"][0]
        assert "_linked_dictionary" in e_entry
        assert e_entry["_linked_dictionary"][0]["id"] == 1


def test_cross_link_dictionary_ethnobotany_case_insensitive():
    """Dictionary-ethnobotany cross-linking is case-insensitive."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path, modules={
            "dictionary": True, "ethnobotany": True,
            "fauna": False, "encyclopedia": False,
        })
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [
            {"id": 1, "entry": "tree", "scientific_name": "BERTHOLLETIA EXCELSA", "definition": "nut"},
        ]}
        ethnobotany = {"data": [
            {"id": 201, "scientific_name": "bertholletia excelsa", "name_indigenous": "t", "name_portuguese": "c"},
        ]}

        _write_json(data_dir / "dictionary.json", dictionary)
        _write_json(data_dir / "ethnobotany.json", ethnobotany)

        cross_link_datasets(config)

        dict_result = _read_json(data_dir / "dictionary.json")
        assert "_linked_ethnobotany" in dict_result["data"][0]


# ── cross_link_datasets: ethnobotany ↔ encyclopedia ──


def test_cross_link_ethnobotany_encyclopedia_by_category():
    """Ethnobotany links to encyclopedia entries in matching categories."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(
            tmp_path,
            modules={
                "dictionary": False, "fauna": False,
                "ethnobotany": True, "encyclopedia": True,
            },
            ethno_enc_categories=["natureza/flora"],
        )
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        ethnobotany = {"data": [
            {"id": 201, "name_indigenous": "castanha", "name_portuguese": "Castanheira", "scientific_name": "Bertholletia excelsa"},
        ]}
        encyclopedia = {"data": [
            {"id": 301, "title": "Castanheira", "categories": ["natureza/flora"]},
            {"id": 302, "title": "Unrelated", "categories": ["sociedade"]},
        ]}

        _write_json(data_dir / "ethnobotany.json", ethnobotany)
        _write_json(data_dir / "encyclopedia.json", encyclopedia)

        cross_link_datasets(config)

        ethno_result = _read_json(data_dir / "ethnobotany.json")
        entry = ethno_result["data"][0]
        assert "_linked_encyclopedia" in entry
        assert len(entry["_linked_encyclopedia"]) == 1
        assert entry["_linked_encyclopedia"][0]["id"] == 301
        assert entry["_linked_encyclopedia"][0]["title"] == "Castanheira"


def test_cross_link_ethnobotany_encyclopedia_matches_scientific_name():
    """Ethnobotany links to encyclopedia when scientific_name matches title."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(
            tmp_path,
            modules={
                "dictionary": False, "fauna": False,
                "ethnobotany": True, "encyclopedia": True,
            },
            ethno_enc_categories=["flora"],
        )
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        ethnobotany = {"data": [
            {"id": 201, "name_indigenous": "xxx", "name_portuguese": "yyy", "scientific_name": "Acacia"},
        ]}
        encyclopedia = {"data": [
            {"id": 301, "title": "Acacia", "categories": ["flora"]},
        ]}

        _write_json(data_dir / "ethnobotany.json", ethnobotany)
        _write_json(data_dir / "encyclopedia.json", encyclopedia)

        cross_link_datasets(config)

        ethno_result = _read_json(data_dir / "ethnobotany.json")
        assert "_linked_encyclopedia" in ethno_result["data"][0]


def test_cross_link_ethnobotany_encyclopedia_no_match():
    """No links when ethnobotany names do not match any encyclopedia title."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(
            tmp_path,
            modules={
                "dictionary": False, "fauna": False,
                "ethnobotany": True, "encyclopedia": True,
            },
            ethno_enc_categories=["flora"],
        )
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        ethnobotany = {"data": [
            {"id": 201, "name_indigenous": "foo", "name_portuguese": "bar", "scientific_name": "baz"},
        ]}
        encyclopedia = {"data": [
            {"id": 301, "title": "Something Else", "categories": ["flora"]},
        ]}

        _write_json(data_dir / "ethnobotany.json", ethnobotany)
        _write_json(data_dir / "encyclopedia.json", encyclopedia)

        cross_link_datasets(config)

        ethno_result = _read_json(data_dir / "ethnobotany.json")
        assert "_linked_encyclopedia" not in ethno_result["data"][0]


# ── cross_link_datasets: dictionary → encyclopedia ──


def test_cross_link_dictionary_encyclopedia_by_title():
    """Dictionary entry links to encyclopedia when entry matches title."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path, modules={
            "dictionary": True, "encyclopedia": True,
            "fauna": False, "ethnobotany": False,
        })
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [
            {"id": 1, "entry": "castanha", "definition": "nut"},
            {"id": 2, "entry": "no-match", "definition": "nope"},
        ]}
        encyclopedia = {"data": [
            {"id": 301, "title": "castanha", "categories": []},
        ]}

        _write_json(data_dir / "dictionary.json", dictionary)
        _write_json(data_dir / "encyclopedia.json", encyclopedia)

        cross_link_datasets(config)

        dict_result = _read_json(data_dir / "dictionary.json")
        entry1 = dict_result["data"][0]
        entry2 = dict_result["data"][1]

        assert "_linked_encyclopedia" in entry1
        assert entry1["_linked_encyclopedia"][0]["id"] == 301

        assert "_linked_encyclopedia" not in entry2


def test_cross_link_dictionary_encyclopedia_with_spaces():
    """Dictionary-encyclopedia title matching normalises spaces to hyphens."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path, modules={
            "dictionary": True, "encyclopedia": True,
            "fauna": False, "ethnobotany": False,
        })
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [
            {"id": 1, "entry": "my word", "definition": "test"},
        ]}
        encyclopedia = {"data": [
            {"id": 301, "title": "my word", "categories": []},
        ]}

        _write_json(data_dir / "dictionary.json", dictionary)
        _write_json(data_dir / "encyclopedia.json", encyclopedia)

        cross_link_datasets(config)

        dict_result = _read_json(data_dir / "dictionary.json")
        assert "_linked_encyclopedia" in dict_result["data"][0]


def test_cross_link_dictionary_encyclopedia_strips_leading_hyphen():
    """Dictionary entry with leading hyphen still matches encyclopedia title."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path, modules={
            "dictionary": True, "encyclopedia": True,
            "fauna": False, "ethnobotany": False,
        })
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [
            {"id": 1, "entry": "-castanha", "definition": "nut"},
        ]}
        encyclopedia = {"data": [
            {"id": 301, "title": "castanha", "categories": []},
        ]}

        _write_json(data_dir / "dictionary.json", dictionary)
        _write_json(data_dir / "encyclopedia.json", encyclopedia)

        cross_link_datasets(config)

        dict_result = _read_json(data_dir / "dictionary.json")
        assert "_linked_encyclopedia" in dict_result["data"][0]


# ── cross_link_datasets: edge cases ──


def test_cross_link_empty_datasets():
    """Cross-linking with empty data arrays does not fail."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path, modules={
            "dictionary": True, "fauna": True,
            "ethnobotany": True, "encyclopedia": True,
        })
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        _write_json(data_dir / "dictionary.json", {"data": []})
        _write_json(data_dir / "fauna.json", {"data": []})
        _write_json(data_dir / "ethnobotany.json", {"data": []})
        _write_json(data_dir / "encyclopedia.json", {"data": []})

        cross_link_datasets(config)

        # No errors; all files remain with empty data
        assert _read_json(data_dir / "dictionary.json")["data"] == []


def test_cross_link_missing_files_skips():
    """cross_link_datasets skips when enabled modules have missing files."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path, modules={
            "dictionary": True, "fauna": True,
            "ethnobotany": False, "encyclopedia": False,
        })
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        # Only dictionary.json exists, fauna.json is missing
        _write_json(data_dir / "dictionary.json", {"data": [{"id": 1, "entry": "w"}]})

        # Should not raise
        cross_link_datasets(config)


def test_cross_link_all_modules_together():
    """All four cross-link types work simultaneously."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(
            tmp_path,
            modules={
                "dictionary": True, "fauna": True,
                "ethnobotany": True, "encyclopedia": True,
            },
            ethno_enc_categories=["natureza/flora"],
        )
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [
            {"id": 1, "entry": "araara", "scientific_name": "Ara ararauna", "definition": "macaw"},
            {"id": 2, "entry": "castanha", "scientific_name": "Bertholletia excelsa", "definition": "nut"},
        ]}
        fauna = {"data": [
            {"id": 101, "scientific_name": "Ara ararauna", "name_indigenous": "araara", "name_portuguese": "arara"},
        ]}
        ethnobotany = {"data": [
            {"id": 201, "scientific_name": "Bertholletia excelsa", "name_indigenous": "tahi", "name_portuguese": "castanha"},
        ]}
        encyclopedia = {"data": [
            {"id": 301, "title": "castanha", "categories": ["natureza/flora"]},
            {"id": 302, "title": "araara", "categories": ["cultura"]},
        ]}

        _write_json(data_dir / "dictionary.json", dictionary)
        _write_json(data_dir / "fauna.json", fauna)
        _write_json(data_dir / "ethnobotany.json", ethnobotany)
        _write_json(data_dir / "encyclopedia.json", encyclopedia)

        cross_link_datasets(config)

        dict_result = _read_json(data_dir / "dictionary.json")
        fauna_result = _read_json(data_dir / "fauna.json")
        ethno_result = _read_json(data_dir / "ethnobotany.json")

        # dict entry 1: fauna link + encyclopedia link (araara matches enc 302)
        d1 = dict_result["data"][0]
        assert "_linked_fauna" in d1
        assert d1["_linked_fauna"][0]["id"] == 101
        assert "_linked_encyclopedia" in d1
        assert d1["_linked_encyclopedia"][0]["id"] == 302

        # dict entry 2: ethnobotany link + encyclopedia link (castanha matches enc 301)
        d2 = dict_result["data"][1]
        assert "_linked_ethnobotany" in d2
        assert d2["_linked_ethnobotany"][0]["id"] == 201
        assert "_linked_encyclopedia" in d2
        assert d2["_linked_encyclopedia"][0]["id"] == 301

        # fauna links back to dictionary
        assert "_linked_dictionary" in fauna_result["data"][0]

        # ethnobotany links back to dictionary and to encyclopedia
        e = ethno_result["data"][0]
        assert "_linked_dictionary" in e
        assert "_linked_encyclopedia" in e
        assert e["_linked_encyclopedia"][0]["id"] == 301


def test_cross_link_disabled_module_ignored():
    """Disabled modules are not processed even if their files exist."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path, modules={
            "dictionary": True, "fauna": False,
            "ethnobotany": False, "encyclopedia": False,
        })
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [
            {"id": 1, "entry": "bird", "scientific_name": "Ara ararauna", "definition": "macaw"},
        ]}
        fauna = {"data": [
            {"id": 101, "scientific_name": "Ara ararauna", "name_indigenous": "araara", "name_portuguese": "arara"},
        ]}

        _write_json(data_dir / "dictionary.json", dictionary)
        _write_json(data_dir / "fauna.json", fauna)

        cross_link_datasets(config)

        dict_result = _read_json(data_dir / "dictionary.json")
        # Fauna module is disabled, so no fauna links should appear
        assert "_linked_fauna" not in dict_result["data"][0]


def test_cross_link_multiple_fauna_same_scientific_name():
    """Multiple fauna entries with the same scientific_name all link to dictionary."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path, modules={
            "dictionary": True, "fauna": True,
            "ethnobotany": False, "encyclopedia": False,
        })
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [
            {"id": 1, "entry": "bird", "scientific_name": "Ara ararauna", "definition": "macaw"},
        ]}
        fauna = {"data": [
            {"id": 101, "scientific_name": "Ara ararauna", "name_indigenous": "a1", "name_portuguese": "p1"},
            {"id": 102, "scientific_name": "Ara ararauna", "name_indigenous": "a2", "name_portuguese": "p2"},
        ]}

        _write_json(data_dir / "dictionary.json", dictionary)
        _write_json(data_dir / "fauna.json", fauna)

        cross_link_datasets(config)

        dict_result = _read_json(data_dir / "dictionary.json")
        linked = dict_result["data"][0]["_linked_fauna"]
        assert len(linked) == 2
        assert {l["id"] for l in linked} == {101, 102}


def test_cross_link_missing_optional_fields():
    """Entries missing optional fields (name_indigenous, etc.) get empty strings in links."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path, modules={
            "dictionary": True, "fauna": True,
            "ethnobotany": False, "encyclopedia": False,
        })
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        dictionary = {"data": [
            {"id": 1, "scientific_name": "Ara sp."},
        ]}
        fauna = {"data": [
            {"id": 101, "scientific_name": "Ara sp."},
        ]}

        _write_json(data_dir / "dictionary.json", dictionary)
        _write_json(data_dir / "fauna.json", fauna)

        cross_link_datasets(config)

        dict_result = _read_json(data_dir / "dictionary.json")
        linked = dict_result["data"][0]["_linked_fauna"][0]
        assert linked["name_indigenous"] == ""
        assert linked["name_portuguese"] == ""

        fauna_result = _read_json(data_dir / "fauna.json")
        f_linked = fauna_result["data"][0]["_linked_dictionary"][0]
        assert f_linked["entry"] == ""
        assert f_linked["definition"] == ""
