"""0.11 pipeline: check / export / render, --out / --bundle-dir, static/, release info."""

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from terradoc.cli import main


@pytest.fixture()
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    result = CliRunner().invoke(main, ["init", "demo"])
    assert result.exit_code == 0, result.output
    return tmp_path / "demo"


def run(*args):
    return CliRunner().invoke(main, list(args))


def enable(project: Path, module: str):
    cfg = project / "terradoc.yaml"
    text = cfg.read_text()
    text = text.replace(f"{module}: {{ enabled: false }}", f"{module}: {{ enabled: true }}")
    cfg.write_text(text)


VIDEO = """- youtube_id: abc123
  title: "A story"
{extra}"""


def write_videos(project: Path, *rows: str):
    (project / "data" / "videos.yaml").write_text("".join(rows))


# ── build layout ─────────────────────────────────────────────────────────

def test_build_out_and_bundle_leave_sources_untouched(project):
    cfg = str(project / "terradoc.yaml")
    before = sorted(p.name for p in (project / "data").rglob("*"))
    result = run("build", "-c", cfg, "--out", "site", "--bundle-dir", "bundle")
    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in (project / "data").rglob("*")) == before
    assert not (project / "docs").exists()
    assert (Path("site") / "pt" / "index.html").exists()
    manifest = json.loads((Path("bundle") / "manifest.json").read_text())
    assert manifest["bundle_schema"] == "0-experimental"
    assert "dictionary" in manifest["modules"]
    release = json.loads((Path("site") / ".release.json").read_text())
    assert release["project"] == "demo"
    assert release["files"] > 0


def test_default_build_keeps_historic_layout(project):
    result = run("build", "-c", str(project / "terradoc.yaml"))
    assert result.exit_code == 0, result.output
    assert (project / "docs" / "pt" / "index.html").exists()
    assert (project / "data" / "dictionary.json").exists()


def test_release_info_uses_ci_environment(project, monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "deadbeef")
    monkeypatch.setenv("GITHUB_REF_NAME", "feature-x")
    result = run("build", "-c", str(project / "terradoc.yaml"), "--out", "site")
    assert result.exit_code == 0, result.output
    release = json.loads((Path("site") / ".release.json").read_text())
    assert release["source_commit"] == "deadbeef"
    assert release["source_ref"] == "feature-x"


def test_static_copied_verbatim(project):
    (project / "static" / "audio").mkdir()
    (project / "static" / "audio" / "song.webm").write_bytes(b"\x1aE\xdf\xa3")
    result = run("build", "-c", str(project / "terradoc.yaml"), "--out", "site")
    assert result.exit_code == 0, result.output
    assert (Path("site") / "audio" / "song.webm").read_bytes() == b"\x1aE\xdf\xa3"
    assert (Path("site") / "images" / "logo.svg").exists()


def test_static_clobbered_by_generated_file_fails(project):
    (project / "static" / "robots.txt").write_text("mine\n")
    result = run("build", "-c", str(project / "terradoc.yaml"), "--out", "site")
    assert result.exit_code != 0
    assert "robots.txt" in str(result.exception)


@pytest.mark.skipif(os.name == "nt", reason="symlinks")
def test_static_symlink_refused(project):
    (project / "static" / "link.txt").symlink_to("/etc/hostname")
    result = run("build", "-c", str(project / "terradoc.yaml"), "--out", "site")
    assert result.exit_code != 0
    assert "symlink" in str(result.exception)


def test_clean_requires_out(project):
    result = run("build", "-c", str(project / "terradoc.yaml"), "--clean")
    assert result.exit_code != 0
    assert "--clean needs --out" in str(result.exception)


def test_clean_removes_stale_files(project):
    stale = Path("site") / "stale.html"
    stale.parent.mkdir()
    stale.write_text("old")
    result = run("build", "-c", str(project / "terradoc.yaml"), "--out", "site", "--clean")
    assert result.exit_code == 0, result.output
    assert not stale.exists()


def test_render_without_export_explains(project):
    result = run("render", "-c", str(project / "terradoc.yaml"), "--bundle-dir", "nowhere", "--out", "site")
    assert result.exit_code != 0
    assert "terradoc export" in str(result.exception)


def test_export_then_render_equals_build(project):
    cfg = str(project / "terradoc.yaml")
    assert run("export", "-c", cfg, "--bundle-dir", "b1").exit_code == 0
    assert run("render", "-c", cfg, "--bundle-dir", "b1", "--out", "s1").exit_code == 0
    assert run("build", "-c", cfg, "--bundle-dir", "b2", "--out", "s2").exit_code == 0
    files1 = {p.relative_to("s1"): p.read_bytes() for p in Path("s1").rglob("*") if p.is_file()}
    files2 = {p.relative_to("s2"): p.read_bytes() for p in Path("s2").rglob("*") if p.is_file()}
    assert files1 == files2


# ── check rules ──────────────────────────────────────────────────────────

def test_check_clean_project_passes(project):
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert result.exit_code == 0, result.output
    assert "0 error(s)" in result.output


@pytest.mark.parametrize("extra,ok", [
    ("", False),
    ("  consent: pending\n", False),
    ("  consent: approved\n", True),
    ("  consent: external\n", True),
])
def test_consent_rule(project, extra, ok):
    enable(project, "videos")
    write_videos(project, VIDEO.format(extra=extra))
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert (result.exit_code == 0) == ok, result.output
    if not ok:
        assert "[consent] data/videos.yaml:1" in result.output
        assert "abc123 (A story)" in result.output


def test_consent_blocks_build(project):
    enable(project, "videos")
    write_videos(project, VIDEO.format(extra=""))
    result = run("build", "-c", str(project / "terradoc.yaml"), "--out", "site")
    assert result.exit_code != 0
    assert not (Path("site") / "pt" / "videos.html").exists()


def test_consent_line_numbers_point_at_each_row(project):
    enable(project, "videos")
    write_videos(project,
                 "# comment\n", VIDEO.format(extra="  consent: approved\n"),
                 VIDEO.replace("abc123", "def456").format(extra=""))
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert "data/videos.yaml:5" in result.output


def test_missing_media_reported(project):
    enable(project, "videos")
    write_videos(project, VIDEO.format(extra="  consent: approved\n  thumbnail: images/nope.jpg\n"))
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert result.exit_code == 1
    assert "missing file 'images/nope.jpg'" in result.output


def test_media_found_in_static(project):
    enable(project, "videos")
    (project / "static" / "images" / "yes.jpg").write_bytes(b"x")
    write_videos(project, VIDEO.format(extra="  consent: approved\n  thumbnail: images/yes.jpg\n"))
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert result.exit_code == 0, result.output


def test_missing_theme_media_reported(project):
    (project / "static" / "images" / "logo.svg").unlink()
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert result.exit_code == 1
    assert "theme references missing file 'images/logo.svg'" in result.output


def test_schema_error_has_tsv_line(project):
    (project / "data" / "dictionary.tsv").write_text(
        "id\tentry\tdefinition\n1\tka\tsun\n1\tko\tmoon\n")  # duplicate id on line 3
    result = run("check", "-c", str(project / "terradoc.yaml"), "--format", "github")
    assert result.exit_code == 1
    assert "::error file=data/dictionary.tsv,line=3,title=terradoc schema::" in result.output


def test_json_report(project):
    enable(project, "videos")
    write_videos(project, VIDEO.format(extra=""))
    result = run("check", "-c", str(project / "terradoc.yaml"), "--format", "json")
    data = json.loads(result.output.split("\nterradoc check:")[0])
    assert data["ok"] is False
    assert data["issues"][0]["rule"] == "consent"
    assert data["issues"][0]["line"] == 1


def test_check_writes_nothing(project):
    before = {p: p.stat().st_mtime_ns for p in project.rglob("*")}
    assert run("check", "-c", str(project / "terradoc.yaml")).exit_code == 0
    after = {p: p.stat().st_mtime_ns for p in project.rglob("*")}
    assert before == after


# ── templates ────────────────────────────────────────────────────────────

def test_videos_oral_template_renders(project):
    enable(project, "videos")
    (project / "static" / "audio").mkdir()
    (project / "static" / "audio" / "story.mp4").write_bytes(b"x")
    write_videos(project, VIDEO.format(extra="  consent: approved\n  source_url: audio/story.mp4\n"))
    (project / "config" / "videos.yaml").write_text(
        "input: ../data/videos.json\ntemplate: templates/videos_oral.html.j2\noutput: ../docs/videos.html\n")
    result = run("build", "-c", str(project / "terradoc.yaml"), "--out", "site")
    assert result.exit_code == 0, result.output
    html = (Path("site") / "pt" / "videos.html").read_text()
    assert "oc-header" in html
    assert "A story" in html


def test_about_credits_only_with_locale_key(project):
    cfg = str(project / "terradoc.yaml")
    assert run("build", "-c", cfg, "--out", "s1").exit_code == 0
    assert "about_credits" not in (Path("s1") / "pt" / "about.html").read_text()
    with open(project / "locales" / "pt.yaml", "a", encoding="utf-8") as f:
        f.write('\nabout_credits: "<p>Fotos: Fulano</p>"\n')
    assert run("build", "-c", cfg, "--out", "s2").exit_code == 0
    assert "Fotos: Fulano" in (Path("s2") / "pt" / "about.html").read_text()
