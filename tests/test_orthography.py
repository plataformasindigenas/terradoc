"""0.14.0: alphabet, fonts, locale completeness, the terradoc/ namespace, extra_css,
and an independent consumer of the bundle."""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from terradoc.cli import main

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    result = CliRunner().invoke(main, ["init", "demo"])
    assert result.exit_code == 0, result.output
    return tmp_path / "demo"


def run(*args):
    return CliRunner().invoke(main, list(args))


def edit_config(project: Path, **top):
    cfg = project / "terradoc.yaml"
    data = yaml.safe_load(cfg.read_text())
    theme = top.pop("theme", None)
    data.update(top)
    if theme:
        data.setdefault("theme", {}).update(theme)
    cfg.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def write_dictionary(project: Path, *rows: tuple[str, str]):
    lines = ["id\tentry\tipa\tpos\tdefinition"]
    for i, (entry, ipa) in enumerate(rows, start=1):
        lines.append(f"{i}\t{entry}\t{ipa}\tn\tsomething {i}")
    (project / "data" / "dictionary.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for old in (project / "data").glob("dictionary.y*ml"):
        old.unlink()


def build(project: Path):
    return run("build", "-c", str(project / "terradoc.yaml"), "--out", "site", "--bundle-dir", "bundle")


def check(project: Path):
    return run("check", "-c", str(project / "terradoc.yaml"))


# ── alphabet ─────────────────────────────────────────────────────────────

def test_no_alphabet_keeps_the_old_dictionary_code(project):
    assert build(project).exit_code == 0
    html = (Path("site") / "pt" / "dictionary.html").read_text()
    assert "ALPHA" not in html
    assert "ae.localeCompare(be, 'pt')" in html


def test_alphabet_reaches_the_dictionary(project):
    edit_config(project, alphabet=["a", "ã", "e", "mb", "m", "nd", "n"])
    result = build(project)
    assert result.exit_code == 0, result.output
    html = (Path("site") / "pt" / "dictionary.html").read_text()
    assert 'ALPHA = (function(letters)' in html
    assert '"mb", "m", "nd", "n"]' in html  # tojson escapes ã as \\u00e3, which JS reads back
    assert "ALPHA.compareWords" in html


def test_alphabet_must_be_a_list_of_letters(project):
    edit_config(project, alphabet="abc")
    result = check(project)
    assert result.exit_code != 0
    assert "alphabet" in result.output


def test_alphabet_duplicates_are_an_error(project):
    edit_config(project, alphabet=["a", "e", "A"])
    result = check(project)
    assert result.exit_code == 1
    assert "letters listed twice: a" in result.output


def test_headword_outside_the_alphabet_is_a_warning(project):
    edit_config(project, alphabet=["a", "e", "mb", "m"])
    write_dictionary(project, ("mbeku", ""), ("ere", ""), ("zebra", ""))
    result = check(project)
    assert result.exit_code == 0, result.output  # warnings publish
    assert "'zebra' starts with a letter that is not in the alphabet" in result.output
    assert "mbeku" not in result.output


def test_alphabet_matching_is_nfc(project):
    edit_config(project, alphabet=["e", "ẽ"])  # precomposed
    write_dictionary(project, ("ẽrẽy", ""))  # decomposed e + combining tilde
    result = check(project)
    assert "not in the alphabet" not in result.output


# ── fonts ────────────────────────────────────────────────────────────────

def test_ipa_missing_from_heading_font_is_a_warning(project):
    write_dictionary(project, ("boɾo", "ˈboɾo"))
    result = check(project)
    assert result.exit_code == 0, result.output
    assert "headings text uses letters that Sora lacks" in result.output
    assert "ɾ (U+027E" in result.output
    assert "ipa text" not in result.output  # IPA renders in Inter, which has it


def test_tilde_vowel_is_covered_by_inter(project):
    write_dictionary(project, ("erẽy", ""))
    result = check(project)
    assert "body text" not in result.output


def test_site_font_is_not_checked(project):
    edit_config(project, theme={"font_family_headings": "'Noto Sans', sans-serif"})
    write_dictionary(project, ("boɾo", ""))
    result = check(project)
    assert "[font]" not in result.output


def test_mono_ipa_font_is_flagged(project):
    edit_config(project, theme={"font_family_ipa": "'IBM Plex Mono', monospace"})
    write_dictionary(project, ("boro", "ˈboɾo"))
    result = check(project)
    assert "ipa text uses letters that IBM Plex Mono lacks" in result.output


def test_ipa_font_and_extra_css_reach_the_page(project):
    (project / "static" / "css").mkdir(parents=True)
    (project / "static" / "css" / "site.css").write_text("body{}")
    edit_config(project, theme={"font_family_ipa": "'Charis SIL', serif", "extra_css": ["css/site.css"]})
    result = build(project)
    assert result.exit_code == 0, result.output
    html = (Path("site") / "pt" / "dictionary.html").read_text()
    assert "--td-font-ipa: 'Charis SIL', serif;" in html
    assert 'href="../css/site.css"' in html


def test_bundled_fonts_include_the_tilde_vowels():
    css = (ROOT / "src" / "terradoc" / "static" / "css" / "fonts.css").read_text()
    assert "inter-vietnamese.woff2" in css
    assert (ROOT / "src" / "terradoc" / "static" / "fonts" / "inter-vietnamese.woff2").is_file()


# ── locales ──────────────────────────────────────────────────────────────

def test_missing_locale_key_is_a_warning(project):
    en = project / "locales" / "en.yaml"
    data = yaml.safe_load(en.read_text())
    key = sorted(data)[0]
    del data[key]
    en.write_text(yaml.safe_dump(data, allow_unicode=True))
    result = check(project)
    assert result.exit_code == 0, result.output
    assert f"key(s) of 'pt' missing in 'en'" in result.output
    assert key in result.output


def test_missing_locale_file_is_a_warning(project):
    edit_config(project, locales=["pt", "en", "bor"])
    result = check(project)
    assert "locale 'bor' has no file" in result.output


# ── templates ────────────────────────────────────────────────────────────

def test_site_page_can_extend_terradocs_own(project):
    d = project / "config" / "templates"
    d.mkdir(parents=True)
    (d / "dictionary.html.j2").write_text(
        '{% extends "terradoc/dictionary.html.j2" %}'
        '{% block extra_styles %}{{ super() }}/* SITE-EXTRA */{% endblock %}')
    result = build(project)
    assert result.exit_code == 0, result.output
    html = (Path("site") / "pt" / "dictionary.html").read_text()
    assert "/* SITE-EXTRA */" in html
    assert "letter-bar" in html  # the rest of terradoc's page is still there


def test_footer_block_can_be_replaced(project):
    d = project / "config" / "templates"
    d.mkdir(parents=True)
    (d / "base.html.j2").write_text(
        '{% extends "terradoc/base.html.j2" %}{% block footer %}<footer>SITE-FOOTER</footer>{% endblock %}')
    result = build(project)
    assert result.exit_code == 0, result.output
    assert "SITE-FOOTER" in (Path("site") / "pt" / "dictionary.html").read_text()


# ── an independent renderer ──────────────────────────────────────────────

def test_bundle_consumer_renders_the_dictionary(project, tmp_path):
    write_dictionary(project, ("akapti", "akapti"), ("amenko", ""))
    assert run("export", "-c", str(project / "terradoc.yaml"), "--bundle-dir", "bundle").exit_code == 0
    out = tmp_path / "dict.html"
    proc = subprocess.run([sys.executable, "-I", str(ROOT / "examples" / "bundle_dictionary.py"), "bundle", str(out)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    html = out.read_text()
    assert "<b>akapti</b>" in html and "<b>amenko</b>" in html


def test_block_contract():
    """The blocks docs/motifs.md promises to sites must exist in base.html.j2."""
    base = (ROOT / "src" / "terradoc" / "templates" / "base.html.j2").read_text()
    for block in ("title", "extra_styles", "content", "footer", "scripts"):
        assert f"{{% block {block} %}}" in base, block


@pytest.mark.skipif(not __import__("shutil").which("node"), reason="needs node")
def test_alphabet_sorting_in_the_browser_code(project):
    """Run the page's ALPHA in node: digraphs, and accented letters outside the alphabet."""
    import re

    edit_config(project, alphabet=["a", "ã", "b", "k", "kw", "o", "u", "w"])
    assert build(project).exit_code == 0
    html = (Path("site") / "pt" / "dictionary.html").read_text()
    code = re.search(r"var ALPHA = \(function\(letters\) \{.*?\}\)\(\[.*?\]\);", html, re.S).group(0)
    words = ["wo", "kudógó", "kwa", "ku", "ãb", "ab", "bó", "ba", "óa"]
    js = code + ("\nvar w = %s; w.sort(ALPHA.compareWords);"
                 "\nconsole.log(JSON.stringify([w, ALPHA.letterOf('óa'), ALPHA.letterOf('kwa')]));"
                 % __import__("json").dumps(words))
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    order, first_o, first_kw = __import__("json").loads(out)
    # ã is its own letter (after a); ó sorts as o; kw after every k-word
    assert order == ["ab", "ãb", "ba", "bó", "ku", "kudógó", "kwa", "óa", "wo"]
    assert [first_o, first_kw] == ["O", "KW"]
