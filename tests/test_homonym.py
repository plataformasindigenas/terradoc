"""Homonym numbers live in their own column (aka¹, aka²), not typed into the headword."""

import json
from pathlib import Path

from tests.test_orthography import build, project, run  # noqa: F401


def test_homonym_column(project):
    (project / "data" / "dictionary.tsv").write_text(
        "id\tentry\thomonym\tdefinition\n1\taka\t2\tsecond\n2\taka\t1\tfirst\n3\tba\t\tplain\n",
        encoding="utf-8")
    for old in (project / "data").glob("dictionary.y*ml"):
        old.unlink()
    result = build(project)
    assert result.exit_code == 0, result.output
    data = json.loads((Path("bundle") / "dictionary.json").read_text())["data"]
    assert [(e["entry"], e["homonym"]) for e in data] == [("aka", 2), ("aka", 1), ("ba", None)]
    html = (Path("site") / "pt" / "dictionary.html").read_text()
    assert 'aka<sup class="homonym">2</sup>' in html  # the page without JavaScript
    assert "function headwordHtml(e)" in html
    assert "(a.homonym || 0) - (b.homonym || 0)" in html  # homonyms sort by number


def test_homonyms_get_no_automatic_encyclopedia_link():
    from terradoc.cross_linker import _link_dict_encyclopedia

    entries = [{"id": 1, "entry": "ba", "homonym": 1}, {"id": 2, "entry": "ba"}]
    _link_dict_encyclopedia(entries, [{"id": "ba", "title": "Ba"}])
    assert "_linked_encyclopedia" not in entries[0]
    assert entries[1]["_linked_encyclopedia"] == [{"id": "ba", "title": "Ba"}]
