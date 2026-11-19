"""Alphabet, fonts, locale completeness, the terradoc/ namespace and an independent
consumer of the bundle (0.14.0; on the v2 templates since 0.23.0)."""

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

def test_no_alphabet_uses_first_letters(project):
    write_dictionary(project, ("akapti", ""), ("bora", ""))
    assert build(project).exit_code == 0
    d = Path("site") / "pt" / "dictionary"
    assert (d / "a.html").is_file() and (d / "b.html").is_file()


def test_alphabet_reaches_the_dictionary(project):
    """Digraphs are letters with their own page, in the alphabet's order on the letter bar."""
    edit_config(project, alphabet=["a", "ã", "e", "mb", "m", "nd", "n"])
    write_dictionary(project, ("mbeku", ""), ("mata", ""), ("ãto", ""), ("aka", ""), ("ndu", ""))
    result = build(project)
    assert result.exit_code == 0, result.output
    d = Path("site") / "pt" / "dictionary"
    for letter in ("a", "ã", "mb", "m", "nd"):
        assert (d / f"{letter}.html").is_file(), letter
    assert "mbeku" in (d / "mb.html").read_text() and "mbeku" not in (d / "m.html").read_text()
    bar = (d / "index.html").read_text()
    from urllib.parse import quote
    order = [bar.index(f'href="{quote(x)}.html"') for x in ("a", "ã", "mb", "m", "nd")]
    assert order == sorted(order)


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

def test_text_font_covers_ipa_and_tilde_vowels(project):
    """The data's IPA and nasal vowels are in the text face: no [font] issue."""
    write_dictionary(project, ("boɾo", "ˈboɾo"), ("erẽy", "eˈɾẽj"))
    result = check(project)
    assert result.exit_code == 0, result.output
    assert "[font]" not in result.output


def test_character_missing_from_the_text_font_is_an_error(project, monkeypatch):
    """`check` says it before the build would stop (fonts.missing is what the build uses)."""
    from terradoc import fonts

    monkeypatch.setattr(fonts, "missing", lambda chars, text="gentium": sorted(c for c in chars if c == "ɾ"))
    write_dictionary(project, ("boɾo", ""))
    result = check(project)
    assert result.exit_code != 0
    assert "the text font (gentium) lacks characters the data uses: ɾ (U+027E" in result.output


@pytest.mark.parametrize("face", ["gentium", "charis", "andika"])
def test_bundled_text_faces_have_ipa_and_tilde_vowels(face):
    from terradoc import fonts

    assert fonts.missing(set("ãẽĩõũỹɾɨʃʒˈː"), face) == []


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
    d = project / "config" / "templates" / "v2" / "pages"
    d.mkdir(parents=True)
    (d / "dictionary_index.html.j2").write_text(
        '{% extends "terradoc/pages/dictionary_index.html.j2" %}'
        '{% block head %}{{ super() }}<meta name="site-extra" content="1">{% endblock %}')
    write_dictionary(project, ("akapti", ""))
    result = build(project)
    assert result.exit_code == 0, result.output
    html = (Path("site") / "pt" / "dictionary" / "index.html").read_text()
    assert '<meta name="site-extra" content="1">' in html
    assert "td-letters" in html or 'href="a.html"' in html  # the rest of terradoc's page


def test_site_base_reaches_every_page(project):
    """A site's base.html.j2 can extend terradoc's and add to a block the pages leave alone."""
    d = project / "config" / "templates" / "v2"
    d.mkdir(parents=True)
    (d / "base.html.j2").write_text(
        '{% extends "terradoc/base.html.j2" %}{% block head %}<meta name="site-base" content="1">{% endblock %}')
    result = build(project)
    assert result.exit_code == 0, result.output
    assert '<meta name="site-base" content="1">' in (Path("site") / "pt" / "about.html").read_text()


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
    """The blocks docs/packs.md promises to sites must exist in the v2 base.html.j2."""
    base = (ROOT / "src" / "terradoc" / "templates_v2" / "base.html.j2").read_text()
    for block in ("title", "head", "main"):
        assert f"{{% block {block} %}}" in base, block
