"""The render step and shared behaviour kept from the v1 test files when v1 was removed
(0.23.0): number formatting, robots.txt, unknown theme settings, template sets, galleries."""

import tempfile
from pathlib import Path

import yaml

from terradoc.build_v2 import format_number
from terradoc.render import write_robots_txt
from tests.test_orthography import build, project, run  # noqa: F401  (fixture)


def set_theme(project: Path, **theme):
    cfg = project / "terradoc.yaml"
    data = yaml.safe_load(cfg.read_text())
    data.setdefault("theme", {}).update(theme)
    cfg.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def test_number_filter():
    """From test_build_site.py (v1): same cases."""
    assert format_number(4865, "pt") == "4.865"
    assert format_number(4865, "en") == "4,865"
    assert format_number(7.0, "pt") == "7,0"
    assert format_number(7.0, "en-GB") == "7.0"
    assert format_number(461, "bor") == "461"
    assert format_number("n/a", "pt") == "n/a"


def test_robots_names_the_sitemap_only_with_an_absolute_address():
    with tempfile.TemporaryDirectory() as tmp:
        docs = Path(tmp)
        write_robots_txt(docs)
        assert "Sitemap" not in (docs / "robots.txt").read_text()
        write_robots_txt(docs, "https://x.terradoc.org/")
        assert "Sitemap: https://x.terradoc.org/sitemap.xml" in (docs / "robots.txt").read_text()


def test_unknown_theme_key_is_an_error(project):
    """From test_motifs.py (v1), with a v2 key."""
    set_theme(project, hero_creditt="A. B.")  # misspelt
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert result.exit_code != 0
    assert "theme.hero_creditt: unknown setting (did you mean 'hero_credit'?)" in result.output
    assert build(project).exit_code != 0


def test_unavailable_template_set_is_refused(project):
    """From test_motifs.py (v1)."""
    result = run("render", "-c", str(project / "terradoc.yaml"), "--out", "site", "--templates", "v9")
    assert result.exit_code != 0
    assert "template set 'v9' is not available" in result.output
    set_theme(project, templates="v9")
    result = run("check", "-c", str(project / "terradoc.yaml"))
    assert result.exit_code != 0
    assert "'v9' is not available" in result.output


def test_explicit_v2_is_still_accepted(project):
    set_theme(project, templates="v2")
    result = build(project)
    assert result.exit_code == 0, result.output


def test_article_gallery(project):
    """An article's gallery images (front matter) appear on its v2 page, credited, and are
    pictures from static/, never other sites' files loaded with the page."""
    from PIL import Image

    images = project / "static" / "images"
    for n in range(4):
        Image.new("RGB", (640, 480), (n * 40, 90, 120)).save(images / f"g{n}.jpg")
    pics = "".join(f"  - url: images/g{n}.jpg\n    alt: Foto {n}\n    credit: A. B.\n" for n in range(4))
    pics += "  - url: https://upload.wikimedia.org/x.jpg\n    credit: C. D.\n"
    (project / "data" / "encyclopedia" / "casa.md").write_text(
        "---\nid: casa\ntitle: Casa\ncategories: [cultura]\nimages:\n" + pics + "---\n\nTexto.\n",
        encoding="utf-8")
    result = build(project)
    assert result.exit_code == 0, result.output
    page = (Path("site") / "pt" / "encyclopedia" / "casa.html").read_text()
    assert "td-gallery" in page  # the first picture leads, the others form the gallery
    for n in range(4):
        assert f'alt="Foto {n}"' in page
    assert page.count("<picture>") == 4 and "A. B." in page
    assert 'href="https://upload.wikimedia.org/x.jpg"' in page and 'src="https://' not in page
