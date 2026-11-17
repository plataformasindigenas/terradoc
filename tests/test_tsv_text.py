"""TSV cells stay text until the schema converts them (the Bororo word "no" is not False)."""

import json
from pathlib import Path

from tests.test_orthography import build, project  # noqa: F401


def test_words_that_look_like_booleans_or_numbers(project):
    (project / "data" / "dictionary.tsv").write_text(
        "id\tentry\tdefinition\n1\tno\tyes\n2\t0\t1.5\n3\tTrue\t\n", encoding="utf-8")
    for old in (project / "data").glob("dictionary.y*ml"):
        old.unlink()
    result = build(project)
    assert result.exit_code == 0, result.output
    data = json.loads((Path("bundle") / "dictionary.json").read_text())["data"]
    assert [(e["id"], e["entry"], e["definition"]) for e in data] == [
        (1, "no", "yes"), (2, "0", "1.5"), (3, "True", None)]
