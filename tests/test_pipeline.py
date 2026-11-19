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
    assert (Path("site") / "images" / "favicon.svg").exists()


@pytest.mark.parametrize("name", ["robots.txt", ".release.json", "assets/site.css",
                                  "pt/index.html", "sw.js", "offline.html"])
def test_static_clobbering_generated_path_is_a_check_error(project, name):
    target = project / "static" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("mine\n")
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert result.exit_code == 1
    assert f"static/{name}" in result.output


def test_static_clobber_still_caught_at_render(project, monkeypatch):
    """Second line of defence if check is bypassed."""
    (project / "static" / "robots.txt").write_text("mine\n")
    cfg = str(project / "terradoc.yaml")
    import terradoc.export as export
    assert run("export", "-c", cfg, "--bundle-dir", "b").exit_code == 1  # check blocks it
    from terradoc.config import load_config
    c = load_config(project / "terradoc.yaml")
    c.bundle_dir_override = Path("b").resolve()
    export.export_bundle(c, run_checks=False)
    result = run("render", "-c", cfg, "--bundle-dir", "b", "--out", "site")
    assert result.exit_code == 1
    assert "robots.txt" in result.output


@pytest.mark.skipif(os.name == "nt", reason="symlinks")
def test_static_symlink_refused(project):
    (project / "static" / "link.txt").symlink_to("/etc/hostname")
    result = run("build", "-c", str(project / "terradoc.yaml"), "--out", "site")
    assert result.exit_code == 1
    assert "symlinks are not allowed" in result.output


@pytest.mark.skipif(os.name == "nt", reason="symlinks")
def test_static_root_symlink_refused(project, tmp_path):
    real = project / "static"
    moved = tmp_path / "elsewhere"
    real.rename(moved)
    real.symlink_to(moved)
    result = run("build", "-c", str(project / "terradoc.yaml"), "--out", "site")
    assert result.exit_code == 1
    assert "static/ is a symlink" in result.output


def test_clean_requires_out(project):
    result = run("build", "-c", str(project / "terradoc.yaml"), "--clean")
    assert result.exit_code == 1
    assert "--clean needs --out" in result.output


@pytest.mark.parametrize("out", [".", "..", "data", "data/sub", "static", "config", "locales"])
def test_clean_refuses_project_and_sources(project, monkeypatch, out):
    monkeypatch.chdir(project)
    before = sorted(str(p) for p in project.rglob("*"))
    result = run("build", "--out", out, "--clean")
    assert result.exit_code == 1, result.output
    assert "--clean refused" in result.output
    assert sorted(str(p) for p in project.rglob("*")) == before


def test_clean_refuses_bundle_inside_out(project, monkeypatch):
    monkeypatch.chdir(project)
    result = run("build", "--out", "out", "--bundle-dir", "out/bundle", "--clean")
    assert result.exit_code == 1
    assert "overlaps the bundle" in result.output


def test_clean_refuses_unmarked_directory(project):
    keep = Path("site") / "precious.jpg"
    keep.parent.mkdir()
    keep.write_bytes(b"only copy")
    result = run("build", "-c", str(project / "terradoc.yaml"), "--out", "site", "--clean")
    assert result.exit_code == 1
    assert "files terradoc did not create" in result.output
    assert keep.read_bytes() == b"only copy"


def test_clean_refuses_docs_with_files_terradoc_did_not_make(project, monkeypatch):
    """Reviewer repro (0.11): a docs/ holding someone's own file, a plain build into it, then
    --out docs --clean must refuse and keep the file."""
    monkeypatch.chdir(project)
    (project / "docs" / "images").mkdir(parents=True)
    (project / "docs" / "images" / "photo.jpg").write_bytes(b"only copy")
    assert run("build").exit_code == 0
    result = run("build", "--out", "docs", "--clean")
    assert result.exit_code == 1
    assert "--clean refused" in result.output
    assert (project / "docs" / "images" / "photo.jpg").read_bytes() == b"only copy"


def test_render_rechecks_consent_against_sources(project):
    """A bundle exported while consent was given must not render after it is revoked."""
    enable(project, "videos")
    write_videos(project, VIDEO.format(extra="  consent: approved\n"))
    cfg = str(project / "terradoc.yaml")
    assert run("export", "-c", cfg, "--bundle-dir", "b").exit_code == 0
    write_videos(project, VIDEO.format(extra="  consent: pending\n"))
    result = run("render", "-c", cfg, "--bundle-dir", "b", "--out", "site")
    assert result.exit_code == 1
    assert "render refused" in result.output and "[consent]" in result.output
    assert not (Path("site") / "pt" / "videos.html").exists()


def test_clean_removes_stale_files_from_previous_render(project):
    cfg = str(project / "terradoc.yaml")
    assert run("build", "-c", cfg, "--out", "site").exit_code == 0
    stale = Path("site") / "stale.html"
    stale.write_text("old")
    result = run("build", "-c", cfg, "--out", "site", "--clean")
    assert result.exit_code == 0, result.output
    assert not stale.exists()


def test_render_without_export_explains(project):
    result = run("render", "-c", str(project / "terradoc.yaml"), "--bundle-dir", "nowhere", "--out", "site")
    assert result.exit_code == 1
    assert "terradoc export" in result.output


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


def test_consent_blocks_export_and_render(project):
    """export runs the full check, so export+render cannot publish unconsented media."""
    enable(project, "videos")
    write_videos(project, VIDEO.format(extra=""))
    cfg = str(project / "terradoc.yaml")
    result = run("export", "-c", cfg, "--bundle-dir", "b")
    assert result.exit_code == 1
    assert "[consent]" in result.output
    assert not (Path("b") / "videos.json").exists()
    result = run("render", "-c", cfg, "--bundle-dir", "b", "--out", "site")
    assert result.exit_code == 1
    assert not (Path("site") / "pt" / "videos.html").exists()


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
    (project / "static" / "images" / "favicon.svg").unlink()
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert result.exit_code == 1
    assert "theme references missing file 'images/favicon.svg'" in result.output


def test_schema_error_has_tsv_line(project):
    (project / "data" / "dictionary.tsv").write_text(
        "id\tentry\tdefinition\n1\tka\tsun\n1\tko\tmoon\n")  # duplicate id on line 3
    result = run("check", "-c", str(project / "terradoc.yaml"), "--format", "github")
    assert result.exit_code == 1
    assert "::error file=data/dictionary.tsv,line=3,title=terradoc schema::" in result.output


def test_tsv_lines_survive_blank_and_multiline_rows(project):
    (project / "data" / "dictionary.tsv").write_text(
        'id\tentry\tdefinition\n'
        '1\tka\tsun\n'
        '\n'                              # blank line: skipped by the reader
        '2\tko\t"moon\nand night"\n'      # quoted field spanning two lines
        '2\tku\tstar\n')                # duplicate id, on line 6
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert "data/dictionary.tsv:6" in result.output, result.output


def test_duplicate_reported_on_its_own_row_after_invalid_row(project):
    (project / "data" / "dictionary.tsv").write_text(
        "id\tentry\tdefinition\n"
        "x\tbad\tnot an int id\n"   # invalid row 1 (line 2)
        "1\tka\tsun\n"
        "1\tko\tmoon\n")            # duplicate on line 4
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert "data/dictionary.tsv:2" in result.output
    assert "data/dictionary.tsv:4" in result.output
    assert "duplicate id 1 (first used on line 3)" in result.output


def test_github_annotation_properties_escaped(project, monkeypatch):
    enable(project, "videos")
    write_videos(project, VIDEO.format(extra=""))
    monkeypatch.setenv("GITHUB_WORKSPACE", str(project.parent))
    result = run("check", "-c", str(project / "terradoc.yaml"), "--format", "github")
    line = next(l for l in result.output.splitlines() if l.startswith("::error"))
    assert line.startswith("::error file=demo/data/videos.yaml,line=1,title=terradoc consent::")


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



def test_about_credits_only_with_locale_key(project):
    cfg = str(project / "terradoc.yaml")
    assert run("build", "-c", cfg, "--out", "s1").exit_code == 0
    assert "about_credits" not in (Path("s1") / "pt" / "about.html").read_text()
    with open(project / "locales" / "pt.yaml", "a", encoding="utf-8") as f:
        f.write('\nabout_credits: "<p>Fotos: Fulano</p>"\n')
    assert run("build", "-c", cfg, "--out", "s2").exit_code == 0
    assert "Fotos: Fulano" in (Path("s2") / "pt" / "about.html").read_text()


# ── 0.12.1: column counts, photo credits, 404 links ─────────────────────

@pytest.mark.parametrize("row,cells", [("2\tko\tmoon\textra", 4), ("2\tko", 2)])
def test_tsv_wrong_column_count_names_the_line(project, row, cells):
    (project / "data" / "dictionary.tsv").write_text(f"id\tentry\tdefinition\n1\tka\tsun\n{row}\n")
    result = run("check", "-c", str(project / "terradoc.yaml"), "--format", "github")
    assert result.exit_code == 1
    assert "::error file=data/dictionary.tsv,line=3," in result.output, result.output
    assert f"{cells} column(s), but the header has 3" in result.output


PLANT = """- id: 1
  name_indigenous: Nanai
  pic_link: {link}
{extra}"""


def write_plants(project: Path, link="images/p.jpg", extra=""):
    enable(project, "ethnobotany")
    (project / "static" / "images" / "p.jpg").write_bytes(b"x")
    (project / "data" / "ethnobotany.yaml").write_text(PLANT.format(link=link, extra=extra))


def test_photo_credit_rendered_with_safe_link(project):
    write_plants(project, link="https://static.inaturalist.org/photos/1/medium.jpg",
                 extra="  pic_credit: \"© Ana, CC BY-NC, via iNaturalist\"\n"
                       "  pic_source: https://www.inaturalist.org/observations/1\n")
    result = run("build", "-c", str(project / "terradoc.yaml"), "--out", "site")
    assert result.exit_code == 0, result.output
    (page,) = [p.read_text() for p in (Path("site") / "pt" / "ethnobotany").glob("*.html")]
    assert '<a href="https://www.inaturalist.org/observations/1" rel="noopener">© Ana, CC BY-NC, via iNaturalist</a>' in page
    assert 'href="https://static.inaturalist.org/photos/1/medium.jpg"' in page
    assert 'src="https://' not in page  # another site's picture is a link, never loaded


@pytest.mark.parametrize("link,extra,message", [
    ("data:image/png;base64,AAAA", "", "only a file or an http(s) address"),
    ("images/p.jpg", "  pic_credit: x\n  pic_source: \"javascript:alert(1)\"\n",
     "must be an http(s) address"),
])
def test_photo_fields_checked(project, link, extra, message):
    write_plants(project, link=link, extra=extra)
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert result.exit_code == 1
    assert message in result.output, result.output


def test_404_links_are_root_relative(project):
    result = run("build", "-c", str(project / "terradoc.yaml"), "--out", "site")
    assert result.exit_code == 0, result.output
    page = (Path("site") / "404.html").read_text()
    assert "<style>" in page and 'rel="stylesheet"' not in page  # CSS inline: works at any depth
    assert 'href="/pt/about.html"' in page
    assert 'href="about.html"' not in page
