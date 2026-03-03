"""Tests for terradoc CLI."""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from terradoc.cli import main, resolve_schema
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
            assert (project_dir / "config").exists()
            assert (project_dir / "config" / "templates").exists()
            assert (project_dir / "config" / "index.yaml").exists()
            assert (project_dir / "config" / "dictionary.yaml").exists()
            assert (project_dir / "config" / "fauna.yaml").exists()
            assert (project_dir / "config" / "encyclopedia.yaml").exists()
            assert (project_dir / "config" / "bibliography.yaml").exists()
            assert (project_dir / "config" / "templates" / "base.html.j2").exists()
            assert (project_dir / "locales").exists()
            assert (project_dir / "docs").exists()
            assert (project_dir / "terradoc.yaml").exists()
            assert (project_dir / "locales" / "pt.yaml").exists()
            assert (project_dir / "locales" / "en.yaml").exists()


def test_cli_init_existing_dir():
    """init command fails when directory exists."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        with runner.isolated_filesystem(temp_dir=tmp):
            Path("existing").mkdir()
            result = runner.invoke(main, ["init", "existing"])
            assert result.exit_code != 0
            assert "already exists" in result.output


def test_resolve_schema_local():
    """resolve_schema prefers local schema files."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "data").mkdir()
        schema_file = tmp_path / "data" / "dictionary_schema.yaml"
        schema_file.write_text("fields: []\n")

        config = TerradocConfig(base_dir=tmp_path)
        result = resolve_schema("dictionary", config)
        assert result == schema_file


def test_resolve_schema_fallback_package():
    """resolve_schema falls back to package schemas."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "data").mkdir()

        config = TerradocConfig(base_dir=tmp_path)
        result = resolve_schema("dictionary", config)
        assert "terradoc" in str(result)
        assert "schemas" in str(result)
