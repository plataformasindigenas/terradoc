"""Tests for terradoc configuration."""

import tempfile
from pathlib import Path

import yaml

from terradoc.config import ModuleConfig, TerradocConfig, ThemeColors, ThemeConfig, load_config


def test_default_config():
    """Default config has sensible defaults."""
    cfg = TerradocConfig()
    assert cfg.project_name == "Terradoc Project"
    assert cfg.locales == ["pt", "en"]
    assert cfg.default_locale == "pt"
    assert cfg.site_context()["title"] == "Terradoc Project"
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
        "site_title": "Platform Title",
        "site_tagline": "Platform Tagline",
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
        "module_labels": {
            "dictionary": "Lexicon",
            "encyclopedia": "Knowledge Base",
        },
        "theme": {
            "logo": "images/custom-logo.svg",
            "favicon": "images/custom-favicon.svg",
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
        assert cfg.site_title == "Platform Title"
        assert cfg.site_tagline == "Platform Tagline"
        assert cfg.culture_name == "TestCulture"
        assert cfg.meta_prefix == "test"
        assert cfg.locales == ["en"]
        assert cfg.locale_labels["en"] == "English"
        # Default "pt" is still present because labels merge with defaults
        assert "pt" in cfg.locale_labels
        assert cfg.module_labels["dictionary"] == "Lexicon"
        assert cfg.default_locale == "en"
        assert cfg.featured_article_id == "main"
        assert cfg.bib_file == "test.bib"
        assert cfg.is_module_enabled("dictionary") is True
        assert cfg.is_module_enabled("fauna") is False
        assert cfg.theme.colors.primary == "#FF0000"
        assert cfg.theme.colors.accent == "#00FF00"
        assert cfg.theme.logo == "images/custom-logo.svg"
        assert cfg.theme.favicon == "images/custom-favicon.svg"
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


def test_theme_config_to_dict_includes_assets():
    """ThemeConfig.to_dict includes color values and asset paths."""
    theme = ThemeConfig()
    d = theme.to_dict()
    assert d["logo"] == "images/logo.svg"
    assert d["favicon"] == "images/favicon.svg"


def test_module_label_fallback():
    """Unknown module labels fall back to title-cased slugs."""
    cfg = TerradocConfig()
    assert cfg.module_label("audio_archive") == "Audio Archive"


def test_load_config_merges_labels_with_defaults():
    """Setting one label in YAML preserves the other defaults."""
    config_data = {
        "module_labels": {"dictionary": "Lexicon"},
        "locale_labels": {"pt": "Brazilian Portuguese"},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        tmp_path = Path(f.name)

    try:
        cfg = load_config(tmp_path)
        # Overridden key
        assert cfg.module_labels["dictionary"] == "Lexicon"
        # Default keys still present
        assert cfg.module_labels["encyclopedia"] == "Encyclopedia"
        assert cfg.module_labels["fauna"] == "Fauna"
        # Overridden locale label
        assert cfg.locale_labels["pt"] == "Brazilian Portuguese"
        # Default locale label still present
        assert cfg.locale_labels["en"] == "English"
    finally:
        tmp_path.unlink()


def test_site_context_includes_custom_module_label():
    """site_context() includes labels for custom modules."""
    cfg = TerradocConfig()
    cfg.modules["recipes"] = ModuleConfig()
    cfg.module_labels["recipes"] = "Recipes"
    ctx = cfg.site_context()
    assert ctx["recipes_label"] == "Recipes"
    # Built-in modules still present
    assert ctx["dictionary_label"] == "Dictionary"
