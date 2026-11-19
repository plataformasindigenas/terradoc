"""A site's own Markdown pages (data/pages/, 0.24.0), sites without data modules, aliases,
the project link."""

from pathlib import Path

import yaml

from tests.test_orthography import build, check, project, run  # noqa: F401  (fixture)

MODULES = ["dictionary", "fauna", "ethnobotany", "encyclopedia", "bibliography", "recordings",
           "corpus", "videos"]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def configure(project: Path, **top) -> None:
    cfg = project / "terradoc.yaml"
    data = yaml.safe_load(cfg.read_text())
    data.update(top)
    cfg.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def portal(project: Path) -> None:
    """A site of pages only, in three languages, like the portal."""
    from PIL import Image

    configure(project, locales=["pt", "en", "es"], modules={m: {"enabled": False} for m in MODULES},
              base_url="https://plataformas.example.org/")
    for n in range(2):
        Image.new("RGB", (900, 600), (40 * n, 90, 120)).save(project / "static" / "images" / f"p{n}.jpg")
    for loc, title in (("pt", "Equipe"), ("en", "Team"), ("es", "Equipo")):
        write(project / "data" / "pages" / loc / "equipe.md",
              f"---\ntitle: {title}\nnav: 2\naliases: [{'equipe.html' if loc == 'pt' else loc + '/old-team.html'}]\n---\n"
              "{#quem}\n## Quem somos\n\n"
              '- ![Retrato de A](images/p0.jpg "A. B.")\n  **Ana**, linguística\n'
              "- ![Retrato de B](images/p1.jpg)\n  **Bia**, pedagogia\n\n"
              "Texto com [link](https://example.org/).\n")
        write(project / "data" / "pages" / loc / "contato.md", f"---\ntitle: C-{loc}\nnav: 3\n---\nEscreva.\n")
        write(project / "data" / "pages" / loc / "home.md", f"## Por que agir agora ({loc})\n\nTexto.\n")


def test_site_of_pages_only_builds(project):
    portal(project)
    result = build(project)
    assert result.exit_code == 0, result.output
    site = Path("site")
    for loc in ("pt", "en", "es"):
        assert (site / loc / "equipe.html").is_file() and (site / loc / "contato.html").is_file()
        assert not (site / loc / "about.html").exists()  # no modules, no about texts
        home = (site / loc / "index.html").read_text()
        assert f"Por que agir agora ({loc})" in home
        assert "td-modules" not in home  # no empty module list
        assert "about.html" not in home  # neither in the menu nor in the footer
    assert not (site / "pt" / "dictionary").exists() and not (site / "pt" / "fauna.html").exists()
    es = (site / "es" / "equipe.html").read_text()
    assert '<html lang="es"' in es and "Saltar al contenido" in es
    assert 'href="../pt/equipe.html"' in es and 'href="../en/equipe.html"' in es  # language switch


def test_pages_menu_order_and_current(project):
    portal(project)
    assert build(project).exit_code == 0
    page = (Path("site") / "pt" / "contato.html").read_text()
    nav = page[page.index('class="td-nav td-nav--wide"'):]
    assert nav.index("equipe.html") < nav.index("contato.html")
    assert '<a href="../pt/contato.html" aria-current="page">C-pt</a>' in page


def test_page_pictures_are_webp_with_size_and_credit_and_lists_become_cards(project):
    portal(project)
    assert build(project).exit_code == 0
    page = (Path("site") / "pt" / "equipe.html").read_text()
    assert page.count("<picture>") == 2 and 'type="image/webp"' in page
    assert 'width="900" height="600"' in page and 'alt="Retrato de A"' in page
    assert "Foto: A. B." in page
    assert '<ul class="td-pagecards">' in page
    assert '<h2 id="quem">Quem somos</h2>' in page
    webps = {p.name for p in (Path("site") / "assets" / "img").iterdir()}
    assert webps and all(w.endswith(".webp") for w in webps)  # kept by prune_images
    css = next((Path("site") / "assets").glob("site.*.css")).read_text()
    assert ".td-pagecards" in css


def test_aliases_forward_relatively_and_stay_out_of_the_sitemap(project):
    portal(project)
    assert build(project).exit_code == 0
    site = Path("site")
    old = (site / "equipe.html").read_text()
    assert 'url=pt/equipe.html' in old and 'noindex' in old
    assert '<link rel="canonical" href="https://plataformas.example.org/pt/equipe.html">' in old
    deep = (site / "es" / "old-team.html").read_text()
    assert 'url=../es/equipe.html' in deep and "Esta página cambió de dirección." in deep
    sitemap = (site / "sitemap.xml").read_text()
    assert "pt/equipe.html" in sitemap and "old-team" not in sitemap and "org/equipe.html<" not in sitemap


def test_page_problems_are_check_errors(project):
    portal(project)
    pages = project / "data" / "pages"
    (pages / "es" / "contato.md").unlink()  # missing in one locale
    write(pages / "pt" / "fauna.md", "---\ntitle: X\n---\n")  # a module's name
    write(pages / "pt" / "sem-titulo.md", "---\nnav: 1\n---\nx\n")
    write(pages / "pt" / "foto.md", "---\ntitle: F\nlayout: wide\n---\n![a](images/missing.jpg)\n"
                                    "![b](https://upload.wikimedia.org/x.jpg)\n")
    write(pages / "en" / "dup.md", "---\ntitle: D\naliases: [en/equipe.html, ../x.html]\n---\n")
    result = check(project)
    assert result.exit_code == 1
    out = result.output
    assert "page 'contato' is missing in es" in out
    assert "'fauna' is a name terradoc uses itself" in out
    assert "a page needs a title" in out
    assert "unknown front matter key(s): layout" in out
    assert "missing picture 'images/missing.jpg'" in out
    assert "picture from another site 'https://upload.wikimedia.org/x.jpg'" in out
    assert "alias 'en/equipe.html' is already an address of the site" in out
    assert "no '.' or '..' parts" in out


def test_static_file_at_an_alias_is_an_error(project):
    portal(project)
    write(project / "static" / "equipe.html", "<p>old</p>")
    result = check(project)
    assert result.exit_code == 1
    assert "static/equipe.html" in result.output and "generated by terradoc" in result.output


def test_no_html_and_no_attributes_but_id_from_page_text(project):
    portal(project)
    write(project / "data" / "pages" / "pt" / "contato.md",
          '---\ntitle: C\n---\n{#ok onclick="alert(1)" style="x"}\n## T\n\n<script>alert(1)</script>\n')
    assert build(project).exit_code == 0
    page = (Path("site") / "pt" / "contato.html").read_text()
    assert '<h2 id="ok">T</h2>' in page
    assert "onclick" not in page and "<script>alert" not in page


def test_project_link_is_configurable_and_defaults_to_terradoc_org(project):
    assert build(project).exit_code == 0
    assert 'href="https://terradoc.org/">Plataformas Indígenas</a>' in (Path("site") / "pt" / "index.html").read_text()
    configure(project, project_url="https://plataformas.terradoc.org/")
    assert build(project).exit_code == 0
    assert 'href="https://plataformas.terradoc.org/">Plataformas Indígenas</a>' in (Path("site") / "pt" / "index.html").read_text()


def test_sites_without_pages_keep_their_about_page_and_css(project):
    """The platforms have data modules and no data/pages/: unchanged (about stays)."""
    assert build(project).exit_code == 0
    site = Path("site")
    assert (site / "pt" / "about.html").is_file()
    assert "about.html" in (site / "pt" / "index.html").read_text()
    css = next((site / "assets").glob("site.*.css")).read_text()
    assert ".td-pagecards" not in css


def test_page_text_is_in_the_font_subset(project):
    portal(project)
    write(project / "data" / "pages" / "pt" / "contato.md", "---\ntitle: C\n---\nŋ ɨ\n")
    result = build(project)
    assert result.exit_code == 0, result.output
    from terradoc.build_v2 import load_strings, site_characters
    from terradoc.config import load_config
    cfg = load_config(project / "terradoc.yaml")
    chars = site_characters(cfg, {loc: load_strings(loc, cfg) for loc in cfg.locales})
    assert {"ŋ", "ɨ"} <= chars


def test_site_of_pages_only_gets_no_people_layer_warnings(project):
    """No palette and no language_code are right for the project's own site (D21)."""
    portal(project)
    cfg = project / "terradoc.yaml"
    data = yaml.safe_load(cfg.read_text())
    data.pop("language_code", None)
    data["theme"].pop("palette", None)
    cfg.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    out = check(project).output
    assert "palette is not set" not in out and "language_code is not set" not in out


def test_alias_with_dot_parts_is_refused(project):
    """./index.html would overwrite the language page; pt/./index.html the home."""
    portal(project)
    write(project / "data" / "pages" / "pt" / "contato.md",
          "---\ntitle: C\naliases: [./index.html, pt/./index.html, a/../b.html]\n---\nx\n")
    result = check(project)
    assert result.exit_code == 1
    assert "no '.' or '..' parts" in result.output and "./index.html" in result.output


def test_front_matter_needs_delimiter_lines():
    """A --- inside a value is text; an unclosed front matter is an error."""
    import pytest

    from terradoc.pages_v2 import split_front_matter
    fm, body = split_front_matter("---\ntitle: Alpha---Beta\n---\nText --- more\n")
    assert fm == {"title": "Alpha---Beta"} and body == "Text --- more\n"
    assert split_front_matter("No front matter.\n") == ({}, "No front matter.\n")
    with pytest.raises(ValueError):
        split_front_matter("---\ntitle: x\nText\n")


def test_uncredited_page_pictures_are_counted(project):
    portal(project)  # p1.jpg has no credit, in three locales
    result = build(project)
    assert result.exit_code == 0, result.output
    assert "pages: 3 picture(s) shown without a credit" in result.output
    assert "1 picture(s) without a credit" in check(project).output


def test_site_title_and_hero_alt_per_locale(project):
    portal(project)
    write(project / "locales" / "en.yaml", (project / "locales" / "en.yaml").read_text()
          + '\nsite_title: "Indigenous Language Platform"\nhero_alt: "A school"\n')
    assert build(project).exit_code == 0
    en = (Path("site") / "en" / "index.html").read_text()
    assert "<title>Indigenous Language Platform</title>" in en
    assert 'class="td-brand__name">Indigenous Language Platform<' in en
    assert "Indigenous Language Platform" not in (Path("site") / "pt" / "index.html").read_text()
