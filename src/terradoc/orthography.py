"""A site's alphabet in Python: first letters and sort order, as the dictionary pages use them.

Same rules as the v1 page script (ALPHA in templates/dictionary.html.j2) and `check`:
letters may be digraphs (longest match first, after NFC and lower-casing); a letter outside
the alphabet whose plain form is in it (ó when the alphabet has o) counts as that letter;
other characters sort after every letter, by code point; spaces, hyphens, apostrophes,
dots and brackets are ignored for sorting. Without an alphabet, the first letter is the
word's first character with accents removed, and words sort by their accent-folded form.
"""
from __future__ import annotations

import re
import unicodedata

_IGNORED = re.compile(r"[\s\-'’.()]")


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").lower()


def _plain(ch: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c))


class Alphabet:
    def __init__(self, letters: list[str]):
        self.letters: list[str] = []
        self.rank: dict[str, int] = {}
        for letter in letters:
            k = _norm(letter)
            if k and k not in self.rank:
                self.rank[k] = len(self.letters)
                self.letters.append(k)
        self._by_length = sorted(self.letters, key=len, reverse=True)

    def _match(self, w: str, i: int) -> tuple[str, int] | None:
        for letter in self._by_length:
            if w.startswith(letter, i):
                return letter, len(letter)
        base = _plain(w[i])
        return (base, 1) if base and base in self.rank else None

    def first_letter(self, word: str) -> str | None:
        """The word's letter (lower case), or None when it starts outside the alphabet."""
        w = _norm(word).lstrip("-").strip()
        if not w:
            return None
        if not self.letters:
            base = _plain(w[0])
            return base if base.isalpha() else None
        m = self._match(w, 0)
        return m[0] if m else None

    def sort_key(self, word: str) -> tuple:
        w = _norm(word).lstrip("-")
        if not self.letters:
            return tuple(ord(c) for c in _plain(w) if not _IGNORED.match(c))
        out, i, n = [], 0, len(self.letters)
        while i < len(w):
            m = self._match(w, i)
            if m:
                out.append(self.rank[m[0]])
                i += m[1]
                continue
            if not _IGNORED.match(w[i]):
                out.append(n + ord(w[i]))
            i += 1
        return tuple(out)

    def letter_order(self, letter: str) -> tuple:
        k = _norm(letter)
        return (self.rank[k],) if k in self.rank else (len(self.letters) + sum(map(ord, k)),)
