"""Tests for terradoc configuration."""

import tempfile
from pathlib import Path

import pytest
import yaml

from terradoc.config import THEME_PRESETS, ModuleConfig, TerradocConfig, ThemeColors, ThemeConfig, load_config


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


def test_theme_colors_defaults():
    """Theme colors have correct defaults (terra palette)."""
    colors = ThemeColors()
    assert colors.primary == "#C81F2D"
    assert colors.accent == "#D4A03A"
    assert colors.bg == "#F4F1EA"


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
        # Unset colors use preset defaults (terra by default)
        assert cfg.theme.colors.bg == "#F4F1EA"
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
    assert len(d) == 20
    assert d["primary"] == "#C81F2D"
    assert d["accent"] == "#D4A03A"


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


def test_theme_presets_exist():
    """THEME_PRESETS contains terra and classic."""
    assert "terra" in THEME_PRESETS
    assert "classic" in THEME_PRESETS
    for name, preset in THEME_PRESETS.items():
        assert "style" in preset
        assert "colors" in preset
        assert "description" in preset


def test_default_theme_is_terra():
    """Default ThemeConfig uses terra style."""
    theme = ThemeConfig()
    assert theme.style == "terra"
    assert theme.border_radius == "28px"
    assert "'Sora'" in theme.font_family_headings
    assert "'Inter'" in theme.font_family


def test_preset_loading_terra():
    """Loading config without preset defaults to terra."""
    config_data = {
        "project_name": "Terra Test",
        "theme": {
            "colors": {
                "primary": "#FF0000",
            },
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        tmp_path = Path(f.name)

    try:
        cfg = load_config(tmp_path)
        # Overridden color
        assert cfg.theme.colors.primary == "#FF0000"
        # Other colors come from terra preset
        assert cfg.theme.colors.accent == "#D4A03A"
        assert cfg.theme.style == "terra"
        assert cfg.theme.border_radius == "28px"
    finally:
        tmp_path.unlink()


def test_preset_loading_classic():
    """Loading config with preset: classic uses classic values."""
    config_data = {
        "project_name": "Classic Test",
        "theme": {
            "preset": "classic",
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        tmp_path = Path(f.name)

    try:
        cfg = load_config(tmp_path)
        assert cfg.theme.style == "classic"
        assert cfg.theme.colors.primary == "#3D352F"
        assert cfg.theme.colors.accent == "#B7522C"
        assert cfg.theme.border_radius == "4px"
    finally:
        tmp_path.unlink()


def test_preset_with_color_override():
    """YAML color overrides merge on top of preset."""
    config_data = {
        "theme": {
            "preset": "classic",
            "colors": {
                "accent": "#CUSTOM",
            },
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        tmp_path = Path(f.name)

    try:
        cfg = load_config(tmp_path)
        assert cfg.theme.colors.accent == "#CUSTOM"
        # Other classic colors preserved
        assert cfg.theme.colors.primary == "#3D352F"
        assert cfg.theme.style == "classic"
    finally:
        tmp_path.unlink()


def test_theme_config_to_dict_includes_style():
    """ThemeConfig.to_dict includes style field."""
    theme = ThemeConfig()
    d = theme.to_dict()
    assert d["style"] == "terra"
    assert "colors" in d


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


def test_load_config_rejects_non_mapping_theme_colors():
    """theme.colors must be a mapping/object."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"theme": {"colors": ["invalid"]}}, f)
        tmp_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="Invalid 'theme.colors'"):
            load_config(tmp_path)
    finally:
        tmp_path.unlink()


def test_load_config_rejects_non_mapping_theme_colors_dark():
    """theme.colors_dark must be a mapping/object."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"theme": {"colors_dark": ["invalid"]}}, f)
        tmp_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="Invalid 'theme.colors_dark'"):
            load_config(tmp_path)
    finally:
        tmp_path.unlink()


# ── Layer 2: module_intensity, term_color, term_weight ──


def test_module_intensity_default():
    """Default module_intensity is empty dict, get() returns 'balanced'."""
    cfg = TerradocConfig()
    assert cfg.theme.module_intensity == {}
    assert cfg.theme.module_intensity.get("dictionary", "balanced") == "balanced"


def test_module_intensity_from_yaml():
    """module_intensity values load from YAML."""
    config_data = {
        "theme": {
            "module_intensity": {
                "dictionary": "minimal",
                "fauna": "rich",
            },
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        tmp_path = Path(f.name)

    try:
        cfg = load_config(tmp_path)
        assert cfg.theme.module_intensity["dictionary"] == "minimal"
        assert cfg.theme.module_intensity["fauna"] == "rich"
        assert cfg.theme.module_intensity.get("encyclopedia", "balanced") == "balanced"
    finally:
        tmp_path.unlink()


def test_term_color_default():
    """Default term_color is empty string."""
    cfg = TerradocConfig()
    assert cfg.theme.term_color == ""


def test_term_weight_default():
    """Default term_weight is '600'."""
    cfg = TerradocConfig()
    assert cfg.theme.term_weight == "600"


def test_to_dict_includes_layer2_fields():
    """to_dict() includes module_intensity, term_color, term_weight."""
    theme = ThemeConfig(
        module_intensity={"dictionary": "minimal"},
        term_color="#8B2500",
        term_weight="700",
    )
    d = theme.to_dict()
    assert d["module_intensity"] == {"dictionary": "minimal"}
    assert d["term_color"] == "#8B2500"
    assert d["term_weight"] == "700"


def test_bundled_template_dir():
    """bundled_template_dir returns a valid Path containing base.html.j2."""
    cfg = TerradocConfig()
    bundled = cfg.bundled_template_dir
    assert (bundled / "base.html.j2").exists()
