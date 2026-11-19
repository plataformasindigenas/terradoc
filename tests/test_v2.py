"""v2 template set (P1): palette, packs, fonts, routes, the built site."""

import ast
import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from terradoc import fonts, packs, palette, sitecheck
from terradoc.cli import main
from terradoc.config import load_config

BORORO = {
    "ground": {"color": "#F4F1EA", "material": "argila branca"},
    "ink": "#111827", "primary": {"color": "#C81F2D", "material": "urucum"},
    "fill": "#D4A03A", "muted": "#6B6F5A",
}


@pytest.fixture()
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    result = CliRunner().invoke(main, ["init", "demo"])
    assert result.exit_code == 0, result.output
    return tmp_path / "demo"


def set_theme(project: Path, **theme):
    path = project / "terradoc.yaml"
    raw = yaml.safe_load(path.read_text())
    top = {k: theme.pop(k) for k in list(theme) if k in ("language_code", "alphabet")}
    raw.update(top)
    raw.setdefault("theme", {}).update(theme)
    path.write_text(yaml.safe_dump(raw, allow_unicode=True))


def build(project: Path, *extra: str):
    return CliRunner().invoke(main, ["build", "-c", str(project / "terradoc.yaml"), "--out", "site",
                                     "--bundle-dir", "bundle", *extra])


# ── palette ──────────────────────────────────────────────────────────────

def test_palette_parses_roles_and_materials():
    roles = palette.parse(BORORO)
    assert roles["primary"].color == "#C81F2D" and roles["primary"].material == "urucum"
    assert roles["ink"].material == ""
    assert palette.contrast_problems(roles) == []


@pytest.mark.parametrize("raw, message", [
    ({"ground": "#fff"}, "not a #rrggbb"),
    ({"paper": "#FFFFFF"}, "unknown role"),
    ("red", "must be a mapping"),
])
def test_palette_rejects_bad_values(raw, message):
    with pytest.raises(ValueError, match=message):
        palette.parse(raw)


def test_palette_contrast_failures_are_named():
    roles = palette.parse({**BORORO, "primary": "#D4A81E"})  # gold as primary: 2.0:1
    problems = palette.contrast_problems(roles)
    assert any("primary on ground" in p for p in problems)
    assert palette.contrast_problems(palette.parse({"ink": "#000000"}))[0].startswith(
        "theme.palette is missing")


def test_contrast_matches_wcag():
    assert round(palette.contrast("#000000", "#FFFFFF"), 2) == 21.0
    assert round(palette.contrast("#C81F2D", "#F4F1EA"), 2) == 5.05  # palettes.md


# ── config ───────────────────────────────────────────────────────────────

def test_v2_keys_are_known_and_switch_template_dirs(project):
    set_theme(project, templates="v2", palette=BORORO, pack="none", hero_credit="X",
              hero_alt="Y", hero_people=False, font_vernacular="charis", language_code="bor")
    cfg = load_config(project / "terradoc.yaml")
    assert cfg.unknown_theme_keys == []
    assert cfg.language_code == "bor" and cfg.theme.hero_people is False
    assert cfg.local_template_dir == project / "config" / "templates" / "v2"
    assert cfg.bundled_template_dir.name == "templates_v2"


def test_v2_is_the_default(project):
    """Since 0.23.0 v2 is the only set: no `templates` key needed."""
    cfg = load_config(project / "terradoc.yaml")
    assert cfg.theme.templates == "v2"
    assert cfg.local_template_dir == project / "config" / "templates" / "v2"
    assert cfg.bundled_template_dir.name == "templates_v2"


# ── packs ────────────────────────────────────────────────────────────────

def write_pack(project: Path, name="p", approved=True, svg='<svg xmlns="http://www.w3.org/2000/svg" '
               'width="10" height="8"><rect width="10" height="8" fill="{{ palette.fill }}"/></svg>'):
    d = project / "config" / "templates" / "v2" / "motifs" / name
    d.mkdir(parents=True)
    el = {"title": "t", "sources": ["s"]}
    if approved:
        el["approved"] = {"by_role": "coordinator", "date": "2026-11-18"}
    (d / "pack.yaml").write_text(yaml.safe_dump({"people": "P", "elements": {"band": el}}))
    (d / "band.svg.j2").write_text(svg)
    return d


def test_pack_renders_approved_elements(project, tmp_path):
    write_pack(project)
    set_theme(project, pack="p", templates="v2")
    cfg = load_config(project / "terradoc.yaml")
    pack = packs.render(packs.load(cfg), {"fill": "#123456"}, tmp_path / "out")
    assert pack.problems == []
    band = pack.get("band")
    assert band.height == 8 and "#123456" in band.svg
    assert (tmp_path / "out" / band.file).read_text() == band.svg


def test_unapproved_element_is_dropped_and_reported(project):
    write_pack(project, approved=False)
    set_theme(project, pack="p", templates="v2")
    pack = packs.load(load_config(project / "terradoc.yaml"))
    assert pack.get("band") is None
    assert any("approved" in p for p in pack.problems)


@pytest.mark.parametrize("kind", ["unapproved", "broken svg", "undefined colour", "list yaml"])
def test_a_bad_pack_element_falls_back_to_the_palette(project, kind):
    if kind == "unapproved":
        write_pack(project, approved=False)
    elif kind == "broken svg":
        write_pack(project, svg='<svg xmlns="http://www.w3.org/2000/svg" width="." height="8"/>')
    elif kind == "undefined colour":
        write_pack(project, svg='<svg width="1" height="1" fill="{{ palette.nope }}"/>')
    else:
        d = write_pack(project)
        (d / "pack.yaml").write_text("- a\n- b\n")
    set_theme(project, pack="p", templates="v2", palette=BORORO)
    result = build(project)
    assert result.exit_code == 0, result.output
    assert "WARNING" in result.output
    assert not list(Path("site/assets").glob("pack/band.*"))
    assert '<hr class="td-rule">' in Path("site/pt/index.html").read_text()


def test_a_missing_pack_is_an_error(project):
    set_theme(project, pack="nope", templates="v2", palette=BORORO)
    result = build(project)
    assert result.exit_code != 0 and "no pack 'nope'" in result.output
    set_theme(project, pack="../x")
    result = build(project)
    assert result.exit_code != 0 and "not a pack name" in result.output


S = 'xmlns="http://www.w3.org/2000/svg" width="1" height="1"'


@pytest.mark.parametrize("svg, problem", [
    (f'<svg {S}><script>x</script></svg>', "<script>"),
    (f'<svg {S}><image href="https://x/y.png"/></svg>', "<image>"),
    (f'<svg {S}><use href="https://x/y.svg#a"/></svg>', "external"),
    (f'<svg {S} onload="x()"></svg>', "event"),
    (f'<svg {S}><style>rect{{fill:url(https://x/a)}}</style></svg>', "<style>"),
    (f'<svg {S}><rect style="fill:url(https://x/a)"/></svg>', "style attribute"),
    (f'<svg {S}><rect fill="url(https://x/a#p)"/></svg>', "external"),
    (f'<svg {S}><set attributeName="href" to="javascript:x"/></svg>', "<set>"),
    ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1" data-height="9"></svg>', "width and height"),
    ('<svg xmlns="http://www.w3.org/2000/svg" width="." height="1"></svg>', "width and height"),
    ('<rect/>', "<svg>"),
    ('<svg', "well-formed"),
])
def test_svg_problems(svg, problem):
    assert problem in packs.svg_problem(svg)


def test_bundled_weave_pack_loads(project):
    set_theme(project, templates="v2")
    pack = packs.load(load_config(project / "terradoc.yaml"))
    assert pack.name == "weave" and set(pack.elements) == {"band", "texture"}
    assert pack.problems == []


# ── fonts ────────────────────────────────────────────────────────────────

def test_covered_ranges_match_the_vendoring_script():
    script = Path(__file__).resolve().parent.parent / "scripts" / "vendor_fonts.py"
    tree = ast.parse(script.read_text())
    ranges = next(ast.literal_eval(n.value) for n in ast.walk(tree)
                  if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "RANGES")
    assert tuple(tuple(r) for r in ranges) == fonts.COVERED


@pytest.mark.parametrize("face", fonts.TEXT_FACES)
def test_font_covers_the_orthographies(face):
    chars = fonts.collect(["ẽ ĩ ũ ỹ ɨ ʉ ɛ ɔ ə ŋ ʔ ɾ ʃ ɲ ʼ ɡ ˈ ː β ɸ ʂ", "g̃ ɨ̃ a̱ ñ ç"])
    assert fonts.missing(chars, face) == []


def test_text_face_is_chosen_per_site(project):
    set_theme(project, templates="v2", palette=BORORO, font_vernacular="gentium")
    assert build(project).exit_code == 0
    from fontTools.ttLib import TTFont
    f = next(Path("site/assets/fonts").glob("td-text-400.*.woff2"))
    assert "Gentium" in " ".join(str(n) for n in TTFont(f)["name"].names if n.nameID == 7)
    set_theme(project, font_vernacular="garamond")
    result = CliRunner().invoke(main, ["check", "-c", str(project / "terradoc.yaml")])
    assert result.exit_code != 0 and "font_vernacular" in result.output


def test_missing_reports_covered_characters_only():
    # U+0378 is unassigned (inside the Greek range), U+4E00 is outside every covered range
    assert fonts.missing({"͸", "一", "a"}) == ["͸"]


def test_subset_is_small_and_hashed(tmp_path):
    built = fonts.build(fonts.collect(["Boe Eno Moto, aregódu ɔɛ ẽ"]), tmp_path)
    assert {b.face.file for b in built} == {f.file for f in fonts.FACES}
    assert {b.name.split(".")[0] for b in built} == {"td-text-400", "td-text-400i", "td-text-700", "td-ui-400"}
    for b in built:
        assert (tmp_path / b.name).stat().st_size == b.size < 25_000
        assert b.name.count(".") == 2
    css = fonts.font_face_css(built, "fonts/")
    assert css.count("@font-face") == len(fonts.FACES) and "font-display:swap" in css


# ── the built site ───────────────────────────────────────────────────────

def test_v2_site_builds_with_working_links(project):
    set_theme(project, templates="v2", palette=BORORO, language_code="bor")
    result = build(project)
    assert result.exit_code == 0, result.output
    site = Path("site")
    for path in ("index.html", "404.html", "pt/index.html", "en/index.html",
                 "pt/dictionary/index.html", "pt/about.html"):
        assert (site / path).is_file(), path
    assert sitecheck.broken_links(site) == []
    assert all(w < 150 * 1024 for w in sitecheck.page_weights(site).values())
    home = (site / "pt" / "index.html").read_text()
    assert '<html lang="pt-BR" data-root="../">' in home
    assert 'lang="bor"' in home
    assert 'action="../pt/dictionary/index.html"' in home
    assert 'rel="preload"' in home and "td-text-400." in home
    css = next((site / "assets").glob("site.*.css")).read_text()
    assert "--primary:#C81F2D" in css and "@font-face" in css
    release = json.loads((site / ".release.json").read_text())
    assert release["owned_by_terradoc"] is True


def test_templates_option_overrides_config(project):
    result = build(project, "--templates", "v2")
    assert result.exit_code == 0, result.output
    assert next(Path("site/assets").glob("site.*.css"))
    assert not Path("site/css/terradoc.css").exists()


def test_two_builds_give_the_same_bytes(project):
    set_theme(project, templates="v2", palette=BORORO)
    for out in ("a", "b"):
        result = CliRunner().invoke(main, ["build", "-c", str(project / "terradoc.yaml"), "--out", out,
                                           "--bundle-dir", "bundle"])
        assert result.exit_code == 0, result.output
    files = sorted(p.relative_to("a") for p in Path("a").rglob("*") if p.is_file() and p.name != ".release.json")
    assert files == sorted(p.relative_to("b") for p in Path("b").rglob("*") if p.is_file() and p.name != ".release.json")
    for f in files:
        assert (Path("a") / f).read_bytes() == (Path("b") / f).read_bytes(), f


def test_rebuild_without_clean_leaves_no_stale_assets(project):
    set_theme(project, templates="v2", palette=BORORO)
    assert build(project).exit_code == 0
    set_theme(project, palette={**BORORO, "primary": "#A01924"})
    assert build(project).exit_code == 0
    assert len(list(Path("site/assets").glob("site.*.css"))) == 1


def test_depth_two_pages_link_back_correctly(project):
    set_theme(project, templates="v2", palette=BORORO)
    assert build(project).exit_code == 0
    page = Path("site/pt/dictionary/index.html").read_text()
    assert 'href="../../en/dictionary/index.html"' in page
    assert 'href="../../assets/site.' in page
    assert sitecheck.broken_links(Path("site")) == []


def test_error_page_works_under_any_mount(project):
    set_theme(project, templates="v2", palette=BORORO)
    path = project / "terradoc.yaml"
    raw = yaml.safe_load(path.read_text())
    raw["base_url"] = "https://demo.terradoc.org"
    path.write_text(yaml.safe_dump(raw))
    assert build(project).exit_code == 0
    page = Path("site/404.html").read_text()
    assert "<style>" in page and 'rel="stylesheet"' not in page and "<script" not in page
    assert 'href="https://demo.terradoc.org/pt/index.html"' in page
    assert 'href="/' not in page and 'src="/' not in page


def test_specimen_page_shows_the_alphabet(project):
    set_theme(project, templates="v2", palette=BORORO, alphabet=["a", "ẽ", "ɨ"])
    assert build(project).exit_code == 0
    page = Path("site/specimen.html").read_text()
    assert "Ẽẽ" in page and "noindex" in page
    assert "specimen" not in (Path("site/sitemap.xml").read_text() if Path("site/sitemap.xml").exists() else "")


def test_fonts_cover_template_and_credit_characters(project):
    set_theme(project, templates="v2", palette=BORORO, hero_credit="Łukasz")
    assert build(project).exit_code == 0
    from fontTools.ttLib import TTFont
    for f in Path("site/assets/fonts").glob("td-text-400.*.woff2"):
        cmap = TTFont(f).getBestCmap()
        assert ord("·") in cmap and ord("Ł") in cmap


def test_unknown_locale_gets_english_strings_and_its_own_lang(project):
    from terradoc.build_v2 import load_strings
    cfg = load_config(project / "terradoc.yaml")
    t = load_strings("fr", cfg)
    assert t.html_lang == "fr" and t.ui_skip == "Skip to content"


def test_spanish_strings_are_bundled_with_every_key(project):
    """es since 0.24.0 (the portal is pt/en/es): same keys as pt."""
    from terradoc.build_v2 import bundled_dir, load_strings
    cfg = load_config(project / "terradoc.yaml")
    t = load_strings("es", cfg)
    assert t.html_lang == "es" and t.ui_skip == "Saltar al contenido"
    keys = lambda loc: set(yaml.safe_load((bundled_dir() / "strings" / f"{loc}.yaml").read_text()))  # noqa: E731
    assert keys("es") == keys("pt") == keys("en")


def test_v2_check_errors(project):
    set_theme(project, templates="v2", palette={**BORORO, "primary": "#D4A81E"})
    (project / "config" / "templates").mkdir(parents=True, exist_ok=True)
    (project / "config" / "templates" / "index.html.j2").write_text("{{ x }}")
    result = CliRunner().invoke(main, ["check", "-c", str(project / "terradoc.yaml")])
    assert result.exit_code != 0
    assert "primary on ground" in result.output
    assert "v1 page overrides" in result.output


@pytest.mark.parametrize("theme, message", [
    ({"hero_image": "images/logo.svg"}, "a photograph"),
    ({"hero_image": "../../etc/passwd"}, "inside static/"),
    ({"colors": {"bg": "#fff"}}, "a setting of the v1 templates, removed in terradoc 0.23.0"),
])
def test_v2_check_refuses_bad_settings(project, theme, message):
    set_theme(project, templates="v2", **theme)
    (project / "static" / "images").mkdir(parents=True, exist_ok=True)
    (project / "static" / "images" / "logo.svg").write_text("<svg/>")
    result = CliRunner().invoke(main, ["check", "-c", str(project / "terradoc.yaml")])
    assert result.exit_code != 0
    assert message in result.output


def test_static_assets_is_reserved(project):
    set_theme(project, templates="v2", palette=BORORO)
    (project / "static" / "assets").mkdir(parents=True)
    (project / "static" / "assets" / "x.txt").write_text("x")
    result = CliRunner().invoke(main, ["check", "-c", str(project / "terradoc.yaml")])
    assert result.exit_code != 0 and "static/assets/ is reserved" in result.output


def test_v2_site_override_extends_terradoc_template(project):
    set_theme(project, templates="v2", palette=BORORO)
    d = project / "config" / "templates" / "v2" / "pages"
    d.mkdir(parents=True)
    (d / "home.html.j2").write_text('{% extends "terradoc/pages/home.html.j2" %}'
                                    '{% block main %}<p>site home</p>{{ super() }}{% endblock %}')
    result = build(project)
    assert result.exit_code == 0, result.output
    assert "<p>site home</p>" in Path("site/pt/index.html").read_text()


def test_sitemap_has_absolute_urls_and_no_error_page(project):
    set_theme(project, templates="v2", palette=BORORO)
    path = project / "terradoc.yaml"
    raw = yaml.safe_load(path.read_text())
    raw["base_url"] = "https://demo.terradoc.org"
    path.write_text(yaml.safe_dump(raw))
    assert build(project).exit_code == 0
    site = Path("site")
    assert sitecheck.sitemap_problems(site) == []
    text = (site / "sitemap.xml").read_text()
    assert "https://demo.terradoc.org/pt/index.html" in text and "404" not in text
    home = (site / "pt" / "index.html").read_text()
    assert 'hreflang="en" href="https://demo.terradoc.org/en/index.html"' in home
