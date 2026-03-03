"""Tests for terradoc configuration."""

import tempfile
from pathlib import Path

import yaml

from terradoc.config import TerradocConfig, ThemeColors, load_config


def test_default_config():
    """Default config has sensible defaults."""
    cfg = TerradocConfig()
    assert cfg.project_name == "Terradoc Project"
    assert cfg.locales == ["pt", "en"]
    assert cfg.default_locale == "pt"
    assert cfg.is_module_enabled("dictionary") is True
    assert cfg.is_module_enabled("fauna") is True
    assert cfg.is_module_enabled("nonexistent") is False


def test_enabled_modules():
    """enabled_modules() returns only enabled modules."""
    cfg = TerradocConfig()
    modules = cfg.enabled_modules()
    slugs = [m["slug"] for m in modules]
    assert "dictionary" in slugs
    assert "encyclopedia" in slugs
    assert "fauna" in slugs
    assert "bibliography" in slugs


def test_theme_colors_defaults():
    """Theme colors have correct defaults."""
    colors = ThemeColors()
    assert colors.primary == "#3D352F"
    assert colors.accent == "#C75B39"
    assert colors.bg == "#F9F6F2"


def test_load_config_from_yaml():
    """load_config reads YAML correctly."""
    config_data = {
        "project_name": "Test Project",
        "culture_name": "TestCulture",
        "meta_prefix": "test",
        "locales": ["en"],
        "locale_labels": {"en": "English"},
        "default_locale": "en",
        "featured_article_id": "main",
        "bib_file": "test.bib",
        "modules": {
            "dictionary": {"enabled": True},
            "fauna": {"enabled": False},
        },
        "theme": {
            "colors": {
                "primary": "#FF0000",
                "accent": "#00FF00",
            },
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        tmp_path = Path(f.name)

    try:
        cfg = load_config(tmp_path)
        assert cfg.project_name == "Test Project"
        assert cfg.culture_name == "TestCulture"
        assert cfg.meta_prefix == "test"
        assert cfg.locales == ["en"]
        assert cfg.locale_labels == {"en": "English"}
        assert cfg.default_locale == "en"
        assert cfg.featured_article_id == "main"
        assert cfg.bib_file == "test.bib"
        assert cfg.is_module_enabled("dictionary") is True
        assert cfg.is_module_enabled("fauna") is False
        assert cfg.theme.colors.primary == "#FF0000"
        assert cfg.theme.colors.accent == "#00FF00"
        # Unset colors keep defaults
        assert cfg.theme.colors.bg == "#F9F6F2"
    finally:
        tmp_path.unlink()


def test_load_config_missing_file():
    """load_config returns defaults when file doesn't exist."""
    cfg = load_config(Path("/nonexistent/path.yaml"))
    assert cfg.project_name == "Terradoc Project"


def test_load_config_none():
    """load_config returns defaults when path is None."""
    cfg = load_config(None)
    assert cfg.project_name == "Terradoc Project"


def test_theme_to_dict():
    """ThemeColors.to_dict returns all color values."""
    colors = ThemeColors()
    d = colors.to_dict()
    assert len(d) == 12
    assert d["primary"] == "#3D352F"
    assert d["accent"] == "#C75B39"
