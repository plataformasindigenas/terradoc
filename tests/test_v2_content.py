"""v2 pages other than the dictionary (P3): species, encyclopedia, bibliography, videos,
corpus, about, links between modules, pictures."""

from pathlib import Path

import pytest
import yaml
from PIL import Image

from terradoc import content_v2 as cv
from terradoc import images, sitecheck
from tests.test_v2 import BORORO, build, project, set_theme  # noqa: F401  (fixture)


# ── pieces ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw, text", [
    (r"Descri\c{c}\~ao", "Descrição"),
    (r"l\'ingua irm\~a", "língua irmã"),
    (r"{\'E}tudes", "Études"),
    (r'Ber\"{o}m', "Beröm"),
    (r"pp. 1--20", "pp. 1–20"),
    (r"Tupar\'{\i}", "Tuparí"),
    ("plain text", "plain text"),
])
def test_delatex(raw, text):
    assert cv.delatex(raw) == text


def test_bib_entry_formats_and_drops_noise():
    b = cv.bib_entry({"id": "x", "type": "article", "author": "Silva, Ana and Souza, Rui and others",
                      "title": "Um estudo.", "year": "2001", "journal": "Revista", "volume": "3",
                      "number": "2", "pages": "1--9", "note": "Source list item [4].",
                      "doi": "https://doi.org/10.1/abc"})
    assert b["authors"] == "Silva, Ana; Souza, Rui; et al."
    assert b["parts"] == [("", "Silva, Ana; Souza, Rui; et al. (2001)."), ("", "Um estudo."),
                          ("", "Revista 3(2): 1–9.")]
    assert b["link"] == "https://doi.org/10.1/abc"
    thesis = cv.bib_entry({"id": "t", "type": "phdthesis", "author": "A, B", "title": "T", "year": "1",
                           "school": "USP", "address": "São Paulo"})
    assert ("i", "T.") in thesis["parts"] and ("thesis", ", São Paulo, USP.") in thesis["parts"]


def test_plain_markdown_in_summaries():
    assert cv.plain_markdown("o [(Harpia)](https://x.org/a) e *Aroe*") == "o (Harpia) e Aroe"


def test_links_are_shown_on_both_sides():
    links = cv.Links()
    links.add("dictionary", 7, "7-adugo.html", "adugo", True)
    links.add("fauna", 1, "1-adugo.html", "Adugo", True)
    links.add("encyclopedia", "adugo", "adugo.html", "Adugo", False)
    links.add_rows("dictionary", [(7, {"_linked_fauna": [{"id": 1}], "_linked_encyclopedia": [{"id": "gone"}]})])
    links.add_rows("encyclopedia", [("adugo", {"_linked_dictionary": [{"id": "7"}]})])
    labels = {"dictionary": "Dicionário", "fauna": "Fauna", "encyclopedia": "Enciclopédia"}
    assert [r["href"] for r in links.related("dictionary", 7, labels)] == \
        ["../fauna/1-adugo.html", "../encyclopedia/adugo.html"]  # "gone" is not built: dropped
    assert [r["href"] for r in links.related("fauna", 1, labels)] == ["../dictionary/7-adugo.html"]


def test_many_small_groups_become_one_list():
    def item(n, group):
        return cv.Item("fauna", n, {}, f"{n}.html", f"name{n:02d}", True, group)
    few = [item(n, "a" if n % 2 else "b") for n in range(6)]
    assert len(cv.groups(few, "?")) == 2
    many = [item(n, f"g{n}") for n in range(cv.MAX_GROUPS + 1)]
    sections = cv.groups(many, "?")
    assert len(sections) == 1 and sections[0]["flat"]


def test_article_images_point_at_the_site_root():
    html = '<p><img src="images/a.jpg"><img src="https://x/b.jpg"><img src="../c.jpg"></p>'
    assert cv.rewrite_article_html(html, "../../") == \
        '<p><img src="../../images/a.jpg"><img src="https://x/b.jpg"><img src="../c.jpg"></p>'


def test_videos_local_audio_and_youtube(tmp_path):
    (tmp_path / "audio").mkdir()
    (tmp_path / "audio" / "story.mp4").write_bytes(b"x")

    class Config:
        bundle_dir = tmp_path

    (tmp_path / "videos.json").write_text(
        '{"data": [{"youtube_id": "story", "source_url": "audio/story.mp4", "title": "S"},'
        ' {"youtube_id": "uhxWDBM8gss", "title": "Y"},'
        ' {"youtube_id": "not-a-real-id", "title": "gone"},'
        ' {"source_url": "../etc/passwd", "title": "out"}]}')
    videos = cv.load_videos(Config, tmp_path)
    assert [(v["title"], v["audio"], bool(v["youtube"])) for v in videos] == [("S", True, False), ("Y", False, True)]


def test_derive_many_runs_in_parallel_and_reports_bad_files(tmp_path):
    jobs = []
    for n in range(10):
        p = tmp_path / f"p{n}.jpg"
        Image.new("RGB", (600 + n, 400), (n * 20, 80, 120)).save(p)
        jobs.append((p, f"images/p{n}.jpg"))
    (tmp_path / "bad.jpg").write_text("not an image")
    jobs.append((tmp_path / "bad.jpg", "images/bad.jpg"))
    done, failed = images.derive_many(jobs, tmp_path / "out", workers=2)
    assert sorted(failed) == ["images/bad.jpg"] and len(done) == 10
    assert [w for _, w in done["images/p0.jpg"].webp] == [160, 480, 600]
    again, _ = images.derive_many(jobs[:10], tmp_path / "out2", workers=1)
    for rel, d in done.items():
        for (a, _), (b, _) in zip(d.webp, again[rel].webp):
            assert a == b and (tmp_path / "out" / a).read_bytes() == (tmp_path / "out2" / b).read_bytes()


# ── the built site ───────────────────────────────────────────────────────

def add_modules(project: Path):
    raw = yaml.safe_load((project / "terradoc.yaml").read_text())
    for m in ("fauna", "bibliography"):
        raw["modules"][m] = {"enabled": True}
    (project / "terradoc.yaml").write_text(yaml.safe_dump(raw, allow_unicode=True))
    (project / "static" / "images").mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 600), (120, 90, 40)).save(project / "static" / "images" / "onca.jpg")
    (project / "data" / "fauna.yaml").write_text(yaml.safe_dump([
        {"id": 1, "name_indigenous": "adugo", "name_portuguese": "onça", "scientific_name": "Panthera onca",
         "pic_link": "images/onca.jpg", "pic_credit": "Foto: A. B.", "info": "Felino."},
        {"id": 2, "name_indigenous": "", "name_portuguese": "anta", "pic_link": "../../etc/passwd"},
    ], allow_unicode=True))
    (project / "data" / "references.bib").write_text(
        "@book{silva2001,\n  author = {Silva, Ana},\n  title = {L\\'ingua},\n  year = {2001},\n"
        "  publisher = {Ed}\n}\n")


def test_other_modules_build_with_working_links(project):
    set_theme(project, templates="v2", palette=BORORO, language_code="bor")
    add_modules(project)
    result = build(project)
    assert result.exit_code == 0, result.output
    site = Path("site")
    assert sitecheck.broken_links(site) == []
    fauna = (site / "pt" / "fauna.html").read_text()
    assert 'href="fauna/1-adugo.html"' in fauna and '<span class="td-card__name" lang="bor">adugo</span>' in fauna
    page = (site / "pt" / "fauna" / "1-adugo.html").read_text()
    assert "Foto: A. B." in page and "Foto: Foto:" not in page
    assert 'type="image/webp"' in page and "assets/img/onca-" in page
    anta = (site / "pt" / "fauna" / "2-anta.html").read_text()
    assert "passwd" not in anta and "<picture>" not in anta  # confined to static/
    bib = (site / "pt" / "bibliography.html").read_text()
    assert 'id="ref-silva2001"' in bib and "<i>Língua.</i>" in bib
    for path in site.glob("pt/encyclopedia/*.html"):
        assert "td-article" in path.read_text()
    about = (site / "pt" / "about.html").read_text()
    assert "td-about" in about
    assert "ui_pending_text" not in about


def test_unused_pictures_are_pruned_and_reused(project):
    set_theme(project, templates="v2", palette=BORORO)
    add_modules(project)
    assert build(project).exit_code == 0
    first = sorted(p.name for p in Path("site/assets/img").iterdir())
    assert first and all(n.startswith("onca-") for n in first)
    Image.new("RGB", (800, 600), (10, 90, 40)).save(project / "static" / "images" / "onca.jpg")
    assert build(project).exit_code == 0
    second = sorted(p.name for p in Path("site/assets/img").iterdir())
    assert len(second) == len(first) and not set(first) & set(second)


# ── review fixes (reviews/2026-11-18-p3-review-*) ───────────────────────

def test_related_order_does_not_depend_on_hashing():
    import subprocess
    import sys
    code = ("from terradoc.content_v2 import Links\n"
            "l = Links()\n"
            "l.add('encyclopedia', 'k', 'k.html', 'K', False)\n"
            "for n in (3027, 3028, 3029):\n"
            "    l.add('dictionary', n, f'{n}-kudoro.html', 'kudoro', True)\n"
            "    l.add_rows('dictionary', [(n, {'_linked_encyclopedia': [{'id': 'k'}]})])\n"
            "print([r['file'] for r in l.related('encyclopedia', 'k', {})])\n")
    outs = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           env={"PYTHONHASHSEED": str(seed), "PATH": ""}).stdout for seed in range(1, 6)}
    assert outs == {"['3027-kudoro.html', '3028-kudoro.html', '3029-kudoro.html']\n"}


def test_corpus_files_are_unique_and_tagged(tmp_path):
    class Config:
        bundle_dir = tmp_path
        language_code = "unk"

    (tmp_path / "corpus.json").write_text(
        '{"data": [{"id": "a_b", "title": "A", "content": "x", "language": "Enawenê"},'
        ' {"id": "a-b", "title": "B", "content": "y", "language": "pt-BR"}]}')
    items = cv.load_corpus(Config)
    assert [i.file for i in items] == ["a-b.html", "a-b-2.html"]
    assert [i.row["_lang"] for i in items] == ["unk", "pt-BR"]


def test_bibliography_skips_empty_rows_and_unknown_years(tmp_path):
    class Config:
        bundle_dir = tmp_path

    (tmp_path / "bibliography.json").write_text(
        '{"data": [{"id": "e", "year": "????"}, {"id": "t", "title": "Título", "year": "????"}]}')
    refs = cv.load_bibliography(Config)
    assert [r["key"] for r in refs] == ["t"] and refs[0]["parts"] == [("i", "Título.")]


def test_other_sites_pictures_are_links_not_loads(project):
    set_theme(project, templates="v2", palette=BORORO)
    add_modules(project)
    rows = yaml.safe_load((project / "data" / "fauna.yaml").read_text())
    rows[0]["pic_link"] = "https://upload.wikimedia.org/x.jpg"
    (project / "data" / "fauna.yaml").write_text(yaml.safe_dump(rows, allow_unicode=True))
    assert build(project).exit_code == 0
    page = Path("site/pt/fauna/1-adugo.html").read_text()
    assert 'src="https://' not in page and 'href="https://upload.wikimedia.org/x.jpg"' in page
    assert "A. B." in page


def test_portuguese_content_is_tagged_on_other_locales(project):
    set_theme(project, templates="v2", palette=BORORO)
    add_modules(project)
    assert build(project).exit_code == 0
    page = Path("site/en/fauna/1-adugo.html").read_text()
    assert '<dd lang="pt-BR">Felino.</dd>' in page
    assert '<dd>Felino.</dd>' in Path("site/pt/fauna/1-adugo.html").read_text()


# ── P5 checks (Lighthouse, screenshots) ─────────────────────────────────

def test_script_controls_are_in_place_at_first_paint(project):
    """The filter box is shown by a class set in <head>, not revealed later by td.js (that
    moved the list down: Lighthouse CLS 0.34 on the Bororo encyclopedia)."""
    set_theme(project, templates="v2", palette=BORORO)
    add_modules(project)
    assert build(project).exit_code == 0
    page = Path("site/pt/fauna.html").read_text()
    head = page.split("</head>")[0]
    assert "className += ' td-js'" in head and head.index("td-js") < head.index("<script src=")
    assert 'class="td-filter td-needs-js"' in page and 'data-td-filter="items"' in page
    assert "hidden>" not in page.split('data-td-filter="items"')[1].split("</div>")[0][:400]
    css = next(Path("site/assets").glob("site.*.css")).read_text()
    assert "html:not(.td-js) .td-needs-js" in css
    assert ".td-entry__cite summary::after" in css  # "Como citar" reads as a control
