"""End-to-end tests: entry gallery (4+ images) and landing-page spotlight card."""

from pathlib import Path

from click.testing import CliRunner

from terradoc.cli import main


def _entry(id_, n_images):
    images = "".join(
        f"- url: images/{id_}_{i}.jpg\n  alt: Picture {i}\n  credit: Someone\n"
        for i in range(n_images)
    )
    return (
        f"---\nid: {id_}\ntitle: {id_.title()}\nvariants: []\nabstract: test\n"
        f"categories: []\ndate: '2026-01-01'\nurl: ''\n"
        f"images:\n{images}" if n_images else
        f"---\nid: {id_}\ntitle: {id_.title()}\nvariants: []\nabstract: test\n"
        f"categories: []\ndate: '2026-01-01'\nurl: ''\nimages: []\n"
    ) + "examples: []\nentry_type: ''\ninfobox: {}\nreferences: []\nsee_also: []\n---\n\nBody.\n"


def _build(spotlight):
    runner = CliRunner()
    result = runner.invoke(main, ["init", "demo"])
    assert result.exit_code == 0
    enc = Path("demo/data/encyclopedia")
    enc.mkdir(parents=True, exist_ok=True)
    (enc / "many.md").write_text(_entry("many", 4))
    (enc / "few.md").write_text(_entry("few", 3))
    if spotlight:
        with open("demo/locales/pt.yaml", "a", encoding="utf-8") as f:
            f.write(
                '\nindex_spotlight_title: "Destaque"\n'
                'index_spotlight_desc: "Descricao do destaque"\n'
                'index_spotlight_href: "encyclopedia/many.html"\n'
                'index_spotlight_image: "images/spot.jpg"\n'
            )
    build = runner.invoke(main, ["build", "-c", "demo/terradoc.yaml"])
    assert build.exit_code == 0, build.output
    return Path("demo/docs/pt")


def test_gallery_only_for_entries_with_four_or_more_images():
    runner = CliRunner()
    with runner.isolated_filesystem():
        pt = _build(spotlight=False)
        many = (pt / "encyclopedia" / "many.html").read_text()
        few = (pt / "encyclopedia" / "few.html").read_text()
        assert many.count('class="entry-gallery-btn"') == 4
        assert 'id="entry-lightbox"' in many
        assert 'class="entry-gallery-btn"' not in few
        assert 'id="entry-lightbox"' not in few


def test_spotlight_card_only_when_locale_keys_present():
    runner = CliRunner()
    with runner.isolated_filesystem():
        pt = _build(spotlight=True)
        index = (pt / "index.html").read_text()
        assert 'data-section="spotlight"' in index
        assert 'href="encyclopedia/many.html"' in index
        assert "images/spot.jpg" in index
    with runner.isolated_filesystem():
        pt = _build(spotlight=False)
        assert 'data-section="spotlight"' not in (pt / "index.html").read_text()
