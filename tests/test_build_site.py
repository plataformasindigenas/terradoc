"""Tests for terradoc site builder."""

import tempfile
from pathlib import Path

from terradoc.build_site import build_language_picker
from terradoc.config import TerradocConfig, ThemeColors, ThemeConfig


def test_build_language_picker():
    """Language picker HTML is generated correctly."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        config = TerradocConfig(
            project_name="Test Project",
            project_subtitle="Test Subtitle",
            locales=["pt", "en"],
            locale_labels={"pt": "Português", "en": "English"},
            base_dir=tmp_path,
        )

        build_language_picker(config)

        index_html = (docs_dir / "index.html").read_text()
        assert "Test Project" in index_html
        assert "Test Subtitle" in index_html
        assert 'src="images/logo.svg"' in index_html
        assert 'rel="icon" href="images/favicon.svg"' in index_html
        assert 'href="pt/index.html"' in index_html
        assert 'href="en/index.html"' in index_html
        assert "Português" in index_html
        assert "English" in index_html


def test_build_language_picker_custom_theme():
    """Language picker uses custom theme colors."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        config = TerradocConfig(
            project_name="Custom",
            locales=["pt"],
            base_dir=tmp_path,
            theme=ThemeConfig(colors=ThemeColors(
                primary="#FF0000",
                accent="#00FF00",
                bg="#0000FF",
            )),
        )

        build_language_picker(config)

        index_html = (docs_dir / "index.html").read_text()
        assert "#FF0000" in index_html
        assert "#00FF00" in index_html
        assert "#0000FF" in index_html


def test_build_language_picker_custom_assets():
    """Language picker uses configured logo and favicon."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        config = TerradocConfig(
            project_name="Assets",
            locales=["en"],
            base_dir=tmp_path,
            theme=ThemeConfig(
                colors=ThemeColors(),
                logo="images/custom-logo.svg",
                favicon="images/custom-favicon.svg",
            ),
        )

        build_language_picker(config)

        index_html = (docs_dir / "index.html").read_text()
        assert 'src="images/custom-logo.svg"' in index_html
        assert 'rel="icon" href="images/custom-favicon.svg"' in index_html


def test_build_language_picker_single_locale():
    """Language picker works with single locale."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        config = TerradocConfig(
            project_name="Single",
            locales=["en"],
            locale_labels={"en": "English"},
            base_dir=tmp_path,
        )

        build_language_picker(config)

        index_html = (docs_dir / "index.html").read_text()
        assert 'href="en/index.html"' in index_html
        assert "pt/index.html" not in index_html


def test_build_language_picker_custom_locale_labels():
    """Language picker uses labels from the project config."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        config = TerradocConfig(
            project_name="Labels",
            locales=["bor", "en"],
            locale_labels={"bor": "Bororo", "en": "English"},
            base_dir=tmp_path,
        )

        build_language_picker(config)

        index_html = (docs_dir / "index.html").read_text()
        assert "Bororo" in index_html
        assert "English" in index_html


def test_theme_dict_includes_style_terra():
    """Theme to_dict includes terra style by default."""
    config = TerradocConfig()
    theme_dict = config.theme.to_dict()
    assert theme_dict["style"] == "terra"


def test_theme_dict_includes_style_classic():
    """Theme to_dict includes classic style when configured."""
    config = TerradocConfig(
        theme=ThemeConfig(style="classic"),
    )
    theme_dict = config.theme.to_dict()
    assert theme_dict["style"] == "classic"


def test_base_template_has_body_class():
    """base.html.j2 template includes td-style body class placeholder."""
    import importlib.resources
    base_template = importlib.resources.files("terradoc.templates") / "base.html.j2"
    content = base_template.read_text()
    assert 'class="td-style-{{ theme.style' in content


def test_base_template_has_fonts_css_link():
    """base.html.j2 template links to fonts.css."""
    import importlib.resources
    base_template = importlib.resources.files("terradoc.templates") / "base.html.j2"
    content = base_template.read_text()
    assert "fonts.css" in content
