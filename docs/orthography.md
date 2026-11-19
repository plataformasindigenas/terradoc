# Alphabet, fonts and interface languages

A platform is used by speakers of the language. How words are ordered, which letters the
dictionary is browsed by, and whether every letter renders in one typeface are part of the
site's twist (see `packs.md`). They are set per site, and nothing here assumes Portuguese.

## The alphabet

```yaml
# terradoc.yaml
alphabet: [a, ã, e, ẽ, g, i, ĩ, k, l, m, mb, n, nd, ng, nj, o, õ, p, r, t, u, ũ, w, x, y]
```

- **Order matters.** It is the order of the dictionary's letter bar and of the entries under
  each letter. Letters after the first are compared by their position in the list, not by
  Portuguese collation.
- **Digraphs are letters.** `mbeku` is listed under MB, not M; the longest letter that matches
  wins.
- **Matching is NFC**, so a decomposed `e` + U+0303 counts as `ẽ`. Case is ignored.
- Spaces, hyphens, apostrophes, full stops and brackets are ignored when sorting. A leading `-`
  (an affix) is ignored for the letter too.
- **Without `alphabet`**, each word is listed under its first character (accents ignored),
  in plain order with accents ignored.

`terradoc check` rejects a letter listed twice, and warns about a headword whose first letter
is not in the alphabet. Warnings do not block publication; such a word is listed after the
alphabet's own letters.

Use the community's own published alphabet, and say where it comes from in `CULTURA.md`.

## Fonts

terradoc bundles two families, subset for each site at build time:
- the **text face**, for the language, Portuguese and IPA alike: Gentium (the default),
  Charis or Andika (`theme.font_vernacular: gentium|charis|andika`). Andika is made for
  learners; Charis's tilde reads as a macron at text sizes, which is why Gentium is the
  default. All three cover Latin, IPA, Greek and the combining marks;
- **Source Sans 3** for the interface (menus, labels, buttons).

`terradoc check` reports, as an error, any character the data uses that the text face lacks
in those ranges: the build would stop on it. Other scripts (a title in Malayalam in the
bibliography) come from the reader's own fonts. Sites cannot add fonts of their own.

## Interface languages

`locales: [pt, en]` lists the interface languages; each needs `locales/<code>.yaml`. Any code
works, including an indigenous language's own (`bor`, `mpu`), so the interface can be in the
language itself. Give it a label in `locale_labels`.

There is no language picker page. The site's root sends each visitor to the language they last
chose with the switch in the header, else to the first of their browser's languages that the
site has, else to `default_locale`.

`terradoc check` warns when a locale lacks keys that the default locale has, because those
labels would show empty. Content (definitions, articles) stays in the languages it was written
in; translating the interface is a separate decision from translating the content.
