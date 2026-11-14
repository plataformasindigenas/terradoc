"""0.12: `terradoc guard`, markdown reports, CODEOWNERS mentions, module counts."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from terradoc.checks import Issue, codeowners_for, format_markdown
from terradoc.cli import main
from terradoc.guard import compare_releases


def site(root: Path, name: str, modules: dict, files: int = 30) -> Path:
    d = root / name
    d.mkdir()
    for i in range(files):
        (d / f"page{i}.html").write_text("x")
    (d / ".release.json").write_text(json.dumps({"modules": modules}))
    return d


def errors(issues):
    return [i for i in issues if i.level == "error"]


# ── shrink against the previous release ──────────────────────────────────

@pytest.mark.parametrize("before,after,blocked", [
    (100, 100, False),
    (100, 91, False),   # -9 %, -9 rows
    (100, 89, True),    # -11 %
    (1000, 979, True),  # -2.1 % but -21 rows
    (1000, 981, False), # -19 rows, -1.9 %
    (5, 0, True),       # emptied
    (100, 150, False),  # growth is fine
])
def test_shrink_thresholds(tmp_path, before, after, blocked):
    prev = site(tmp_path, "prev", {"dictionary": before})
    cur = site(tmp_path, "cur", {"dictionary": after})
    assert bool(errors(compare_releases(cur, prev))) == blocked


def test_vanished_module_blocks(tmp_path):
    prev = site(tmp_path, "prev", {"dictionary": 50, "fauna": 40})
    cur = site(tmp_path, "cur", {"dictionary": 50})
    [issue] = errors(compare_releases(cur, prev))
    assert "'fauna' went from 40 to 0" in issue.message


def test_confirm_shrink_turns_errors_into_warnings(tmp_path):
    prev = site(tmp_path, "prev", {"dictionary": 100})
    cur = site(tmp_path, "cur", {"dictionary": 10})
    issues = compare_releases(cur, prev, confirm_shrink=True)
    assert issues and not errors(issues)


def test_baseline_catches_slow_erosion(tmp_path):
    base = site(tmp_path, "base", {"dictionary": 1000})
    prev = site(tmp_path, "prev", {"dictionary": 760})
    cur = site(tmp_path, "cur", {"dictionary": 745})   # -2 % vs previous, -25.5 % vs baseline
    assert not errors(compare_releases(cur, prev))
    [issue] = errors(compare_releases(cur, prev, baseline=base))
    assert "baseline" in issue.message


def test_no_previous_release_is_allowed(tmp_path):
    cur = site(tmp_path, "cur", {"dictionary": 1})
    assert compare_releases(cur, None) == []


def test_previous_without_counts_warns_only(tmp_path):
    prev = site(tmp_path, "prev", {})
    cur = site(tmp_path, "cur", {"dictionary": 1})
    issues = compare_releases(cur, prev)
    assert issues and not errors(issues)


# ── file loss ────────────────────────────────────────────────────────────

def test_file_loss_threshold(tmp_path):
    prev = site(tmp_path, "prev", {"d": 1}, files=400)   # limit = max(10, 20) = 20
    cur = site(tmp_path, "cur", {"d": 1}, files=380)
    assert not errors(compare_releases(cur, prev))
    for i in range(379, 375, -1):
        (cur / f"page{i}.html").unlink()                 # now 24 lost
    [issue] = errors(compare_releases(cur, prev))
    assert "24 files of the previous release are missing (limit 20)" in issue.message


def test_small_sites_get_a_floor_of_ten_files(tmp_path):
    prev = site(tmp_path, "prev", {"d": 1}, files=30)
    cur = site(tmp_path, "cur", {"d": 1}, files=20)      # 10 lost: allowed
    assert not errors(compare_releases(cur, prev))


def test_previous_not_built_by_terradoc_is_a_warning(tmp_path):
    (tmp_path / "plain").mkdir()
    cur = site(tmp_path, "cur", {"d": 1})
    result = CliRunner().invoke(main, ["guard", "--current", str(cur), "--previous", str(tmp_path / "plain")])
    assert result.exit_code == 0, result.output
    assert "comparison with it skipped" in result.output


def test_current_without_release_json_is_an_error(tmp_path):
    (tmp_path / "plain").mkdir()
    result = CliRunner().invoke(main, ["guard", "--current", str(tmp_path / "plain")])
    assert result.exit_code == 1
    assert "no .release.json" in result.output


def test_guard_cli_exit_codes(tmp_path):
    prev = site(tmp_path, "prev", {"dictionary": 100})
    cur = site(tmp_path, "cur", {"dictionary": 50})
    runner = CliRunner()
    assert runner.invoke(main, ["guard", "--current", str(cur), "--previous", str(prev)]).exit_code == 1
    ok = runner.invoke(main, ["guard", "--current", str(cur), "--previous", str(prev), "--confirm-shrink"])
    assert ok.exit_code == 0, ok.output


# ── release info carries module counts ───────────────────────────────────

def test_release_json_has_module_counts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(main, ["init", "demo"]).exit_code == 0
    (tmp_path / "demo" / "data" / "dictionary.tsv").write_text("id\tentry\n1\tka\n2\tko\n")
    result = runner.invoke(main, ["build", "-c", "demo/terradoc.yaml", "--out", "site"])
    assert result.exit_code == 0, result.output
    release = json.loads((tmp_path / "site" / ".release.json").read_text())
    assert release["modules"]["dictionary"] == 2


# ── markdown + CODEOWNERS ────────────────────────────────────────────────

def test_markdown_report_is_bilingual_and_escapes_tables():
    md = format_markdown([Issue("error", "consent", "a | b", "data/videos.yaml", 3)],
                         mentions=["@ana"], run_url="https://example/run/1")
    assert "Publicação bloqueada / Publication blocked" in md
    assert "| ❌ | `data/videos.yaml` | 3 | [consent] a \\| b |" in md
    assert "https://example/run/1" in md
    assert md.rstrip().endswith("cc @ana")


def test_markdown_all_good():
    assert "Tudo certo" in format_markdown([])


@pytest.fixture()
def codeowners(tmp_path):
    p = tmp_path / "CODEOWNERS"
    p.write_text(
        "# comment\n"
        "*                    @owner\n"
        "data/encyclopedia/   @writer\n"
        "/data/*.tsv          @lexicographer @owner\n"
        "*.bib                @librarian\n")
    return p


@pytest.mark.parametrize("file,expected", [
    ("data/encyclopedia/boe.md", ["@writer"]),
    ("data/dictionary.tsv", ["@lexicographer", "@owner"]),
    ("data/sub/x.tsv", ["@owner"]),            # /data/*.tsv does not reach subdirs
    ("data/references.bib", ["@librarian"]),
    ("terradoc.yaml", ["@owner"]),
    (None, ["@owner"]),                        # issue without a file → '*' rule
])
def test_codeowners_last_match_wins(codeowners, file, expected):
    assert codeowners_for([file], codeowners) == expected


def test_codeowners_dedup_and_missing_file(codeowners, tmp_path):
    assert codeowners_for(["data/dictionary.tsv", "terradoc.yaml"], codeowners) == ["@lexicographer", "@owner"]
    assert codeowners_for(["x"], tmp_path / "nope") == []


def test_check_markdown_mentions_owners(tmp_path, monkeypatch, codeowners):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(main, ["init", "demo"]).exit_code == 0
    (tmp_path / "demo" / "data" / "dictionary.tsv").write_text("id\tentry\n1\tka\n1\tko\n")
    result = runner.invoke(main, ["check", "-c", "demo/terradoc.yaml", "--format", "markdown",
                                  "--codeowners", str(codeowners)])
    assert result.exit_code == 1
    assert "`data/dictionary.tsv` | 3 |" in result.output
    assert "cc @lexicographer @owner" in result.output


@pytest.mark.parametrize("pattern,file,expected", [
    # examples from GitHub's CODEOWNERS documentation
    ("*.js", "a/b/c.js", True),
    ("docs/*", "docs/getting-started.md", True),
    ("docs/*", "docs/build-app/troubleshooting.md", False),
    ("/build/logs/", "build/logs/x/y.log", True),
    ("/build/logs/", "x/build/logs/y.log", False),
    ("apps/", "any/apps/z.py", True),
    ("/docs/", "x/docs/a.md", False),
    ("**/logs", "deep/er/logs/a.log", True),
    ("/data/*.tsv", "data/sub/x.tsv", False),
])
def test_codeowners_github_examples(pattern, file, expected):
    from terradoc.checks import _codeowners_match
    assert _codeowners_match(pattern, file) is expected
