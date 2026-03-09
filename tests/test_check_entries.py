"""Tests for terradoc encyclopedia entry validation."""

import tempfile
from pathlib import Path

import yaml

from terradoc.check_entries import check_entries, load_categories_vocabulary, _parse_front_matter


def _make_entry(tmp: Path, filename: str, content: str):
    """Helper to create a markdown entry file."""
    entry_dir = tmp / "encyclopedia"
    entry_dir.mkdir(exist_ok=True)
    (entry_dir / filename).write_text(content, encoding="utf-8")


def test_check_entries_valid():
    """check_entries returns 0 for valid entries."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "test-entry.md", """---
id: test-entry
title: Test Entry
date: 2024-01-01
categories:
  - test
---
This is the body.
""")
        assert check_entries(tmp_path) == 0


def test_check_entries_missing_id():
    """check_entries catches missing id."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "bad.md", """---
title: No ID
---
Body text.
""")
        assert check_entries(tmp_path) == 1


def test_check_entries_duplicate_id():
    """check_entries catches duplicate ids."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "a.md", """---
id: same-id
title: Entry A
---
Body A.
""")
        _make_entry(tmp_path, "b.md", """---
id: same-id
title: Entry B
---
Body B.
""")
        assert check_entries(tmp_path) == 1


def test_check_entries_html_in_body():
    """check_entries catches HTML tags in body."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "html.md", """---
id: html-entry
title: HTML Entry
---
This has <div>HTML</div> in it.
""")
        assert check_entries(tmp_path) == 1


def test_check_entries_bad_date():
    """check_entries catches invalid date format."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "bad-date.md", """---
id: bad-date
title: Bad Date
date: January 2024
---
Body.
""")
        assert check_entries(tmp_path) == 1


def test_check_entries_missing_directory():
    """check_entries returns 1 for missing encyclopedia directory."""
    with tempfile.TemporaryDirectory() as tmp:
        assert check_entries(Path(tmp)) == 1


def test_check_entries_empty_directory_is_ok():
    """check_entries accepts an empty encyclopedia directory."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "encyclopedia").mkdir()
        assert check_entries(tmp_path) == 0


def test_check_entries_list_field_not_list():
    """check_entries catches non-list value for list fields."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "bad-list.md", """---
id: bad-list
title: Bad List
categories: not-a-list
---
Body.
""")
        assert check_entries(tmp_path) == 1


def test_parse_front_matter_valid():
    """_parse_front_matter extracts front matter and body."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.md"
        path.write_text("---\nid: test\ntitle: Test\n---\nBody text.\n")
        fm, body = _parse_front_matter(path)
        assert fm["id"] == "test"
        assert fm["title"] == "Test"
        assert "Body text." in body


def test_parse_front_matter_missing_start():
    """_parse_front_matter raises for missing --- start."""
    import pytest

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bad.md"
        path.write_text("No front matter here.\n")
        with pytest.raises(ValueError, match="missing front matter start"):
            _parse_front_matter(path)


# ── ID format validation ──


def test_check_entries_id_format_uppercase():
    """check_entries rejects uppercase characters in id."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "Bad-Id.md", """---
id: Bad-Id
title: Uppercase
---
Body.
""")
        assert check_entries(tmp_path) == 1


def test_check_entries_id_format_underscore():
    """check_entries rejects underscores in id."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "bad_id.md", """---
id: bad_id
title: Underscore
---
Body.
""")
        assert check_entries(tmp_path) == 1


def test_check_entries_id_format_spaces():
    """check_entries rejects spaces in id."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "bad id.md", """---
id: "bad id"
title: Spaces
---
Body.
""")
        assert check_entries(tmp_path) == 1


def test_check_entries_id_format_accents():
    """check_entries rejects accented characters in id."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "café.md", """---
id: café
title: Accent
---
Body.
""")
        assert check_entries(tmp_path) == 1


def test_check_entries_id_format_starts_with_hyphen():
    """check_entries rejects id starting with hyphen."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "-bad.md", """---
id: "-bad"
title: Hyphen start
---
Body.
""")
        assert check_entries(tmp_path) == 1


def test_check_entries_id_format_valid():
    """check_entries accepts well-formed ids."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "good-id-123.md", """---
id: good-id-123
title: Good ID
---
Body.
""")
        assert check_entries(tmp_path) == 0


# ── Filename/ID consistency ──


def test_check_entries_filename_mismatch():
    """check_entries fails when filename stem doesn't match id."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "wrong-name.md", """---
id: actual-id
title: Mismatch
---
Body.
""")
        assert check_entries(tmp_path) == 1


def test_check_entries_filename_matches():
    """check_entries passes when filename stem matches id."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "my-entry.md", """---
id: my-entry
title: Match
---
Body.
""")
        assert check_entries(tmp_path) == 0


# ── see_also referential integrity ──


def test_check_entries_see_also_valid():
    """check_entries passes when see_also targets exist."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "entry-a.md", """---
id: entry-a
title: Entry A
see_also:
  - entry-b
---
Body A.
""")
        _make_entry(tmp_path, "entry-b.md", """---
id: entry-b
title: Entry B
---
Body B.
""")
        assert check_entries(tmp_path) == 0


def test_check_entries_see_also_broken():
    """check_entries fails when see_also target doesn't exist."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "entry-a.md", """---
id: entry-a
title: Entry A
see_also:
  - nonexistent-entry
---
Body A.
""")
        assert check_entries(tmp_path) == 1


def test_check_entries_see_also_multiple_broken():
    """check_entries reports all broken see_also targets."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "entry-a.md", """---
id: entry-a
title: Entry A
see_also:
  - ghost-1
  - ghost-2
---
Body A.
""")
        assert check_entries(tmp_path) == 1


# ── Category vocabulary validation ──


def test_load_categories_vocabulary_missing_file():
    """Returns None when categories.yaml doesn't exist."""
    with tempfile.TemporaryDirectory() as tmp:
        assert load_categories_vocabulary(Path(tmp)) is None


def test_load_categories_vocabulary_valid():
    """Returns set of category paths."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        vocab = ["society", "society/organization", "nature"]
        (tmp_path / "categories.yaml").write_text(
            yaml.dump(vocab), encoding="utf-8"
        )
        result = load_categories_vocabulary(tmp_path)
        assert result == {"society", "society/organization", "nature"}


def test_load_categories_vocabulary_non_list():
    """Returns None and warns for non-list format."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "categories.yaml").write_text("key: value\n", encoding="utf-8")
        assert load_categories_vocabulary(tmp_path) is None


def test_check_entries_category_valid():
    """check_entries passes when categories match vocabulary."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        vocab = ["society", "nature"]
        (tmp_path / "categories.yaml").write_text(
            yaml.dump(vocab), encoding="utf-8"
        )
        _make_entry(tmp_path, "my-entry.md", """---
id: my-entry
title: My Entry
categories:
  - society
---
Body.
""")
        assert check_entries(tmp_path) == 0


def test_check_entries_category_invalid():
    """check_entries fails when category not in vocabulary."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        vocab = ["society", "nature"]
        (tmp_path / "categories.yaml").write_text(
            yaml.dump(vocab), encoding="utf-8"
        )
        _make_entry(tmp_path, "my-entry.md", """---
id: my-entry
title: My Entry
categories:
  - unknown-category
---
Body.
""")
        assert check_entries(tmp_path) == 1


def test_check_entries_no_vocabulary_skips_validation():
    """Without categories.yaml, any category is accepted."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "my-entry.md", """---
id: my-entry
title: My Entry
categories:
  - anything-goes
---
Body.
""")
        assert check_entries(tmp_path) == 0
