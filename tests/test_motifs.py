"""Motif packs and per-file template overrides (0.13.0).

A site's culture assets live in the site repo (config/templates/motifs/<name>/);
terradoc ships only the neutral `weave` pack, and an unknown pack name is an
error rather than a silent fallback to another people's motif.
"""

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from terradoc.cli import main

PARTS = ("background.html.j2", "motif.html.j2", "divider.html.j2", "badge.html.j2", "grain.css.j2")


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


def set_theme(project: Path, **values):
    cfg = project / "terradoc.yaml"
    data = yaml.safe_load(cfg.read_text())
    data.setdefault("theme", {}).update(values)
    cfg.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def add_pack(project: Path, name: str, marker: str):
    d = project / "config" / "templates" / "motifs" / name
    d.mkdir(parents=True)
    for part in PARTS:
        if part.endswith(".css.j2"):
            (d / part).write_text(f".td-style-terra::before {{ content: '{marker}-{part}'; }}\n")
        else:
            (d / part).write_text(f'<i class="{marker}-{part}"></i>\n')


def build(project: Path):
    return run("build", "-c", str(project / "terradoc.yaml"), "--out", "site", "--bundle-dir", "bundle")


def test_default_is_the_neutral_pack(project):
    result = build(project)
    assert result.exit_code == 0, result.output
    html = (Path("site") / "pt" / "index.html").read_text()
    assert "Tugarege" not in html  # the Bororo moiety badge is no longer anyone's default
    assert "concentric circles" not in html  # comments never reach the page


def test_bundled_packs_are_neutral_only():
    import importlib.resources
    motifs = importlib.resources.files("terradoc.templates") / "motifs"
    assert sorted(p.name for p in motifs.iterdir() if p.is_dir() and not p.name.startswith("_")) == ["weave"]


@pytest.mark.parametrize("key", ["hero_background", "hero_motif", "hero_divider", "page_badge", "grain_pattern"])
def test_unknown_pack_is_a_check_error(project, key):
    set_theme(project, **{key: "moiety"})
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert result.exit_code == 1
    assert f"theme.{key}: motif pack 'moiety'" in result.output


def test_unknown_pack_blocks_build(project):
    set_theme(project, page_badge="nonesuch")
    result = build(project)
    assert result.exit_code != 0
    assert not (Path("site") / "pt" / "index.html").exists()


def test_pack_name_cannot_escape(project):
    set_theme(project, hero_motif="../../etc")
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert result.exit_code == 1
    assert "is not a motif pack name" in result.output


def test_none_and_dots_need_no_pack(project):
    set_theme(project, hero_background="none", hero_motif="none", hero_divider="none",
              page_badge="none", grain_pattern="dots")
    result = build(project)
    assert result.exit_code == 0, result.output


def test_site_pack_is_used_everywhere(project):
    add_pack(project, "local", "LOCALPACK")
    set_theme(project, hero_background="local", hero_motif="local", hero_divider="local",
              page_badge="local", grain_pattern="local",
              hero_images=["images/logo.svg"])  # the frame motif only appears with hero photos
    result = build(project)
    assert result.exit_code == 0, result.output
    index = (Path("site") / "pt" / "index.html").read_text()
    for part in PARTS:
        if part != "badge.html.j2":  # the badge sits on section pages, not the home page
            assert f"LOCALPACK-{part}" in index, part
    assert "LOCALPACK-badge.html.j2" in (Path("site") / "pt" / "dictionary.html").read_text()


def test_one_override_keeps_the_rest_bundled(project):
    """A site may replace one partial without copying every template (was a hard failure)."""
    d = project / "config" / "templates" / "motifs" / "weave"
    d.mkdir(parents=True)
    (d / "badge.html.j2").write_text('<i class="SITE-BADGE"></i>\n')
    result = build(project)
    assert result.exit_code == 0, result.output
    html = (Path("site") / "pt" / "dictionary.html").read_text()
    assert "SITE-BADGE" in html
    assert (Path("site") / "pt" / "index.html").exists()  # the rest still renders from terradoc's templates


def test_site_page_template_overrides_bundled_one(project):
    d = project / "config" / "templates"
    d.mkdir(parents=True)
    (d / "about.html.j2").write_text('{% extends "base.html.j2" %}{% block content %}SITE-ABOUT{% endblock %}')
    result = build(project)
    assert result.exit_code == 0, result.output
    assert "SITE-ABOUT" in (Path("site") / "pt" / "about.html").read_text()


def test_unknown_theme_key_is_an_error(project):
    set_theme(project, hero_backgroud="weave")  # misspelt
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert result.exit_code != 0
    assert "theme.hero_backgroud: unknown setting (did you mean 'hero_background'?)" in result.output
    assert build(project).exit_code != 0


def test_template_set_v1_is_the_default_and_explicit_v1_is_identical(project):
    assert build(project).exit_code == 0
    first = (Path("site") / "pt" / "index.html").read_bytes()
    result = run("build", "-c", str(project / "terradoc.yaml"), "--out", "site2",
                 "--bundle-dir", "bundle2", "--templates", "v1")
    assert result.exit_code == 0, result.output
    assert (Path("site2") / "pt" / "index.html").read_bytes() == first


def test_unavailable_template_set_is_refused(project):
    result = run("render", "-c", str(project / "terradoc.yaml"), "--out", "site", "--templates", "v9")
    assert result.exit_code != 0
    assert "template set 'v9' is not available" in result.output
    set_theme(project, templates="v9")
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert result.exit_code != 0
    assert "'v9' is not available" in result.output
