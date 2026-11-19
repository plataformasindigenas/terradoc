"""v2 dictionary (REDESIGN-PLAN.md D18, D24, P2).

    <locale>/dictionary/index.html        search (script) + letter bar
    <locale>/dictionary/<letter>.html     every word of a letter (works without script)
    <locale>/dictionary/_.html            words that start outside the alphabet
    <locale>/dictionary/<id>-<slug>.html  one page per word (D24: no forwarding when it changes)
    <locale>/dictionary.html              forwards old v1 links (?entry=<id>, ?search=<q>)
    assets/search/dictionary.<hash>.json  the search index, fetched when search is used
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from terradoc.cross_linker import _slugify
from terradoc.orthography import Alphabet

# Part-of-speech values that only say "not classified yet": not shown.
PLACEHOLDER_POS = {"X", "LEX", ""}
OTHER = "_"
GLOSS_CHARS = 160
OPTIONAL = ("ipa", "pos", "definition", "example_sent", "scientific_name", "comment", "audio",
            "pic_link", "pic_credit", "wiki_link")  # in the search index and the letter lists


@dataclass
class Word:
    row: dict
    id: int
    entry: str
    homonym: int | None
    file: str              # file name inside dictionary/
    letter: str | None     # None: outside the alphabet
    key: tuple = ()
    prev: "Word | None" = None
    next: "Word | None" = None


@dataclass
class Letter:
    letter: str            # lower case, or OTHER
    label: str
    file: str
    words: list[Word] = field(default_factory=list)


def entry_slug(word: str) -> str:
    return _slugify(word).replace("_", "-")


def entry_file(entry_id, word: str) -> str:
    slug = entry_slug(word)
    return f"{entry_id}-{slug}.html" if slug else f"{entry_id}.html"


def script_slug(word: str) -> str:
    """What td-dict.js computes for a headword (NFKD, U+0300–U+036F removed, lower case,
    runs of other characters to "-"). The index carries the real slug only where they differ."""
    text = unicodedata.normalize("NFKD", word or "")
    text = "".join(c for c in text if not 0x300 <= ord(c) <= 0x36F).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def letter_file(letter: str, rank: int) -> str:
    if letter == OTHER:
        return "_.html"
    if all(unicodedata.category(c)[0] in "LM" for c in letter):
        return f"{letter}.html"
    return f"l{rank}.html"


def gloss(text) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= GLOSS_CHARS else text[:GLOSS_CHARS - 1].rstrip() + "…"


def load(config) -> tuple[list[Word], list[Letter]]:
    path = config.bundle_dir / "dictionary.json"
    if not path.is_file():
        return [], []
    rows = json.loads(path.read_text(encoding="utf-8"))["data"]
    alpha = Alphabet(config.alphabet)
    words = []
    for r in rows:
        for k in OPTIONAL:  # templates use StrictUndefined: every field the pages read exists
            r.setdefault(k, None)
        entry = str(r.get("entry") or "").strip()
        if not entry or r.get("id") in (None, ""):
            continue
        homonym = r.get("homonym")
        words.append(Word(r, r["id"], entry, int(homonym) if homonym not in (None, "") else None,
                          entry_file(r["id"], entry), alpha.first_letter(entry)))
    for w in words:
        w.key = (alpha.sort_key(w.entry), w.homonym or 0,
                 (0, w.id, "") if isinstance(w.id, int) else (1, 0, str(w.id)))
    words.sort(key=lambda w: w.key)
    for a, b in zip(words, words[1:]):
        a.next, b.prev = b, a
    letters: dict[str, Letter] = {}
    for w in words:
        k = w.letter or OTHER
        if k not in letters:
            rank = alpha.rank.get(k, len(alpha.letters))
            label = "…" if k == OTHER else k.upper() if len(k) == 1 else k[:1].upper() + k[1:]
            letters[k] = Letter(k, label, letter_file(k, rank))
        letters[k].words.append(w)
    ordered = sorted(letters.values(),
                     key=lambda L: (L.letter == OTHER, alpha.letter_order(L.letter)))
    return words, ordered


def letter_bar(config, letters: list[Letter]) -> list[dict]:
    """Every alphabet letter (greyed out when no word starts with it), then the others."""
    have = {L.letter: L for L in letters}
    alpha = Alphabet(config.alphabet)
    out = []
    names = alpha.letters or [L.letter for L in letters if L.letter != OTHER]
    for i, k in enumerate(names):
        L = have.get(k)
        label = k.upper() if len(k) == 1 else k[:1].upper() + k[1:]
        out.append({"letter": k, "label": label, "file": L.file if L else "", "count": len(L.words) if L else 0})
    if OTHER in have:
        out.append({"letter": OTHER, "label": "…", "file": have[OTHER].file, "count": len(have[OTHER].words)})
    return out


def search_index(words: list[Word]) -> bytes:
    """One row per word, in dictionary order: id, headword, homonym, the whole definition
    (searched in full, shortened on screen), IPA, scientific name, has audio, and the slug
    only when the page script would compute a different one (the page is <id>-<slug>.html)."""
    rows = []
    for w in words:
        slug = entry_slug(w.entry)
        row = [w.id, w.entry, w.homonym or 0, re.sub(r"\s+", " ", str(w.row.get("definition") or "")).strip(),
               str(w.row.get("ipa") or ""), str(w.row.get("scientific_name") or ""),
               1 if w.row.get("audio") else 0]
        if slug != script_slug(w.entry):
            row.append(slug)
        rows.append(row)
    data = {"v": 2, "fields": ["id", "entry", "homonym", "definition", "ipa", "scientific", "audio", "slug?"],
            "rows": rows}
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def write_index(words: list[Word], out: Path) -> str:
    data = search_index(words)
    name = f"assets/search/dictionary.{hashlib.sha256(data).hexdigest()[:10]}.json"
    (out / "assets" / "search").mkdir(parents=True, exist_ok=True)
    (out / name).write_bytes(data)
    return name


def keyboard_keys(config) -> list[str]:
    """The alphabet's letters that phone keyboards may lack (anything not plain a–z), then
    the site's extra keys."""
    keys = [L for L in Alphabet(config.alphabet).letters if not re.fullmatch(r"[a-z]+", L)]
    for k in config.keyboard:
        if k not in keys:
            keys.append(k)
    return keys


def folds_for_script(config) -> dict[str, str]:
    """search_folds, accent-free and lower case, as the page script applies them."""
    def plain(s):
        return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(c))
    return {plain(k): plain(v) for k, v in config.search_folds.items()}


def entry_context(config, w: Word, t, root: str, out: Path, related: list[dict]) -> dict:
    """Everything an entry page shows; optional blocks only when filled. `related`: pages
    of other modules linked to this word (content_v2.Links)."""
    r = w.row
    pos = str(r.get("pos") or "").strip()
    audio = []
    files = [a for a in (r.get("audio") or []) if isinstance(a, dict) and a.get("file_path")]
    for i, a in enumerate(files, start=1):
        if (out / "audio" / a["file_path"]).is_file():
            audio.append({"src": f"{root}audio/{a['file_path']}",
                          "type": "audio/webm" if a.get("format", "webm") == "webm" else "audio/wav",
                          "label": f"{t['ui_recording']} {i}" if len(files) > 1 else t["ui_recording"]})
    pic = str(r.get("pic_link") or "")
    host = ""
    if pic.startswith(("http://", "https://")):
        from urllib.parse import urlsplit
        host = urlsplit(pic).netloc.removeprefix("www.")
        host = "Wikimedia Commons" if host.endswith("wikimedia.org") else host
    elif pic:
        pic = root + pic.lstrip("/")
    return {
        "word": w, "row": r,
        "pos": t[f"pos_{pos}"] or pos if pos not in PLACEHOLDER_POS else "",
        "audio": audio, "related": related, "picture": pic, "picture_host": host,
        "picture_credit": str(r.get("pic_credit") or ""),
        "wiki": str(r.get("wiki_link") or ""),
    }
