"""v2 pages other than the dictionary (REDESIGN-PLAN.md P3).

    <locale>/encyclopedia.html              all articles; category chips and a filter (script)
    <locale>/encyclopedia/<id>.html         one article (same address as v1)
    <locale>/fauna.html, ethnobotany.html   names in the language first, grouped
    <locale>/fauna/<id>-<slug>.html         one animal / plant
    <locale>/ethnobotany/<id>-<slug>.html
    <locale>/bibliography.html              every reference, anchors #ref-<key>
    <locale>/videos.html                    YouTube links with local posters, or local files
    <locale>/corpus.html, corpus/<id>.html  texts
    <locale>/about.html                     the site's about_* strings

Old v1 links keep working: `fauna.html?search=`, `encyclopedia.html?category=` are read by
td.js's list filter, and article addresses did not change.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote, urlsplit

from terradoc.dictionary_v2 import entry_slug


@dataclass
class Item:
    kind: str                 # fauna | ethnobotany | encyclopedia | corpus
    id: object
    row: dict
    file: str                 # file name inside <kind>/
    name: str                 # what the page is called
    vernacular: bool          # name is in the language (lang attribute)
    group: str = ""
    prev: "Item | None" = None
    next: "Item | None" = None
    dictionary: list = field(default_factory=list)   # [(href from the item's page, word)]


def read_rows(config, name: str) -> list[dict]:
    path = config.bundle_dir / f"{name}.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("data", []) if isinstance(data, dict) else data


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def plain_markdown(text) -> str:
    """Summaries are shown as text: [label](url) keeps the label, *emphasis* its words."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", clean(text))
    return re.sub(r"(\*\*|\*|__)(\S(?:.*?\S)?)\1", r"\2", text)


def fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def item_file(item_id, name: str) -> str:
    slug = entry_slug(name)
    return f"{item_id}-{slug}.html" if slug else f"{item_id}.html"


def humanize(slug: str) -> str:
    text = slug.replace("-", " ").replace("_", " ").strip()
    return text[:1].upper() + text[1:]


def link_chain(items: list[Item]) -> None:
    for a, b in zip(items, items[1:]):
        a.next, b.prev = b, a


# ── LaTeX left in BibTeX fields (\'a, \~a, \c{c}, {\"o}, --) ─────────────────

_ACCENTS = {"'": "\u0301", "`": "\u0300", "^": "\u0302", "~": "\u0303", '"': "\u0308",
            "c": "\u0327", "=": "\u0304", ".": "\u0307", "u": "\u0306", "v": "\u030C", "H": "\u030B"}


def delatex(text) -> str:
    text = str(text or "")
    if "\\" not in text and "{" not in text and "--" not in text:
        return text

    def accent(m):
        mark, letter = m.group(1), m.group(2) or m.group(3)
        if letter == "\\i":
            letter = "i"
        return unicodedata.normalize("NFC", letter + _ACCENTS[mark])
    text = re.sub(r"\\([`'^~\"=.])\s*(?:\{(\\i|\w)\}|(\\i|\w))", accent, text)
    text = re.sub(r"\\([cuvH])\s*(?:\{(\\i|\w)\}|\s(\w))", accent, text)
    text = text.replace("\\&", "&").replace("\\%", "%").replace("\\_", "_").replace("\\$", "$")
    text = text.replace("---", "\u2014").replace("--", "\u2013").replace("~", "\u00a0")
    return re.sub(r"[{}]", "", text)


# ── loaders ──────────────────────────────────────────────────────────────────

def load_species(config, kind: str) -> list[Item]:
    """Fauna or ethnobotany: grouped (fauna by the people's classification, plants by
    family), names in the language first; an entry without one uses its Portuguese name."""
    items = []
    for r in read_rows(config, kind):
        if r.get("id") in (None, ""):
            continue
        native = clean(r.get("name_indigenous"))
        name = native or clean(r.get("name_portuguese")) or clean(r.get("scientific_name")) or str(r["id"])
        group = clean(r.get("classification_indigenous") if kind == "fauna" else r.get("family"))
        items.append(Item(kind, r["id"], r, item_file(r["id"], name), name, bool(native), group))
    items.sort(key=lambda i: (i.group == "", fold(i.group), fold(i.name), str(i.id)))
    link_chain(items)
    return items


MAX_GROUPS = 12


def groups(items: list[Item], uncategorized: str) -> list[dict]:
    """Sections of a species list. With more than MAX_GROUPS groups (Enawenê-Nawê animal
    classes, plant families) a menu of them would be longer than the list helps: one
    list A–Z instead, each item showing its group."""
    if len({i.group for i in items}) > MAX_GROUPS:
        flat = sorted(items, key=lambda i: (fold(i.name), str(i.id)))
        return [{"key": "", "label": "", "vernacular": False, "items": flat, "anchor": "g1", "flat": True}]
    out: dict[str, dict] = {}
    for i in items:
        g = out.setdefault(i.group, {"key": i.group, "label": i.group or uncategorized,
                                     "vernacular": bool(i.group) and i.kind == "fauna", "items": [],
                                     "flat": False})
        g["items"].append(i)
    for n, g in enumerate(out.values(), start=1):
        g["anchor"] = f"g{n}"
    return list(out.values())


def load_encyclopedia(config) -> list[Item]:
    items = []
    for r in read_rows(config, "encyclopedia"):
        aid = str(r.get("id") or "")
        if not aid or "/" in aid or aid.startswith("."):
            continue
        r["abstract"] = plain_markdown(r.get("abstract"))
        items.append(Item("encyclopedia", aid, r, f"{aid}.html", clean(r.get("title")) or aid, False))
    items.sort(key=lambda i: (fold(i.name), i.id))
    link_chain(items)
    return items


def top_categories(items: list[Item]) -> list[dict]:
    counts: dict[str, int] = {}
    for i in items:
        for top in {str(c).split("/")[0] for c in i.row.get("categories") or [] if c}:
            counts[top] = counts.get(top, 0) + 1
    return [{"key": k, "count": n} for k, n in sorted(counts.items(), key=lambda kv: (fold(kv[0]), kv[0]))]


LANG_TAG = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


def load_corpus(config) -> list[Item]:
    """Texts; `_lang` is the row's `language` when it is a language tag, else the site's
    language (the field often holds a name, "Makurap"). File names are unique."""
    items, used = [], set()
    for r in read_rows(config, "corpus"):
        cid = str(r.get("id") or "")
        if not cid or not clean(r.get("content")):
            continue
        name = clean(r.get("title")) or cid
        stem = entry_slug(cid) or "texto"
        file, n = f"{stem}.html", 1
        while file in used:
            n += 1
            file = f"{stem}-{n}.html"
        used.add(file)
        lang = clean(r.get("language"))
        r["_lang"] = lang if LANG_TAG.match(lang) else config.language_code
        r["description"] = plain_markdown(r.get("description"))
        items.append(Item("corpus", cid, r, file, name, True))
    link_chain(items)
    return items


# ── bibliography ─────────────────────────────────────────────────────────────

NOISE_NOTE = re.compile(r"^source list item", re.I)


def _sentence(text: str) -> str:
    text = text.strip()
    return text if not text or text[-1] in ".?!" else text + "."


def bib_entry(r: dict) -> dict:
    """One reference, author-year, LaTeX removed. `parts`: (kind, text) in order, kind ""
    (plain), "i" (italic) or "thesis" (the page puts "Tese (doutorado)" before the text)."""
    f = {k: clean(delatex(r.get(k))) for k in ("author", "year", "title", "journal", "volume", "number",
                                               "pages", "booktitle", "editor", "publisher", "address",
                                               "school", "note", "doi", "url", "type")}
    names = [a.strip() for a in re.split(r"\s+and\s+", f["author"]) if a.strip()]
    if len(names) > 1 and names[-1].lower() == "others":
        names[-1] = "et al."
    authors = "; ".join(names)
    container = ""
    if f["journal"]:
        container = f["journal"] + (f" {f['volume']}" if f["volume"] else "") + \
            (f"({f['number']})" if f["number"] else "") + (f": {f['pages']}" if f["pages"] else "")
    elif f["booktitle"]:
        container = (f"In: {f['editor']} (org.), " if f["editor"] else "In: ") + f["booktitle"] + \
            (f", p. {f['pages']}" if f["pages"] else "")
    place = ", ".join(x for x in (f["address"], f["publisher"] or f["school"]) if x)
    thesis = f["type"] if f["type"] in ("phdthesis", "mastersthesis") else ""
    italic_title = not container
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", f["doi"])
    link = f"https://doi.org/{doi}" if doi else (f["url"] if f["url"].startswith(("http://", "https://")) else "")
    year = "" if set(f["year"]) <= {"?", ""} else f["year"]
    head = authors + (f" ({year})" if year else "")
    parts = [("", _sentence(head))] if head else []
    if f["title"]:
        parts.append(("i" if italic_title else "", _sentence(f["title"])))
    if container:
        parts.append(("", _sentence(container)))
    if thesis:
        parts.append(("thesis", _sentence(", " + place) if place else "."))
    elif place:
        parts.append(("", _sentence(place)))
    note = "" if NOISE_NOTE.match(f["note"]) else f["note"]
    if note:
        parts.append(("", _sentence(note)))
    return {"key": str(r.get("id") or ""), "authors": authors, "year": year, "title": f["title"].rstrip("."),
            "thesis": thesis, "parts": parts, "link": link,
            "sort": (fold(authors or f["title"]), f["year"], fold(f["title"]))}


def load_bibliography(config) -> list[dict]:
    refs = [bib_entry(r) for r in read_rows(config, "bibliography")
            if r.get("id") and (clean(r.get("author")) or clean(r.get("title")))]
    refs.sort(key=lambda b: b["sort"])
    return refs


# ── videos ───────────────────────────────────────────────────────────────────

AUDIO_EXT = {".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".flac"}
YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def load_videos(config, out: Path) -> list[dict]:
    """A video is shown when it can be played: a local file (played in the page; a sound
    player for files under audio/ or with an audio extension) or a
    YouTube id (a poster linking to YouTube; no embedded player, no third-party requests
    until the reader chooses to go)."""
    videos = []
    for r in read_rows(config, "videos"):
        src = str(r.get("source_url") or "")
        local = src if src and not src.startswith(("http://", "https://", "/")) and ".." not in src \
            and (out / src).is_file() else ""
        audio = bool(local) and (local.startswith("audio/") or Path(local).suffix.lower() in AUDIO_EXT)
        yid = str(r.get("youtube_id") or "")
        youtube = f"https://www.youtube.com/watch?v={yid}" if YOUTUBE_ID.match(yid) and not local else ""
        if not (local or youtube):
            continue
        videos.append({"title": clean(r.get("title")), "category": clean(r.get("category")),
                       "description": plain_markdown(r.get("description")), "language": clean(r.get("language")),
                       "duration": clean(r.get("duration")), "local": local, "audio": audio, "youtube": youtube,
                       "thumbnail": str(r.get("thumbnail") or ""), "poster": None})
    return videos


def video_groups(videos: list[dict]) -> list[dict]:
    out: dict[str, list] = {}
    for v in videos:
        out.setdefault(v["category"], []).append(v)
    return [{"label": k[:1].upper() + k[1:], "videos": vs} for k, vs in out.items()]


# ── links between modules ────────────────────────────────────────────────────

def picture_parts(link: str) -> tuple[str, str]:
    """(local path under static/, external URL): exactly one is set for a usable link."""
    link = str(link or "").strip()
    if link.startswith(("http://", "https://")):
        return "", link
    if not link or link.startswith("/") or ".." in link.split("/"):
        return "", ""
    return link, ""


def host_of(url: str) -> str:
    host = urlsplit(url).netloc.removeprefix("www.")
    return "Wikimedia Commons" if host.endswith("wikimedia.org") else host


def rewrite_article_html(html: str, root: str) -> str:
    """Article HTML from Markdown: images written as `images/x.jpg` are site-root paths."""
    return re.sub(r'(<img\b[^>]*?\bsrc=")(?!https?:|/|\.\./|data:)', lambda m: m.group(1) + root, html)


# ── links between modules, both ways ─────────────────────────────────────────

KIND_ORDER = ("dictionary", "fauna", "ethnobotany", "encyclopedia")
LINK_FIELDS = {"_linked_dictionary": "dictionary", "_linked_fauna": "fauna",
               "_linked_ethnobotany": "ethnobotany", "_linked_encyclopedia": "encyclopedia"}


class Links:
    """Every page that exists (kind, id) and the links between them. A link recorded on
    one side (a word's `_linked_fauna`, an animal's `_linked_dictionary`) is shown on both
    pages; a link to a page that is not built is dropped."""

    def __init__(self):
        self.pages: dict[tuple[str, str], dict] = {}
        self.edges: dict[tuple[str, str], set] = {}

    def add(self, kind: str, item_id, file: str, name: str, vernacular: bool, homonym=None) -> None:
        self.pages[(kind, str(item_id))] = {"kind": kind, "file": file, "name": name,
                                            "vernacular": vernacular, "homonym": homonym}

    def add_rows(self, kind: str, rows) -> None:
        for item_id, row in rows:
            for key, other in LINK_FIELDS.items():
                for target in row.get(key) or []:
                    if isinstance(target, dict) and target.get("id") not in (None, ""):
                        a, b = (kind, str(item_id)), (other, str(target["id"]))
                        self.edges.setdefault(a, set()).add(b)
                        self.edges.setdefault(b, set()).add(a)

    def href(self, kind: str, item_id) -> str:
        """From a page one level below the locale directory (every detail page)."""
        page = self.pages.get((kind, str(item_id)))
        return f"../{kind}/{quote(page['file'])}" if page else ""

    def related(self, kind: str, item_id, labels: dict[str, str]) -> list[dict]:
        out = []
        for k, i in self.edges.get((kind, str(item_id)), ()):
            page = self.pages.get((k, i))
            if page and (k, i) != (kind, str(item_id)):
                out.append({**page, "label": labels.get(k, k), "href": self.href(k, i)})
        out.sort(key=lambda p: (KIND_ORDER.index(p["kind"]) if p["kind"] in KIND_ORDER else 9,
                                fold(p["name"]), p["homonym"] or 0, p["file"]))
        return out
