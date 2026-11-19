"""Tests for terradoc configuration."""

import tempfile
from pathlib import Path

import pytest
import yaml

from terradoc.config import ModuleConfig, TerradocConfig, ThemeConfig, load_config


def test_default_config():
    """Default config has sensible defaults."""
    cfg = TerradocConfig()
    assert cfg.project_name == "Terradoc Project"
    assert cfg.locales == ["pt", "en"]
    assert cfg.default_locale == "pt"
    assert cfg.site_context()["title"] == "Terradoc Project"
    assert cfg.is_module_enabled("dictionary") is True
    assert cfg.is_module_enabled("fauna") is True
    assert cfg.is_module_enabled("videos") is True
    assert cfg.is_module_enabled("nonexistent") is False


def test_enabled_modules():
    """enabled_modules() returns only enabled modules."""
    cfg = TerradocConfig()
    modules = cfg.enabled_modules()
    slugs = [m["slug"] for m in modules]
    assert "dictionary" in slugs
    assert "encyclopedia" in slugs
    assert "fauna" in slugs
    assert "ethnobotany" in slugs
    assert "bibliography" in slugs
    assert "recordings" in slugs
    assert "corpus" in slugs
    assert "videos" in slugs


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
            "favicon": "images/custom-favicon.svg",
            "hero_image": "images/home.jpg",
            "palette": {"primary": {"color": "#8A3B12", "material": "urucum"}},
            "pack": "none",
            "hero_people": "no",
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
        assert cfg.theme.palette == {"primary": {"color": "#8A3B12", "material": "urucum"}}
        assert cfg.theme.favicon == "images/custom-favicon.svg"
        assert cfg.theme.pack == "none" and cfg.theme.hero_people is False
        assert cfg.theme.templates == "v2" and cfg.unknown_theme_keys == []
        assert cfg.theme.media() == {"hero_image": "images/home.jpg", "favicon": "images/custom-favicon.svg"}
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
        assert cfg.module_labels["videos"] == "Videos"
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


def test_load_config_rejects_non_mapping_top_level():
    """Malformed top-level YAML should raise a clear error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("- not-a-mapping\n")
        tmp_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="expected a YAML mapping at top level"):
            load_config(tmp_path)
    finally:
        tmp_path.unlink()


def test_load_config_rejects_non_mapping_theme():
    """theme must be a mapping/object."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"theme": ["invalid"]}, f)
        tmp_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="Invalid 'theme'"):
            load_config(tmp_path)
    finally:
        tmp_path.unlink()


# ── Layer 2: module_intensity, term_color, term_weight ──


def test_bundled_template_dir():
    """bundled_template_dir returns a valid Path containing base.html.j2."""
    cfg = TerradocConfig()
    bundled = cfg.bundled_template_dir
    assert (bundled / "base.html.j2").exists()


def test_theme_media_lists_only_what_is_set():
    assert ThemeConfig(favicon="").media() == {}
    assert ThemeConfig().media() == {"favicon": "images/favicon.svg"}


def test_v1_theme_keys_are_kept_as_unknown_for_check():
    """load_config does not fail on v1 keys; `check` names them (0.23.0)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"theme": {"colors": {"primary": "#FF0000"}, "hero_background": "weave"}}, f)
        tmp_path = Path(f.name)
    try:
        cfg = load_config(tmp_path)
        assert cfg.unknown_theme_keys == ["colors", "hero_background"]
    finally:
        tmp_path.unlink()
