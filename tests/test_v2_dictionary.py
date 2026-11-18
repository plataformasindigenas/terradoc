"""v2 dictionary (P2): letter pages, word pages, search index, old links, service worker."""

import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from terradoc import sitecheck
from terradoc.cli import main
from terradoc.dictionary_v2 import entry_file, gloss
from terradoc.orthography import Alphabet
from tests.test_v2 import BORORO, build, project, set_theme  # noqa: F401

ROWS = [
    # id, entry, homonym, pos, definition, ipa, example, comment
    (1, "aka", 2, "S", "segundo sentido", "aka", "", ""),
    (2, "aka", 1, "LEX", "primeiro sentido", "", "aka ba = exemplo", ""),
    (3, "mbore", "", "V", "andar", "ᵐbore", "", "nota"),
    (4, "ãto", "", "X", "fogo", "", "", ""),
    (5, "óra", "", "", "rio", "", "", ""),
    (6, "casa", "", "", "palavra fora do alfabeto", "", "", ""),
]


def write_dictionary(project: Path, rows=ROWS):
    lines = ["id\tentry\thomonym\tpos\tdefinition\tipa\texample_sent\tcomment"]
    lines += ["\t".join(str(x) for x in r) for r in rows]
    (project / "data" / "dictionary.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for old in (project / "data").glob("dictionary.y*ml"):
        old.unlink()


def site_with_dictionary(project, **extra):
    write_dictionary(project)
    set_theme(project, templates="v2", palette=BORORO, language_code="mpu",
              alphabet=["a", "ã", "b", "e", "m", "mb", "o", "r", "t"], **extra)
    path = project / "terradoc.yaml"
    raw = yaml.safe_load(path.read_text())
    raw["base_url"] = "https://demo.terradoc.org"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True))
    result = build(project)
    assert result.exit_code == 0, result.output
    return Path("site")


# ── alphabet in Python ───────────────────────────────────────────────────

def test_python_alphabet_matches_the_browser_code():
    a = Alphabet(["a", "ã", "b", "k", "kw", "o", "u", "w"])
    words = ["wo", "kudógó", "kwa", "ku", "ãb", "ab", "bó", "ba", "óa"]
    assert sorted(words, key=a.sort_key) == ["ab", "ãb", "ba", "bó", "ku", "kudógó", "kwa", "óa", "wo"]
    assert a.first_letter("óa") == "o" and a.first_letter("kwa") == "kw"
    assert a.first_letter("casa") is None and a.first_letter("-ka") == "k"


@pytest.mark.skipif(not __import__("shutil").which("node"), reason="needs node")
def test_python_and_v1_page_order_agree_on_real_words():
    """The v1 page script and the v2 letter pages must list words in the same order."""
    src = (Path(__file__).resolve().parent.parent / "src" / "terradoc" / "templates" / "dictionary.html.j2").read_text()
    code = re.search(r"var ALPHA = \(function\(letters\) \{.*?\n        \}\)\(", src, re.S).group(0)
    letters = ["a", "ã", "e", "ẽ", "g", "i", "ĩ", "k", "l", "m", "mb", "n", "nd", "ng", "nj", "o", "õ",
               "p", "r", "t", "u", "ũ", "w", "x", "y"]
    words = ["mbore", "mamõap yãpet", "ãto", "ndutnda", "nga", "na", "-ka", "kõ", "ko", "óra", "o'a",
             "ẽpe", "epe", "x-ray", "yã", "ũen", "uen", "wã", "ming", "mito"]
    js = code + json.dumps(letters) + ");\nvar w = " + json.dumps(words) + \
        "; w.sort(ALPHA.compareWords); console.log(JSON.stringify(w));"
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == sorted(words, key=Alphabet(letters).sort_key)


# ── names ────────────────────────────────────────────────────────────────

def test_entry_file_names():
    assert entry_file(30, "aregodu") == "30-aregodu.html"
    assert entry_file(7, "Ãto bõe") == "7-ato-boe.html"
    assert entry_file(8, "—") == "8.html"


def test_gloss_is_short_and_single_line():
    assert gloss("a\n  b") == "a b"
    assert len(gloss("x" * 400)) == 160 and gloss("x" * 400).endswith("…")


# ── the built dictionary ─────────────────────────────────────────────────

def test_letter_and_word_pages(project):
    site = site_with_dictionary(project)
    d = site / "pt" / "dictionary"
    assert sorted(p.name for p in d.glob("*.html")) == sorted([
        "index.html", "a.html", "ã.html", "mb.html", "o.html", "_.html",
        "1-aka.html", "2-aka.html", "3-mbore.html", "4-ato.html", "5-ora.html", "6-casa.html"])
    a = (d / "a.html").read_text()
    # homonyms in number order, with their number as a superscript
    assert a.index('href="2-aka.html"') < a.index('href="1-aka.html"')
    assert '<sup class="td-homonym">1</sup>' in a
    assert 'lang="mpu"' in a
    assert "óra" in (d / "o.html").read_text()  # ó sorts as o
    assert "casa" in (d / "_.html").read_text()
    assert sitecheck.broken_links(site) == []


def test_word_page_contents(project):
    site = site_with_dictionary(project)
    d = site / "pt" / "dictionary"
    one = (d / "2-aka.html").read_text()
    assert '<h1 class="td-entry__hw"><span class="td-word"><span class="td-hw" lang="mpu">aka</span><sup class="td-homonym">1</sup>' in one
    assert "td-entry__pos" not in one  # LEX is a placeholder
    assert "aka ba = exemplo" in one
    assert 'href="a.html#e-2"' in one  # back to the list, at this word
    assert 'rel="next" href="1-aka.html"' in one
    assert '<link rel="canonical" href="https://demo.terradoc.org/pt/dictionary/2-aka.html">' in one
    assert 'hreflang="en" href="https://demo.terradoc.org/en/dictionary/2-aka.html"' in one
    three = (d / "3-mbore.html").read_text()
    assert "Verbo" in three or ">V<" in three
    assert "/ᵐbore/" in three and "nota" in three
    assert "td-audio" not in three
    en = (site / "en" / "dictionary" / "3-mbore.html").read_text()
    assert '<div class="td-entry__def" lang="pt-BR">andar</div>' in en  # glosses are Portuguese


def test_search_index(project):
    site = site_with_dictionary(project)
    index = next((site / "assets" / "search").glob("dictionary.*.json"))
    data = json.loads(index.read_text())
    assert data["fields"][:4] == ["id", "entry", "homonym", "file"]
    assert [r[0] for r in data["rows"]][:3] == [2, 1, 4]  # dictionary order
    page = (site / "pt" / "dictionary" / "index.html").read_text()
    assert f'data-index="../../assets/search/{index.name}"' in page
    assert 'class="td-keyboard"' in page and 'data-key="ã"' in page


def test_search_folds_reach_the_page(project):
    site = site_with_dictionary(project)
    path = project / "terradoc.yaml"
    raw = yaml.safe_load(path.read_text())
    raw["search_folds"] = {"r": "l", "U": "o"}
    raw["keyboard"] = ["á"]
    path.write_text(yaml.safe_dump(raw, allow_unicode=True))
    assert build(project).exit_code == 0
    page = (site / "pt" / "dictionary" / "index.html").read_text()
    assert "&#34;r&#34;: &#34;l&#34;" in page and "&#34;u&#34;: &#34;o&#34;" in page
    assert 'data-key="á"' in page


def test_old_links_page_and_sitemap(project):
    site = site_with_dictionary(project)
    compat = (site / "pt" / "dictionary.html").read_text()
    assert "noindex" in compat and "entry" in compat and "search" in compat
    sitemap = (site / "sitemap.xml").read_text()
    assert "/pt/dictionary/2-aka.html" in sitemap and "/pt/dictionary/a.html" in sitemap
    assert "/pt/dictionary.html" not in sitemap


def test_service_worker_precaches_existing_files(project):
    site = site_with_dictionary(project)
    sw = (site / "sw.js").read_text()
    precache = json.loads(re.search(r"var PRECACHE = (\[.*?\]);", sw).group(1))
    assert "pt/dictionary/index.html" in precache
    assert any(p.startswith("assets/search/") for p in precache)
    assert all((site / p).is_file() for p in precache)
    assert "__VERSION__" not in sw and "__OFFLINE__" not in sw


def test_audio_only_for_files_that_exist(project):
    write_dictionary(project)
    audio = project / "data" / "audio"
    audio.mkdir(parents=True)
    (audio / "mbore.webm").write_bytes(b"\x1aE\xdf\xa3")
    set_theme(project, templates="v2", palette=BORORO, alphabet=["a", "ã", "b", "e", "m", "mb", "o", "r", "t"])
    assert build(project).exit_code == 0
    page = Path("site/pt/dictionary/3-mbore.html").read_text()
    assert '<source src="../../audio/mbore.webm" type="audio/webm">' in page
    assert "Gravação" in page
    assert "♪" in Path("site/pt/dictionary/mb.html").read_text()
