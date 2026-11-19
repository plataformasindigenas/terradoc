"""Tests for terradoc CLI."""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from terradoc.cli import main
from terradoc.config import TerradocConfig


def test_cli_help():
    """CLI shows help text."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Terradoc" in result.output


def test_cli_build_help_has_no_output_override():
    """build help no longer exposes the removed output override."""
    runner = CliRunner()
    result = runner.invoke(main, ["build", "--help"])
    assert result.exit_code == 0
    assert "--output" not in result.output


def test_cli_build_missing_config():
    """build command fails when config file is missing."""
    runner = CliRunner()
    result = runner.invoke(main, ["build", "-c", "/nonexistent/terradoc.yaml"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_cli_init():
    """init command scaffolds a new project."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        with runner.isolated_filesystem(temp_dir=tmp):
            result = runner.invoke(main, ["init", "test-project"])
            assert result.exit_code == 0

            project_dir = Path("test-project")
            assert project_dir.exists()
            assert (project_dir / "data").exists()
            assert (project_dir / "data" / "encyclopedia").exists()
            # templates and pages are bundled (v2): no config/ unless --eject-templates
            assert not (project_dir / "config").exists()
            assert (project_dir / "locales").exists()
            assert (project_dir / "static" / "images" / "favicon.svg").exists()
            assert (project_dir / "terradoc.yaml").exists()
            assert (project_dir / "locales" / "pt.yaml").exists()
            assert (project_dir / "locales" / "en.yaml").exists()


def test_cli_init_eject_templates():
    """--eject-templates copies the bundled templates for local editing."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        with runner.isolated_filesystem(temp_dir=tmp):
            result = runner.invoke(main, ["init", "p", "--eject-templates"])
            assert result.exit_code == 0
            assert (Path("p") / "config" / "templates" / "v2" / "base.html.j2").exists()
            assert (Path("p") / "config" / "templates" / "v2" / "pages" / "home.html.j2").exists()
            assert not list((Path("p") / "config" / "templates" / "v2").rglob("__init__.py"))


def test_cli_init_existing_dir():
    """init command fails when directory exists."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        with runner.isolated_filesystem(temp_dir=tmp):
            Path("existing").mkdir()
            result = runner.invoke(main, ["init", "existing"])
            assert result.exit_code != 0
            assert "already exists" in result.output


def test_cli_init_then_build_smoke():
    """A fresh scaffold builds into a complete starter site."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        with runner.isolated_filesystem(temp_dir=tmp):
            init_result = runner.invoke(main, ["init", "demo"])
            assert init_result.exit_code == 0

            build_result = runner.invoke(main, ["build", "-c", "demo/terradoc.yaml"])
            assert build_result.exit_code == 0, build_result.output
            assert "0 error(s)" in build_result.output

            project_dir = Path("demo")
            assert (project_dir / "docs" / "index.html").exists()
            assert (project_dir / "docs" / "pt" / "index.html").exists()
            assert (project_dir / "docs" / "en" / "index.html").exists()
            assert (project_dir / "docs" / "pt" / "dictionary" / "index.html").exists()
            assert (project_dir / "docs" / "pt" / "encyclopedia.html").exists()
            assert (project_dir / "docs" / "sw.js").exists()
            assert not list((project_dir / "docs").glob("*-data.json"))


def test_cli_v1_is_refused_with_the_release_that_removed_it():
    """A site still asking for v1 gets a clear message, not a traceback."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        with runner.isolated_filesystem(temp_dir=tmp):
            assert runner.invoke(main, ["init", "demo"]).exit_code == 0
            result = runner.invoke(main, ["build", "-c", "demo/terradoc.yaml", "--templates", "v1"])
            assert result.exit_code != 0
            assert "v1 was removed in terradoc 0.23.0" in result.output


def test_cli_v1_leftovers_are_check_errors():
    """v1 theme keys, page configs and patterns are named as v1 leftovers to delete."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        with runner.isolated_filesystem(temp_dir=tmp):
            assert runner.invoke(main, ["init", "demo"]).exit_code == 0
            cfg = Path("demo/terradoc.yaml")
            cfg.write_text(cfg.read_text().replace("  pack: weave\n", "  pack: weave\n  hero_background: weave\n"))
            (Path("demo/config/templates/motifs/x")).mkdir(parents=True)
            Path("demo/config/dictionary.yaml").write_text("input: x\n")
            result = runner.invoke(main, ["check", "-c", "demo/terradoc.yaml"])
            assert result.exit_code == 1
            assert "theme.hero_background: a setting of the v1 templates, removed in terradoc 0.23.0" in result.output
            assert "config/ has v1 page configs (dictionary.yaml)" in result.output
            assert "config/templates/motifs/ holds v1 patterns" in result.output


def test_cli_categories_no_encyclopedia():
    """categories command fails when no encyclopedia dir exists."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        with runner.isolated_filesystem(temp_dir=tmp):
            result = runner.invoke(main, ["categories"])
            assert result.exit_code != 0
            assert "No encyclopedia directory" in result.output


def test_cli_categories_dumps_paths():
    """categories command outputs sorted unique category paths."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        with runner.isolated_filesystem(temp_dir=tmp):
            data_dir = Path("data")
            data_dir.mkdir()
            enc_dir = data_dir / "encyclopedia"
            enc_dir.mkdir()

            (enc_dir / "entry-a.md").write_text("""---
id: entry-a
title: Entry A
categories:
  - nature/fauna
  - society
---
Body A.
""", encoding="utf-8")
            (enc_dir / "entry-b.md").write_text("""---
id: entry-b
title: Entry B
categories:
  - society
  - nature/flora
---
Body B.
""", encoding="utf-8")

            result = runner.invoke(main, ["categories"])
            assert result.exit_code == 0
            assert "nature/fauna" in result.output
            assert "nature/flora" in result.output
            assert "society" in result.output


def test_cli_categories_writes_file():
    """categories --output writes to a file."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        with runner.isolated_filesystem(temp_dir=tmp):
            data_dir = Path("data")
            data_dir.mkdir()
            enc_dir = data_dir / "encyclopedia"
            enc_dir.mkdir()

            (enc_dir / "entry-a.md").write_text("""---
id: entry-a
title: Entry A
categories:
  - nature
---
Body.
""", encoding="utf-8")

            result = runner.invoke(main, ["categories", "-o", "data/categories.yaml"])
            assert result.exit_code == 0

            out = Path("data/categories.yaml")
            assert out.exists()
            content = out.read_text()
            assert "nature" in content


def test_resolve_schema_local():
    """resolve_schema prefers local schema files."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "data").mkdir()
        schema_file = tmp_path / "data" / "dictionary_schema.yaml"
        schema_file.write_text("fields: []\n")

        config = TerradocConfig(base_dir=tmp_path)
        result = config.resolve_schema("dictionary")
        assert result == schema_file


def test_resolve_schema_fallback_package():
    """resolve_schema falls back to package schemas."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "data").mkdir()

        config = TerradocConfig(base_dir=tmp_path)
        result = config.resolve_schema("dictionary")
        assert "terradoc" in str(result)
        assert "schemas" in str(result)
