"""Pages: a site's own Markdown pages (0.24.0).

    data/pages/<locale>/<slug>.md       front matter + Markdown

Front matter:
    title: "Plataformas"                required
    description: "..."                  optional (meta description; lede under the title)
    nav: 2                              optional: listed in the menu, in this order
    aliases: [plataformas.html]         optional: old addresses (from the site root) that
                                        forward here; terradoc writes the forwarding pages

A page is published at `<locale>/<slug>.html`. Every slug must exist in every locale, since
the language switch keeps the address and changes only the locale. `home.md` is not a page of
its own: it is shown on the home page under the hero.

Markdown as in encyclopedia articles (no HTML). Pictures `![what it shows](images/x.jpg
"credit")` come from static/ and are published as responsive WebP; a list in which every item
has a picture is laid out as cards (team, partners). `{#id}` on the line before a heading sets
its anchor.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from terradoc.config import TerradocConfig

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")
ALIAS_RE = re.compile(r"^(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+\.html$")
HOME = "home"
FRONT_KEYS = {"title", "description", "nav", "aliases"}


@dataclass
class Page:
    locale: str
    slug: str
    source: Path
    title: str = ""
    description: str = ""
    nav: int | None = None
    aliases: list[str] = field(default_factory=list)
    body: str = ""
    html: str = ""

    @property
    def path(self) -> str:
        return f"{self.locale}/{self.slug}.html"


def pages_dir(config: TerradocConfig) -> Path:
    return config.data_dir / "pages"


def reserved_slugs(config: TerradocConfig) -> set[str]:
    """Names a page cannot take: the module pages and the files terradoc writes itself."""
    return set(config.modules) | {"index", "about", "404", "offline", "specimen", "dictionary"}


FRONT_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)^---[ \t]*(?:\r?\n|\Z)", re.S | re.M)


def split_front_matter(text: str) -> tuple[dict, str]:
    """Front matter between two lines that are exactly `---` (a `---` inside a value is text)."""
    m = FRONT_RE.match(text)
    if not m:
        if text.startswith("---"):
            raise ValueError("front matter opened with --- but not closed by a line with ---")
        return {}, text
    data = yaml.safe_load(m.group(1))
    if data is not None and not isinstance(data, dict):
        raise ValueError("front matter must be a mapping")
    return data or {}, text[m.end():].lstrip("\n")


def load(config: TerradocConfig) -> tuple[list[Page], list[tuple[str, str]]]:
    """Every page of every locale, and the problems found as (file, message). A page with a
    problem is left out (check reports it as an error, so the build stops before this)."""
    root = pages_dir(config)
    pages: list[Page] = []
    problems: list[tuple[str, str]] = []
    if not root.is_dir():
        return pages, problems
    rel = lambda p: p.relative_to(config.base_dir).as_posix()  # noqa: E731
    reserved = reserved_slugs(config)
    for path in sorted(root.rglob("*")):
        if path.is_dir() or path.name == "README.md":
            continue
        parts = path.relative_to(root).parts
        if len(parts) != 2 or path.suffix != ".md" or parts[0] not in config.locales:
            problems.append((rel(path), "pages live in data/pages/<locale>/<slug>.md, "
                                        f"with <locale> one of {', '.join(config.locales)}"))
            continue
        slug = path.stem
        if not SLUG_RE.match(slug):
            problems.append((rel(path), "a page name uses a-z, 0-9 and '-' (it becomes the address)"))
            continue
        if slug in reserved:
            problems.append((rel(path), f"'{slug}' is a name terradoc uses itself; rename the page"))
            continue
        try:
            fm, body = split_front_matter(path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, ValueError, UnicodeDecodeError) as exc:
            problems.append((rel(path), f"front matter cannot be read: {exc}"))
            continue
        unknown = sorted(str(k) for k in fm if k not in FRONT_KEYS)
        if unknown:
            problems.append((rel(path), f"unknown front matter key(s): {', '.join(unknown)} "
                                        f"(known: {', '.join(sorted(FRONT_KEYS))})"))
        title = fm.get("title")
        if slug != HOME and (not isinstance(title, str) or not title.strip()):
            problems.append((rel(path), "a page needs a title"))
            continue
        nav = fm.get("nav")
        if nav is not None and (isinstance(nav, bool) or not isinstance(nav, int)):
            problems.append((rel(path), "nav must be a whole number (the order in the menu)"))
            nav = None
        aliases = fm.get("aliases") or []
        if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
            problems.append((rel(path), "aliases must be a list of addresses, e.g. [plataformas.html]"))
            aliases = []
        bad = [a for a in aliases if not ALIAS_RE.match(a) or {".", ".."} & set(a.split("/"))
               or a.startswith("assets/")]
        if bad:
            problems.append((rel(path), "an alias is a path from the site root ending in .html "
                                        f"(no '.' or '..' parts, not under assets/): {', '.join(bad)}"))
            aliases = [a for a in aliases if a not in bad]
        if slug == HOME and (nav is not None or aliases):
            problems.append((rel(path), "home.md is shown on the home page: no nav or aliases"))
        pages.append(Page(parts[0], slug, path, str(title or "").strip(),
                          str(fm.get("description") or "").strip(), nav, aliases, body))

    # The language switch keeps the address: a page must exist in every locale.
    by_slug: dict[str, set[str]] = {}
    for p in pages:
        by_slug.setdefault(p.slug, set()).add(p.locale)
    for slug, locs in sorted(by_slug.items()):
        missing = [loc for loc in config.locales if loc not in locs]
        if missing:
            problems.append((f"data/pages/{{{','.join(missing)}}}/{slug}.md",
                             f"page '{slug}' is missing in {', '.join(missing)} (every locale needs it)"))

    # Aliases must not shadow a page or each other.
    owners: dict[str, str] = {}
    paths = {p.path for p in pages}
    for p in pages:
        for a in p.aliases:
            if a in paths or a in owners or a in GENERATED:
                problems.append((rel(p.source), f"alias '{a}' is already an address of the site"))
            owners.setdefault(a, rel(p.source))
    return pages, problems


GENERATED = {"index.html", "404.html", "offline.html", "specimen.html"}


def local_images(page: Page) -> list[tuple[str, str]]:
    """(path from static/, credit) of each local picture a page shows."""
    from terradoc.markdown_utils import build_markdown_renderer

    out = []
    for tok in build_markdown_renderer().parse(page.body):
        for child in tok.children or []:
            if child.type == "image":
                src = str(child.attrGet("src") or "")
                if src and not src.startswith(("http://", "https://", "//", "data:")):
                    out.append((src, str(child.attrGet("title") or "").strip()))
    return out


def image_sources(page: Page) -> list[str]:
    """Local picture paths a page shows (as written: from static/)."""
    return [src for src, _ in local_images(page)]


def external_images(page: Page) -> list[str]:
    from terradoc.markdown_utils import build_markdown_renderer

    return [str(c.attrGet("src")) for tok in build_markdown_renderer().parse(page.body)
            for c in tok.children or [] if c.type == "image"
            and str(c.attrGet("src") or "").startswith(("http://", "https://", "//", "data:"))]


def _renderer():
    from mdit_py_plugins.attrs import attrs_block_plugin

    from terradoc.markdown_utils import build_markdown_renderer

    md = build_markdown_renderer()
    md.use(attrs_block_plugin)

    def image(self, tokens, idx, options, env):
        tok = tokens[idx]
        src = str(tok.attrGet("src") or "")
        alt = html.escape(self.renderInlineAsText(tok.children or [], options, env), quote=True)
        credit = str(tok.attrGet("title") or "").strip()
        d = env["pictures"].get(src)
        if d is None:  # check reports it; never load another site's file with the page
            return alt
        root = env["root"]
        out = (f'<span class="td-pic"><picture><source type="image/webp" srcset="{d.srcset(root)}" '
               f'sizes="(min-width: 48em) 40rem, 100vw"><img src="{html.escape(root + d.src, quote=True)}" '
               f'width="{d.width}" height="{d.height}" alt="{alt}" loading="lazy" decoding="async"></picture>')
        if credit:
            out += f'<small class="td-pic__credit">{html.escape(env["photo"])}: {html.escape(credit)}</small>'
        return out + "</span>"

    md.add_render_rule("image", image)
    return md


def render(page: Page, pictures: dict, root: str, photo_label: str) -> str:
    """The page's HTML. `pictures`: static path -> images.Derived; `root`: the prefix from
    the page back to the site root."""
    md = _renderer()
    tokens = md.parse(page.body)
    for tok in tokens:  # {#id} only: no other attributes from the text
        if tok.attrs:
            keep = {k: v for k, v in tok.attrs.items() if k == "id" and re.match(r"^[A-Za-z][\w-]*$", str(v))}
            tok.attrs = keep
    _mark_cards(tokens)
    return md.renderer.render(tokens, md.options, {"pictures": pictures, "root": root, "photo": photo_label})


def _mark_cards(tokens) -> None:
    """A bullet list whose every item shows a picture becomes a card grid."""
    for i, tok in enumerate(tokens):
        if tok.type != "bullet_list_open":
            continue
        level, items, with_pic, j = tok.level, 0, 0, i + 1
        has_pic = False
        while j < len(tokens) and not (tokens[j].type == "bullet_list_close" and tokens[j].level == level):
            t = tokens[j]
            if t.type == "list_item_open" and t.level == level + 1:
                items += 1
                has_pic = False
            elif t.type == "inline" and any(c.type == "image" for c in t.children or []):
                has_pic = True
            elif t.type == "list_item_close" and t.level == level + 1 and has_pic:
                with_pic += 1
            j += 1
        if items and items == with_pic:
            tok.attrSet("class", "td-pagecards")


def alias_target(alias: str, target: str) -> str:
    """Relative address from the forwarding page at `alias` to `target` (both from the site
    root), so a preview forwards inside the preview."""
    return "../" * alias.count("/") + target
