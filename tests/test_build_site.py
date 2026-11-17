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


def test_language_root_redirects():
    """The root page redirects by browser language, defaulting to default_locale."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "docs").mkdir()
        config = TerradocConfig(
            project_name="T", locales=["pt", "en", "bor"], default_locale="pt", base_dir=tmp_path,
        )
        build_language_picker(config)
        html = (tmp_path / "docs" / "index.html").read_text()
        assert '["pt", "en", "bor"]' in html
        assert "navigator.languages" in html
        assert "location.replace" in html
        assert "localStorage.getItem('td-locale')" in html
        assert '(pick || "pt")' in html
        assert 'content="0; url=pt/index.html"' in html


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
            locales=["pt", "en"],
            locale_labels={"pt": "Português", "en": "English"},
            base_dir=tmp_path,
        )

        build_language_picker(config)

        index_html = (docs_dir / "index.html").read_text()
        assert "Português" in index_html
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


def test_language_picker_loads_fonts_css_and_style_class():
    """language picker keeps standalone layout but includes theme font/style hooks."""
    import importlib.resources
    template = importlib.resources.files("terradoc.templates") / "language_picker.html.j2"
    content = template.read_text()
    assert "css/fonts.css" in content
    assert 'class="td-style-{{ theme.style' in content


# ── Layer 2: decorative macros and CSS ──


def test_decor_template_exists():
    """decor.html.j2 exists in bundled templates."""
    import importlib.resources
    decor = importlib.resources.files("terradoc.templates") / "decor.html.j2"
    assert decor.is_file()


def test_terradoc_css_has_td_term():
    """.td-term class exists in terradoc.css."""
    import importlib.resources
    css = importlib.resources.files("terradoc.static.css") / "terradoc.css"
    content = css.read_text()
    assert ".td-term" in content
    assert "var(--td-term-color)" in content


def test_sitemap_absolute_and_without_error_pages():
    """The sitemap lists absolute URLs of content pages; no 404 or root redirect."""
    from terradoc.build_site import write_robots_txt, write_sitemap

    with tempfile.TemporaryDirectory() as tmp:
        docs = Path(tmp)
        for rel in ("index.html", "404.html", "pt/index.html", "pt/encyclopedia/ãa b.html"):
            (docs / rel).parent.mkdir(parents=True, exist_ok=True)
            (docs / rel).write_text("x")
        config = TerradocConfig(base_url="https://x.terradoc.org/", base_dir=docs)
        write_sitemap(docs, config, ["pt"])
        write_robots_txt(docs, config.base_url)
        sitemap = (docs / "sitemap.xml").read_text()
        assert "<loc>https://x.terradoc.org/pt/index.html</loc>" in sitemap
        assert "<loc>https://x.terradoc.org/pt/encyclopedia/%C3%A3a%20b.html</loc>" in sitemap
        assert "404.html" not in sitemap
        assert "<loc>https://x.terradoc.org/index.html</loc>" not in sitemap
        assert "Sitemap: https://x.terradoc.org/sitemap.xml" in (docs / "robots.txt").read_text()


def test_no_sitemap_without_base_url():
    from terradoc.build_site import write_robots_txt, write_sitemap

    with tempfile.TemporaryDirectory() as tmp:
        docs = Path(tmp)
        (docs / "sitemap.xml").write_text("stale")
        write_sitemap(docs, TerradocConfig(base_dir=docs), ["pt"])
        write_robots_txt(docs)
        assert not (docs / "sitemap.xml").exists()
        assert "Sitemap" not in (docs / "robots.txt").read_text()


def test_number_filter():
    from terradoc._kodudo.rendering import format_number

    assert format_number(4865, "pt") == "4.865"
    assert format_number(4865, "en") == "4,865"
    assert format_number(7.0, "pt") == "7,0"
    assert format_number(7.0, "en-GB") == "7.0"
    assert format_number(461, "bor") == "461"
    assert format_number("n/a", "pt") == "n/a"
