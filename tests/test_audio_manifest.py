"""data/audio/manifest.tsv: audio matched to entries by id, with consent, and no names."""

import json
from pathlib import Path

from tests.test_orthography import build, check, project, run, write_dictionary  # noqa: F401

HEADER = "file\tentry_id\tspeaker\tconsent\n"


def add_audio(project: Path, *names: str, manifest: str | None = None):
    audio = project / "data" / "audio"
    audio.mkdir(parents=True, exist_ok=True)
    for name in names:
        (audio / name).write_bytes(b"webm")
    if manifest is not None:
        (audio / "manifest.tsv").write_text(HEADER + manifest, encoding="utf-8")


def audio_of(bundle: Path) -> dict[int, list[str]]:
    data = json.loads((bundle / "dictionary.json").read_text(encoding="utf-8"))["data"]
    return {e["id"]: [a["file_path"] for a in e.get("audio", [])] for e in data}


def test_without_manifest_audio_follows_the_headword(project):
    write_dictionary(project, ("ba 1", "ba"), ("ba 2", "ba"))
    add_audio(project, "ba_1.webm")
    assert build(project).exit_code == 0
    assert audio_of(Path("bundle")) == {1: ["ba_1.webm"], 2: []}


def test_manifest_matches_by_id_whatever_the_headword(project):
    write_dictionary(project, ("ba", "ba"), ("ba", "ba"), ("kuri", "kuri"))
    add_audio(project, "ba.webm", "kuri__s.webm", "kuri.webm", "spare.webm",
              manifest="ba.webm\t2\t\tapproved\nkuri__s.webm\t3\ts01\tapproved\n"
                       "kuri.webm\t3\t\tapproved\nspare.webm\t1\t\tpending\n")
    result = check(project)
    assert result.exit_code != 0
    assert "spare.webm: 'consent' must be one of approved, external" in result.output

    (project / "data" / "audio" / "spare.webm").unlink()
    manifest = project / "data" / "audio" / "manifest.tsv"
    manifest.write_text("\n".join(manifest.read_text().splitlines()[:-1]) + "\n")
    result = build(project)
    assert result.exit_code == 0, result.output
    assert audio_of(Path("bundle")) == {1: [], 2: ["ba.webm"], 3: ["kuri.webm", "kuri__s.webm"]}
    assert sorted(p.name for p in (Path("site") / "audio").iterdir()) == ["ba.webm", "kuri.webm", "kuri__s.webm"]


def test_manifest_errors(project):
    write_dictionary(project, ("ba", "ba"))
    add_audio(project, "ba.webm", "extra.webm",
              manifest="ba.webm\t1\tMaria\tapproved\nba.webm\t1\t\tapproved\ngone.webm\t9\t\tapproved\n")
    out = check(project).output
    assert "speaker 'Maria' must be an id such as s01, not a name" in out
    assert "ba.webm → 1 is listed twice" in out
    assert "missing file 'gone.webm'" in out
    assert "gone.webm: no dictionary entry with id '9'" in out
    assert "extra.webm is not in the manifest" in out


def test_manifest_columns(project):
    write_dictionary(project, ("ba", "ba"))
    add_audio(project, "ba.webm")
    (project / "data" / "audio" / "manifest.tsv").write_text("file\tentry\nba.webm\t1\n")
    assert "columns must be file entry_id speaker consent" in check(project).output
