"""Markdown and HTML utilities for terradoc."""

import html as html_lib
import re
from html.parser import HTMLParser

from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin

HTML_TAG_RE = re.compile(r"<\s*[a-zA-Z][^>]*>")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {
            "p", "br", "hr", "li", "tr", "th", "td",
            "h1", "h2", "h3", "h4", "h5", "h6",
        }:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def get_text(self) -> str:
        text = html_lib.unescape("".join(self.parts))
        return re.sub(r"\\s+", " ", text).strip()


def build_markdown_renderer() -> MarkdownIt:
    """Create a configured MarkdownIt renderer."""
    md = MarkdownIt("gfm-like", {"html": False, "linkify": False})
    md.use(footnote_plugin)
    return md


def assert_no_html(content_md: str, entry_id: str) -> None:
    """Raise ValueError if markdown content contains HTML tags."""
    if content_md and HTML_TAG_RE.search(content_md):
        raise ValueError(
            f"Entry {entry_id}: content_md contains HTML tags; use markdown only"
        )


def html_to_text(html: str) -> str:
    """Strip HTML tags and return plain text."""
    if not html:
        return ""
    parser = _TextExtractor()
    parser.feed(html)
    return parser.get_text()


def process_wikilinks(content_md: str, all_ids: set) -> str:
    """Convert [[wikilink]] and [[target|Display]] to markdown links."""
    def _replace_wikilink(match):
        target_raw = match.group(1).strip()
        display = match.group(2)
        if display:
            display = display.strip()
        else:
            display = target_raw

        target = target_raw.lower().replace(" ", "-")

        if target in all_ids:
            return f"[{display}]({target}.html)"
        else:
            print(f"  WARNING: broken wikilink [[{target_raw}]] — no entry with id '{target}'")
            return f'<span class="broken-link">{display}</span>'

    return re.sub(r"\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]", _replace_wikilink, content_md)


def build_category_tree(entries: list[dict]) -> dict:
    """Build a nested category tree from hierarchical category paths.

    Returns a dict like:
    {"sociedade": {"_count": 5, "organização-social": {"_count": 3}}}
    """
    tree: dict = {}
    for entry in entries:
        for cat in entry.get("categories") or []:
            parts = cat.split("/")
            node = tree
            for part in parts:
                if part not in node:
                    node[part] = {"_count": 0}
                node[part]["_count"] += 1
                node = node[part]
    return tree


def generate_toc(content_html: str, entry_id: str) -> tuple[str, str]:
    """Generate a table of contents from h3/h4 headings and add IDs.

    Returns (toc_html, modified_content_html).
    """
    heading_re = re.compile(r"<h([34])([^>]*)>([^<]+)</h\1>", re.IGNORECASE)
    headings = []
    index = 0

    for match in heading_re.finditer(content_html):
        level = match.group(1)
        text = match.group(3).strip()
        heading_id = f"{entry_id}-section-{index}"
        headings.append({"level": level, "text": text, "id": heading_id})
        index += 1

    if len(headings) < 2:
        return "", content_html

    toc_parts = ['<div class="toc"><div class="toc-title">']
    toc_parts.append("</div><ul class='toc-list'>")
    for i, h in enumerate(headings):
        cls = ' class="toc-h4"' if h["level"] == "4" else ""
        toc_parts.append(
            f'<li{cls}><a href="#{h["id"]}">{i + 1}. {h["text"]}</a></li>'
        )
    toc_parts.append("</ul></div>")
    toc_html = "".join(toc_parts)

    index = 0

    def _add_id(match):
        nonlocal index
        level = match.group(1)
        attrs = match.group(2)
        text = match.group(3)
        heading_id = f"{entry_id}-section-{index}"
        index += 1
        return f'<h{level}{attrs} id="{heading_id}">{text}</h{level}>'

    modified_content = heading_re.sub(_add_id, content_html)

    return toc_html, modified_content
