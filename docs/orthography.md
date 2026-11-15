# Alphabet, fonts and interface languages

A platform is used by speakers of the language. How words are ordered, which letters the
dictionary is browsed by, and whether every letter renders in one typeface are part of the
site's twist (see `motifs.md`). They are set per site, and nothing here assumes Portuguese.

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
- **Without `alphabet`**, the dictionary behaves as before: the first character of each word,
  and Portuguese collation.

`terradoc check` rejects a letter listed twice, and warns about a headword whose first letter
is not in the alphabet. Warnings do not block publication; such a word is listed after the
alphabet's own letters.

Use the community's own published alphabet, and say where it comes from in `CULTURA.md`.

## Fonts

terradoc bundles three typefaces:
- **Inter** (body): Latin, Latin Extended, IPA, and the tilde vowels (ẽ, ỹ, the combining tilde);
- **Sora** (headings): basic Latin and Latin Extended; **no IPA, no ẽ**;
- **IBM Plex Mono** (code): no IPA.

IPA fields (`ipa`) render in the body font unless the site sets `theme.font_family_ipa`.

`terradoc check` warns when the data uses a letter that the font for that kind of text lacks.
The browser would then draw that one letter in another typeface, mid-word. It checks three
kinds of text:
- dictionary headwords and encyclopedia titles, against the headings font;
- `ipa` fields, against the IPA font;
- everything else, against the body font.

It only checks the bundled fonts.

**To use a font of your own:**
1. put the files and a stylesheet with `@font-face` rules in `static/`;
2. list the stylesheet in `theme.extra_css`;
3. name the font in the theme.

```yaml
theme:
  extra_css: ["css/site-fonts.css"]          # static/css/site-fonts.css
  font_family_headings: "'Charis SIL', 'Inter', serif"
  font_family_ipa: "'Charis SIL', serif"
```

Check the font's license allows redistribution (SIL OFL fonts do).

## Interface languages

`locales: [pt, en]` lists the interface languages; each needs `locales/<code>.yaml`. Any code
works, including an indigenous language's own (`bor`, `mpu`), so the interface can be in the
language itself. Give it a label in `locale_labels`.

`terradoc check` warns when a locale lacks keys that the default locale has, because those
labels would show empty. Content (definitions, articles) stays in the languages it was written
in; translating the interface is a separate decision from translating the content.
