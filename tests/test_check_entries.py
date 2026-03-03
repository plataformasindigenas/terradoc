"""Tests for terradoc encyclopedia entry validation."""

import tempfile
from pathlib import Path

from terradoc.check_entries import check_entries, _parse_front_matter


def _make_entry(tmp: Path, filename: str, content: str):
    """Helper to create a markdown entry file."""
    entry_dir = tmp / "encyclopedia"
    entry_dir.mkdir(exist_ok=True)
    (entry_dir / filename).write_text(content, encoding="utf-8")


def test_check_entries_valid():
    """check_entries returns 0 for valid entries."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_entry(tmp_path, "test.md", """---
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
