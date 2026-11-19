# Changelog

All notable changes to terradoc are documented here.

## [Unreleased]

## [0.22.0] — 2026-11-19

### Added

- **v2 pages for the other modules** (REDESIGN-PLAN.md P3), all working without JavaScript:
  - **Fauna and ethnobotany:** a list with names in the language first, Portuguese and
    scientific names, thumbnails; grouped by the people's classification (animals) or family
    (plants), or one A–Z list showing each item's group when there would be more than 12
    groups. A page per item, `fauna/<id>-<slug>.html` and `ethnobotany/<id>-<slug>.html`:
    picture with credit, filled fields only, abundance per village, links, "how to cite",
    previous/next.
  - **Encyclopedia:** all articles A–Z with their summaries (Markdown links shown as text);
    category chips (script) and `?category=a/b` from v1 links. Article pages keep the v1
    address `encyclopedia/<id>.html`: summary, a side column on wide screens (picture,
    infobox, type, categories, external link), text (images written as `images/x.jpg` point
    at the site root), pictures, examples, references linked to the bibliography, see also.
  - **Bibliography:** author-year list sorted by author, LaTeX accents removed (`\'a`,
    `\c{c}`, `--`), DOI links, anchors `#ref-<key>`; rows with no author and no title and
    "Source list item" notes left out.
  - **Videos:** a local file plays in the page (a sound player for files under `audio/` or
    with an audio extension; the list then counts "gravações"); a YouTube video is a local
    poster linking to YouTube, never an embedded player.
  - **Corpus:** a list and a page per text, `lang` from the row's `language` when it is a
    language tag, else the site's `language_code`.
  - **About:** the site's `about_mission`, `about_partners`, `about_contact`,
    `about_citation` and `about_credits` strings.
- **Links between modules in both directions:** a word's `_linked_fauna` also shows on the
  animal's page, an animal's `_linked_dictionary` on the word's page, and so on; links to
  pages that are not built are dropped.
- **List filter** (td.js) on long lists; reads `?search=` and `?q=` from v1 links.
- **Pictures:** WebP copies at 160/480/960 px, made in parallel and kept in `assets/img/`
  between builds (unused ones are removed at the end); the build reports pictures shown
  without a credit per module. Paths from the data are confined to `static/`.
- Portuguese content on other locales' pages carries `lang="pt-BR"`.

### Changed

- **Other sites' pictures are links, never loaded with the page** (dictionary, fauna,
  ethnobotany, encyclopedia), with the credit next to the link when there is one: nothing
  loads from another site unless the reader chooses.

## [0.21.0] — 2026-11-18

### Added

- **v2 dictionary.** A page per letter (`dictionary/<letter>.html`, words outside the
  alphabet in `dictionary/_.html`) that works without JavaScript, and a page per word,
  `dictionary/<id>-<slug>.html` (D24): headword with its homonym number, part of speech
  (hidden when it is a placeholder such as `X` or `LEX`), IPA, recordings ("Gravação 1, 2…",
  no names, D26), definition, and example, scientific name, note and links only when filled;
  a picture is shown only with a credit (`pic_credit`), otherwise linked (D27); "how to
  cite", previous/next word, canonical and hreflang. "Back" returns to the list the word was
  opened from (letter or search) with the word focused (the link itself is the #e-<id> target).
- **Search** on the dictionary page: a separate index (`assets/search/dictionary.<hash>.json`,
  whole definitions, no file names: Bororo 106 KB gzipped, budget 120 KB, checked by
  `sitecheck`) fetched when the search box is first used; ignores accents, case, apostrophes
  and a leading hyphen; order: the word itself, words starting with the query, a gloss that is
  the query, the query as a word in a gloss, inside words, then IPA and scientific names; the
  query is in the address (`?q=`). Loading, empty and failure (with
  "try again") states. `search_folds` in terradoc.yaml makes letters equal in the language's
  words (Enawenê-Nawê: `{r: l, b: w, u: o}`).
- **On-screen keyboard** with the alphabet's letters a phone keyboard may lack, plus
  `keyboard:` extras from terradoc.yaml; 44 px keys.
- **Old links keep working:** `<locale>/dictionary.html?entry=<id>` and `?search=<q>`
  forward to the word or the search.
- **Offline:** `sw.js` stores the shell (CSS, page script, the two critical fonts,
  `offline.html`) at install, other `assets/` files when first used, and the last 300 pages
  visited (served from the store when the network fails or takes over 4 s); photos and audio
  are never stored. Cache names carry the worker's scope (previews share one origin) and a
  new release clears the old shell and stored pages. A page never opened shows `offline.html`.
- **Text face per site** (`theme.font_vernacular: gentium | charis | andika`), Gentium by
  default. Charis (D16) draws its tilde so flat that ã õ ũ read as ā ō ū at text sizes, and all
  three sites write nasal vowels or Portuguese with tildes.
- `terradoc.orthography.Alphabet`: the alphabet's first letters and order in Python, the same
  as the page script (tested against it in node).

### Changed

- Body text is a little larger (Gentium has a smaller x-height than Charis).

## [0.20.0] — 2026-11-18

### Added

- **Template set v2 (first part).** `theme.templates: v2` (or `--templates v2`) builds the
  redesigned site: routes defined in code (`build_v2.py`), a home page (site name in the
  language, one sentence, a credited photograph, dictionary search box, one section per
  module), header with a phone menu that works without JavaScript, footer, the language
  redirect, a 404 page that carries its CSS inline and links to `base_url` (so it works under
  any mount), and `specimen.html` (alphabet, the headwords with most stacked marks, IPA, in
  every shipped style; not in the sitemap). Pages v2 does not have yet render a short "in preparation" page, so links
  and the sitemap stay complete. Site overrides live in `config/templates/v2/`; there
  `terradoc/<name>` means terradoc's own v2 template. v1 output is unchanged (gate).
- **Palette roles** (`theme.palette`: `ground`, `ink`, `primary`, `fill`, `muted`, each with
  its `material`). `check` errors when a pairing the components use is under 4.5:1. Without a
  palette, v2 uses the v1 colours and `check` warns.
- **Motif packs for v2** (`theme.pack`): `config/templates/v2/motifs/<name>/` with `pack.yaml`
  and `band`, `texture`, `emblem` SVG templates drawn with the palette. An element without
  `approved: {by_role, date}` or `sources`, or that does not render, or is not a plain drawing
  (shapes and local references only: no style, script, image, text or external URL), is left
  out with a `check` warning and the site shows its palette there; a pack name that does not
  exist is an error. `pack: none` shows the palette only. terradoc bundles a neutral `weave`.
- **Fonts subset per site.** Charis (text, vernacular, IPA) and Source Sans 3 (interface),
  renamed `td-text` and `td-ui` as the OFL requires, are subset at build time to the
  characters the site uses, including the templates' own text, credits and labels (about
  9–13 KB per style). The interface uses one weight, so a page needs two font files before
  its content. A character in the Latin, IPA or combining ranges that a shipped text-face
  subset lacks fails the build. `scripts/vendor_fonts.py`
  records the pinned upstream releases and checksums.
- **Responsive images**: the home photograph gets WebP copies at 480/960/1600 px (never
  upscaled), with deterministic names.
- `language_code` (ISO 639-3) for `lang` on vernacular text; `theme.hero_credit`,
  `theme.hero_alt`, `theme.font_vernacular`, and `theme.hero_people` (recorded, not used yet).
  `check` (v2) refuses a hero image or favicon outside `static/` and a hero that is not a
  photograph.
- **Same input, same bytes.** Fonts, CSS, pack and images get content-hashed names and are
  reproducible (font timestamps are kept; image names include the Pillow version), so
  sitepull keeps unchanged files. `assets/` is rebuilt from empty on every build, and
  `static/assets/` is reserved. The v2 sitemap is written from the route list.
- **v2 gate.** `gate/v2.sh` and a `v2` job in `sites-gate`: each site's branch in
  `gate/v2/sites.txt` is built with v2, built again and compared byte for byte, and checked
  for broken links, page weight (150 KB gzipped before photos and audio, counting every font
  the CSS declares), sitemap and file count (`python -m terradoc.sitecheck`); the font
  specimen is screenshotted and kept as a workflow artifact.

### Deprecated

- **The v1 template contract ends with v1.** Page configs in `config/*.yaml`, v1 page
  overrides in `config/templates/*.j2` and the v1 theme keys (`colors`, `hero_background`,
  `hero_motif`, `hero_divider`, `page_badge`, `grain_pattern`, `hero_images`, `hero_stats`, …)
  are not read by v2. v1 is removed in the release after every site has moved to v2.

### Dependencies

- `fonttools[woff]` and `pillow`.

## [0.19.0] — 2026-11-18

### Changed

- **Accented letters outside the alphabet sort as their plain letter.** With
  `alphabet: [a, …, o, …]`, *kudógó* sorts as *kudogo* instead of putting ó
  after the last letter; letters listed in the alphabet (Makurap's ã, ẽ) keep their own place.
  `check` uses the same rule for its first-letter warnings. v1 manifest for Makurap refrozen.

## [0.18.0] — 2026-11-18

### Added

- **Homonym numbers.** A `homonym` column (int) in the dictionary: the headword shows it as a
  superscript (aka¹, aka²), in the list, the entry, and fauna/ethnobotany links, and homonyms
  sort by it. Entries with a homonym get no automatic encyclopedia link by title, since the
  title does not say which sense an article is about. v1 manifests refrozen for this.

### Fixed

- **TSV cells stay text** until the schema converts them: the word "no" was read as `False`
  and "0" as a number in text columns.

## [0.17.0] — 2026-11-17

### Added

- **Template sets.** `theme.templates` (default `v1`) and `--templates` on `build` and
  `render` choose the template set; this version has only `v1` (v2 comes with the redesign).
  An unavailable set is refused.
- **v1 is frozen.** The `sites-gate` workflow now also builds each platform at a fixed commit
  (`gate/v1/sites.txt`) with pinned dependencies and fails on any byte difference from
  `gate/v1/<site>.sha256`. `gate/v1.sh check|freeze` runs the same locally.

- **Audio manifest.** `data/audio/manifest.tsv` (`file`, `entry_id`, `speaker`, `consent`)
  says which dictionary entry each recording belongs to, so homonyms and headword edits no
  longer decide it. With it, only listed files with `consent: approved|external` are
  published; `check` fails on unlisted or missing files, unknown entry ids, duplicate rows and
  a `speaker` that is not an id such as `s01`. Without it, audio still follows the headword.

### Changed

- **Unknown `theme:` keys are errors** in `check` and `build`, with a suggestion for near
  misspellings, instead of being ignored.

## [0.16.1] — 2026-11-17

### Changed

- **No speaker names on the dictionary.** Recordings are no longer labelled with the
  speaker's name (taken from the audio filename); an entry with several recordings shows
  "Gravação 1", "Gravação 2" ("Recording" in English; `dict_recording_label` overrides it).
  The published `dictionary.json` no longer carries a `speaker` field. Audio filenames are
  unchanged.

## [0.16.0] — 2026-11-17

### Changed

- **Sitemap with absolute URLs.** New top-level `base_url` (the site's public address).
  `sitemap.xml` now lists absolute, escaped URLs, as the protocol requires, and leaves out
  `404.html` and the root language redirect; `robots.txt` points at it with an absolute URL.
  Without `base_url` no sitemap is written (the old one, with relative URLs, was invalid).
- **Numbers in the interface language.** A `number` template filter: `4.865` and `7,0%` in
  Portuguese (and any language but English), `4,865` and `7.0%` in English. Used for the
  dictionary, encyclopedia and home-page counts.

## [0.15.0] — 2026-11-15

### Changed

- **No language picker.** The site's root page now sends visitors straight to their language:
  the one they last chose with the language switch, else the first of the browser's languages
  the site has, else `default_locale`. Without JavaScript it goes to `default_locale`.

### Added

- **`server/`: sitepull**, the web server's side of publishing (not part of the PyPI package).
  A systemd timer polls `refs/sites/*` anonymously, verifies each release (branch tip, regular
  files only, size limits), switches it in atomically, smoke-tests it through Caddy and switches
  back on failure. `sitectl` gives status, rollback with hold, retry, purge and a break-glass
  import. See `server/README.md`.
- sitepull: per-site `refs = refs/<word>` (default `refs/sites`), so one repository can publish
  two sites (`www`: `refs/portal/*`, `refs/landing/*`).

## [0.14.0] — 2026-11-15

Orthography is part of each platform's twist: its own alphabet, fonts that have its letters,
and interface languages. See `docs/orthography.md`.

### Added

- **`alphabet`** in `terradoc.yaml`: the language's letters in order, digraphs allowed
  (`mb`, `ng`). The dictionary's letter bar and sort order follow it (longest match, NFC,
  case-insensitive). Without it, nothing changes.
- **Inter's tilde-vowel subset** (`inter-vietnamese.woff2`, same Inter 4.001): ẽ, ỹ and the
  combining tilde now render in Inter instead of a fallback font.
- `theme.font_family_ipa` (the font for `ipa` fields) and `theme.extra_css` (site stylesheets
  from `static/`, for example with `@font-face` rules for a font of the site's own).
- `check` warnings:
  - a headword whose first letter is not in the alphabet;
  - letters in the data that the font for that kind of text lacks (headwords and titles,
    IPA, body), using precomputed coverage of the bundled fonts (`tools/font_coverage.py`);
  - interface keys of the default locale missing from another locale, or a locale without
    its file.
  - A letter listed twice in `alphabet` is an error.
- **`terradoc/<name>` template namespace:** a site's page can
  `{% extends "terradoc/dictionary.html.j2" %}` and change one block. `base.html.j2` gains a
  `footer` block. The supported blocks are listed in `docs/motifs.md`.
- `examples/bundle_dictionary.py`: an independent, standard-library-only consumer of the export
  bundle, run by the tests. It keeps the bundle usable by a renderer other than terradoc.
- `.github/workflows/sites-gate.yml`: every push builds each platform with its pinned terradoc
  and with the new commit, and lists the differences.

### Changed

- IPA in the dictionary uses the body font (Inter has IPA) instead of IBM Plex Mono (which has
  none).
- The site workflow retries a not-yet-propagated PyPI release for up to about 24 minutes
  (before: about 10), with `--no-cache-dir`.
- A malformed `terradoc.yaml` is reported in one line instead of a traceback.

## [0.13.0] — 2026-11-14

Each people's visual motifs now belong to that people's site, not to terradoc.

### Changed (breaking for sites that used `moiety` or `lattice`)

- **Motif packs live in `motifs/<name>/`** (`background.html.j2`, `motif.html.j2`,
  `divider.html.j2`, `badge.html.j2`, `grain.css.j2`); the theme settings `hero_background`,
  `hero_motif`, `hero_divider`, `page_badge` and `grain_pattern` each name a pack. A site
  supplies its own in `config/templates/motifs/<name>/`. See `docs/motifs.md`.
- **terradoc ships only the neutral `weave` pack, and it is the default.** The Bororo
  `moiety` pack (Tugarege/Ecerae) and the Enawenê-Nawê `lattice` pack moved to those sites'
  repositories. Before, `moiety` was the default for every site, and an unknown badge name drew
  the moiety badge.
- **An unknown or missing pack is a `check` error** (also at `render`), never a silent
  fallback; `none` (and `dots` for the grain) need no pack.
- **Templates are looked up file by file, the site first:** a site may override one page or
  one partial in `config/templates/` and inherit the rest. Before, the presence of
  `config/templates/` replaced all of terradoc's templates, and the build failed on the first
  page the site had not copied.

Upgrading: copy your pack from the 0.12.1 package (`templates/hero/hero_{bg,motif,divider}_<name>.html.j2`,
the badge in `decor.html.j2`, the grain in `base.html.j2`) into `config/templates/motifs/<name>/`.
Bororo, Enawenê-Nawê and Makurap were migrated with byte-identical output.

## [0.12.1] — 2026-11-14

### Added

- **Photo credits** in ethnobotany and fauna: optional `pic_credit` (shown under the photo in
  the detail panel; locale key `photo_credit`, default "Foto") and `pic_source` (its link).
  `pic_link` may now also be an `http(s)` address on these pages (it used to be prefixed with
  `../` and break); `check` refuses any other scheme there, and a `pic_source` that is not `http(s)`.

### Changed

- A TSV row with too many or too few cells is reported as "line N: K column(s), but the header
  has M" on its own line, instead of a Python type error for the whole file.
- `404.html` links are root-relative (`/css/…`, `/<locale>/…`), so the page works when served
  for a missing path at any depth; its menu used to point at pages outside `/<locale>/`.
- Reusable workflow: `pip install` is retried for up to ~10 minutes while the pinned version is
  "not found" (a fresh release takes a while to reach every PyPI mirror).

## [0.12.0] — 2026-11-14

### Added

- **Reusable GitHub Actions workflow** `.github/workflows/site.yml`: validates, builds, guards
  and publishes every branch as `refs/sites/<name>`; failure issues with CODEOWNERS mentions,
  closed automatically on the next success; preview cleanup on branch deletion. See
  `docs/publishing.md`.
- **`terradoc guard`**: compares a built site with the release it replaces (module shrink
  >20 records or >10 %, >25 % against an optional baseline, files lost > max(10, 5 %));
  `--confirm-shrink` turns the errors into warnings.
- **`--format markdown`** for `check` and `guard` (bilingual pt/en issue body), with
  `--codeowners FILE` (GitHub's matching rules; last match wins) and `--run-url`.
- `.release.json` now records per-module record counts (`modules`).

### Changed

- Duplicate primary keys are reported as "duplicate id X (first used on line N)".

## [0.11.0] — 2026-11-14

### Added

- **`terradoc check`**: validates a project without writing anything and
  reports every problem with file and line (`--format text|github|json`;
  `github` emits Actions annotations). New blocking rules: **consent**
  (`videos`/`recordings` rows need `consent: approved` or `consent: external`)
  and **media** (every referenced `images/...`/`audio/...` file must exist).
  Schema validation now reports all rows of all modules, not just the first
  failure.
- **`terradoc export`** and **`terradoc render`**: the build split in two. The
  export bundle (`manifest.json` + one JSON per module) is the intended
  contract for other renderers; its format is **experimental**
  (`bundle_schema: "0-experimental"`).
- **`--out DIR`, `--bundle-dir DIR`, `--clean`** on `build`/`render`/`export`:
  build without touching the checkout. Page configs that say `../docs/` and
  `../data/*.json` are remapped in memory; existing projects need no changes.
  `--clean` refuses any directory that is, contains or overlaps the project,
  its sources, templates or bundle, and any directory that terradoc did not
  build from empty (`owned_by_terradoc` in `.release.json`).
- `export` always runs the full check, and `render` re-checks consent and
  `static/` against the sources, so neither can publish unconsented media
  (not even from a bundle exported before consent was withdrawn).
- **`static/`**: copied verbatim into the site root. The build fails if a
  generated file would overwrite one, or if `static/` is or contains a
  symlink (both are also `check` errors).
- **`.release.json`** in the site root: project, terradoc version, source
  commit and ref (`GITHUB_SHA`/`GITHUB_REF_NAME` or git), file count, bytes.
  No timestamps, so identical inputs give identical output.
- **`videos_oral.html.j2`**: oral-corpus layout for self-hosted media (from the
  Makurap platform); select it in `config/videos.yaml`.
- **About page image credits**, shown when the locale defines `about_credits`
  (and optionally `about_credits_heading`).

### Changed

- `terradoc build` runs the full `check` first; projects with unconsented
  videos/recordings rows or missing media files now fail to build.
- `terradoc init` no longer copies the templates into `config/templates/`
  (use `--eject-templates`), and puts the logo and favicon in `static/images/`.
- `uv.lock` regenerated: it still listed the external `aptoro` and
  bibtexparser 1.x from before 0.9.0.

### Compatibility

Rendered HTML is byte-identical to 0.10.0 for the three Plataformas sites
(Bororo, Enawenê-Nawê, Makurap), checked from clean checkouts.

## [0.10.0] — 2026-10-09

### Added

- **Entry gallery.** Encyclopedia entries with four or more images now get a
  captioned thumbnail grid with a keyboard-navigable lightbox (`<dialog>`;
  arrows, Esc, click-outside). The sidebar's tiny "more images" thumbnails are
  replaced by the gallery on those entries. Entries with fewer than four images
  are unchanged. New locale keys: `enc_gallery`, `enc_gallery_close`,
  `enc_gallery_prev`, `enc_gallery_next` (all have defaults).
- **Landing-page spotlight card.** A highlighted card shown first under the
  "Explore" heading when the locale file defines `index_spotlight_href`
  (plus optional `index_spotlight_title`, `_desc`, `_image`, `_image_alt`,
  `_stat`, `_stat_label`, `_cta`). Nothing renders if the keys are absent.

## [0.9.0] — 2026-08-25

### Changed

- **Self-contained: no external aptoro/kodudo dependency.** The `aptoro`
  (schema validation) and `kodudo` (Jinja2 rendering) libraries are now
  inlined as `terradoc._aptoro` and `terradoc._kodudo`. All dependencies
  are standard PyPI packages — no private repos or sibling installs needed.
  `pip install terradoc` is all it takes.
- **Relaxed dictionary schema.** The bundled `dictionary_schema.yaml` now
  treats `pos` as an optional free-text field (`str?`) instead of a
  required enum. Platform-specific schemas in `data/` can still enforce
  stricter validation per project.

### Removed

- **`aptoro` and `kodudo` as external dependencies.** Both are inlined;
  the `pyproject.toml` dependency list no longer references them. Existing
  installs that have them as separate packages are unaffected — the
  inlined copies use private import paths (`terradoc._aptoro`,
  `terradoc._kodudo`).

## [0.8.0] — 2026-04-15

### Added

- **Convention-based dictionary audio.** New `attach_audio_to_dictionary` step
  in the build pipeline scans `data/audio/` and attaches audio files to
  dictionary entries by slug convention — `data/audio/<slug>.webm` as primary,
  `data/audio/<slug>__<speaker>.webm` for per-speaker variants. No schema
  changes required on the dictionary: the engine populates `entry.audio` at
  build time from whatever files are present on disk. Slug derivation is
  lowercase + diacritic strip + non-alphanumeric collapsed to `_`.
- **Audio copy step.** `build_site.copy_audio_files` mirrors
  `data/audio/*.webm` → `docs/audio/` as part of the static-asset phase
  (parallel to `copy_static_assets`). Files beginning with `_` are skipped so
  import reports and notes don't end up in the deployed site.
- **Audio coverage badge.** The dictionary page header now shows a compact
  pill ("🔊 N com áudio (X%)") when `meta.audio_coverage.entries_with_audio`
  is non-zero. Two new locale keys consumed with fallbacks:
  `dict_with_audio_label` and `audio_files_label`.

### Changed

- **Dictionary template audio URL prefix.** `dictionary.html.j2` now emits
  `<audio src="{base}audio/…">` instead of `{base}recordings/…`, matching the
  new `docs/audio/` output directory. Sites using the old `recordings` module
  are unaffected — `attach_recordings_to_dictionary` still runs when the
  `recordings` module is enabled, and it writes to the same `entry.audio`
  field, so the template change is format-agnostic.

### Notes for site maintainers

- The new audio attach step is a **no-op** when `data/audio/` does not exist,
  so existing sites (e.g. enawenenawe) build unchanged.
- To adopt the new convention, drop WebM files into `data/audio/<slug>.webm`
  using the same slug rule the engine applies to `entry.entry`. Multiple
  recordings per entry: add `__<speaker>` suffixes.
- `meta.audio_coverage` is written into `dictionary.json` automatically and
  is available to any consumer of the generated JSON.

## [0.7.0] — 2026-03-21

### Added

- **About page.** New `about.html.j2` template rendered for every locale.
  Shows project logo, mission, team/partners, contact info, citation block
  (monospace), and a tools grid linking to terradoc/aptoro/kodudo on PyPI.
  Content driven entirely by `about_*` locale keys.
- **Custom 404 page.** New `404.html.j2` template with terra-styled layout,
  large logo, accent "404" text, and a home link button.
- **SEO meta tags.** `base.html.j2` now emits `<meta name="description">`,
  Open Graph (`og:title`, `og:description`, `og:type`, `og:image`,
  `og:locale`), and Twitter Card tags.
- **Sitemap and robots.txt.** `build_site` now generates `sitemap.xml` and
  `robots.txt` in the output root.

### Changed

- **bibtexparser v2.** Updated from v1 to v2 API
  (`bibtexparser.parse_string()` / `Library` / `Entry.fields_dict`).
  Minimum dependency bumped to `bibtexparser>=2.0.0b7`.

### Fixed

- **About page badge.** `about.html.j2` now uses
  `theme.page_badge` instead of hardcoding `"moiety"`.

## [0.6.0] — 2026-03-21

### Added

- **Configurable page badge.** New `theme.page_badge` config field selects the
  SVG badge rendered on inner page headings. Three presets:
  - `moiety` (default): Split-circle Bororo moiety badge (Tugarege/Ecerae).
  - `lattice`: Circle with diagonal lattice lines and Yãkwa triangle
    (Enawenê-Nawê).
  - `weave`: Simple concentric circles (culturally neutral).
  - `none`: Disables the badge.
- **Configurable grain texture.** New `theme.grain_pattern` config field
  controls the subtle background texture overlay. Presets:
  - `dots` (default): Small dot grid (sand/parchment feel).
  - `lattice`: Diagonal crossing lines (woven fibre feel).
  - `weave`: Small rounded rectangles (basket-weave feel).
  - `none`: Disables the grain overlay.
- **Configurable hero height.** New `theme.hero_height` config field: set to
  `"large"` for a 92 vh hero, otherwise defaults to 70 vh.

### Changed

- **Enhanced lattice motif.** The `lattice` hero motif now features dashed
  lattice lines with a subtle drift animation, denser centre cross-hatching,
  and a more prominent Yãkwa house triangle with roof ridge and golden peak.
- **Enhanced lattice divider.** The `lattice` section divider now includes a
  small Yãkwa triangle at the centre of the river wave pattern.

## [0.5.1] — 2026-03-21

### Fixed

- **Lattice background animation.** Lines in the `lattice` hero background
  preset now animate their endpoints (`x1`/`y1`/`x2`/`y2`) to expand outward
  from each source point, matching the expanding behaviour of the `moiety`
  preset. Previously the lines appeared at full size and only faded in/out.

## [0.5.0] — 2026-03-21

### Added

- **Modular hero animation presets.** Three new config fields
  (`theme.hero_background`, `theme.hero_motif`, `theme.hero_divider`)
  allow each project to independently select culturally appropriate
  animations from built-in presets. Available presets:
  - `moiety` (default): Bororo-inspired — expanding circles/diamonds
    with dual moiety-coded dash patterns, two-toned village circle
    with pulsing baito, adugo jaguar spine divider.
  - `lattice`: Enawenê-Nawê-inspired — diagonal waitiwina fishing dam
    lattice, concentric village circles with Yãkwa house triangle,
    river wave divider with lattice cross marks.
  - `weave`: Culturally neutral — expanding rounded rectangles, simple
    concentric circles with accent ring, diamond-accented line divider.
  - `none`: Disables the component entirely.
- **Hero template partials.** Nine new `templates/hero/` partials
  (`hero_bg_*.html.j2`, `hero_motif_*.html.j2`, `hero_divider_*.html.j2`)
  keep each preset self-contained with its own CSS and SVG markup,
  including `prefers-reduced-motion` support.

### Changed

- **Footer divider follows hero preset.** The footer spine divider in
  `base.html.j2` now uses the same `hero_divider` preset as the index
  page, ensuring visual consistency across all pages.
- **Extracted inline hero SVG.** Background animation, photo frame motif,
  and section divider SVGs moved from `index.html.j2` into includable
  partials, reducing the main template by ~250 lines.

## [0.4.0] — 2026-03-21

### Added

- **Corpus module.** New `corpus` converter, schema, and split-pane
  template for displaying and searching annotated text collections.
  Includes JavaScript full-text search with match highlighting,
  language tags, and responsive layout. Bundled schema, CLI
  scaffolding, index data copying, and default module config included.

## [0.3.3] — 2026-03-21

### Changed

- **Configurable module order.** New `module_order` field in `terradoc.yaml`
  controls navigation bar and index card ordering. Defaults to the built-in
  order; enabled modules not listed are appended automatically.
- **Dynamic index page sections.** The index template now iterates enabled
  modules instead of a hardcoded list, so ethnobotany and future modules
  appear automatically.
- **Theme-driven hero gradient.** Replaced hardcoded hex colors in the index
  hero background with `--td-color-bg-light` and `--td-color-bg-infobox`
  CSS variables, ensuring the gradient adapts to custom themes.
- **Dynamic teaser image mapping.** Index section images are now assigned
  from `theme.hero_images` in module order instead of a fixed mapping.

## [0.3.2] — 2026-03-21

### Changed

- **Generic field names for multi-community support.** Renamed all
  Bororo-specific identifiers to generic ones: `name_bororo` →
  `name_indigenous`, `classification_bororo` → `classification_indigenous`.
  Schema names drop the `bororo_` prefix (e.g. `bororo_fauna` → `fauna`).
  Templates use generic fallback labels ("indígena" instead of "Bororo").
- **Configurable ethnobotany↔encyclopedia cross-link categories.** The
  `ethnobotany_encyclopedia_categories` config field (default
  `["natureza/flora"]`) controls which encyclopedia categories are linked
  to ethnobotany entries, allowing per-project customization.

## [0.3.1] — 2026-03-21

### Added

- **Ethnobotany module.** New `ethnobotany` converter, schema, showcase
  template, and cross-linker support. The template groups entries by
  botanical family, displays usage (Bororo and Portuguese), fruiting period,
  environment, and abundance per village. Cross-links to dictionary by
  scientific name and to encyclopedia entries tagged `natureza/flora`.
  Bundled schema, CLI scaffolding, and default module config included.

## [0.3.0] — 2026-03-11

A major release that redesigns the terra theme, adds two new modules, and
introduces build-time validation and an opt-in knowledge graph.

### Added

- **Videos module.** New `videos` converter, template, schema, and index
  teaser for YouTube-hosted video collections. Supports category filtering,
  thumbnail grid with play overlays, and oEmbed metadata. Bundled schema,
  CLI scaffolding, and default module config included.
- **Encyclopedia knowledge graph (opt-in).** Force-directed D3.js
  visualization showing entries connected by categories, `see_also` links,
  and wikilinks. Activated per-project with `encyclopedia: { graph: true }`
  in `terradoc.yaml`. Includes expand/collapse by category, zoom/pan/drag,
  color-coded nodes, and tooltips with abstract and article link.
- **Wikilink target extraction.** New `extract_wikilink_targets()` utility
  captures link targets before conversion to HTML, enabling graph edge
  generation and future link analysis.
- **`ModuleConfig.graph` flag.** Modules can now declare opt-in features
  beyond `enabled`; `graph` (default `false`) gates encyclopedia graph
  generation and rendering.
- **Build preflight validation.** `run_all_converters()` now checks all
  enabled modules for missing schemas and required data paths before running
  any converter, failing fast with a clear summary.
- **`_load_schema` helper.** Consolidates schema loading across all
  converters with a clear `FileNotFoundError` when a schema file is missing.
- **Page badges.** Small split-circle moiety SVG badge on all inner page
  headings (dictionary, encyclopedia, fauna, bibliography, recordings,
  videos).
- **`--td-color-gold` CSS variable.** Configurable gold accent color for
  decorative elements (stat separators, fauna borders, section labels).

### Changed

- **Terra theme palette.** Updated defaults: primary `#C81F2D`, accent
  `#D4A03A`, fonts `Sora`/`Inter`, border-radius `28px`. The terra preset
  now uses a warmer, more distinctive color scheme.
- **Hero redesign.** Village circle motif with photo cluster, floating
  satellite images, ambient SMIL pulse animations, and interactive peephole
  hover effect.
- **Section teasers.** Unified card layout with organic dashed left borders,
  per-section accent colors via `data-section` attribute and CSS custom
  properties, and warm hover states.
- **Section headings.** Flex layout with red accent bar, nested diamond SVG
  motif, and consistent styling across all templates.
- **Footer overhaul.** Prominent organic SVG adugo spine, removed resources
  column, credits now link terradoc/aptoro/kodudo to PyPI.
- **Dictionary layout.** `dict-layout` constrained to viewport height
  (`calc(100vh - 10rem)`) so the word list scrolls within the visible area
  instead of extending the page.
- **Encyclopedia categories.** Category list capped at
  `calc(100vh - 16rem)` with `overflow-y: auto`.
- **`see_also` and `wikilink_targets` in index JSON.** Encyclopedia index
  records now include these fields to support graph generation.
- **Recordings and videos in CLI scaffolding.** `terradoc init` now
  generates config files for all six modules.

### Fixed

- **Navbar overlap on inner pages.** CSS shorthand `padding: 0 2rem` in
  `.td-style-terra .td-container` was resetting `padding-top` to 0,
  overriding the navbar clearance. Changed to `padding-left`/`padding-right`
  only across all responsive breakpoints.

## [0.2.0] — 2026-03-09

A major feature release adding a complete theming system and data validation
pipeline. 32 files changed across the codebase; test count grew from 30 to 124.

### Added

- **Theme presets.** Two built-in presets (`terra` and `classic`) with full
  18-color palettes, font stacks, and border-radius tokens. Projects select a
  preset in `terradoc.yaml` and can override individual values on top.
- **Decorative macros.** Eight parameterised Jinja2 macros in a shared
  `decor.html.j2` (`hero_decor`, `motif_divider`, `section_accent`,
  `badge_circle`, `spine_divider`, `progress_dots`, `section_spine`,
  `category_marker`) providing inline-SVG ornaments and structural accents.
- **Per-module intensity.** New `theme.module_intensity` config map lets
  projects dial each page's decoration density to `minimal`, `balanced`
  (default), or `rich`.
- **Term emphasis.** `.td-term` CSS class with `--td-term-color` and
  `--td-term-weight` custom properties for highlighting indigenous-language
  terms. The `terra` preset adds a dotted underline.
- **ID format validation.** Encyclopedia IDs must now match
  `^[a-z0-9][a-z0-9-]*$` — no uppercase, spaces, underscores, or accented
  characters.
- **Filename/ID consistency.** Each Markdown file's stem must match its `id`
  front-matter field; mismatches fail the build.
- **`see_also` referential integrity.** Every `see_also` target is validated
  against the set of known entry IDs after all files are parsed. Broken
  references fail the build.
- **Bibliography key validation.** References to BibTeX keys are validated
  upfront during encyclopedia conversion. Unresolvable keys (including entries
  that reference keys when no `.bib` file exists) fail the build instead of
  silently producing error markers in the rendered output.
- **Category vocabulary.** If a `data/categories.yaml` file exists (a flat YAML
  list of valid category paths), every entry's categories are validated against
  it. This prevents category drift and near-duplicate paths.
- **`terradoc categories` CLI command.** Reads all encyclopedia entries and
  outputs sorted unique category paths. Supports `--output` / `-o` to write
  directly to `data/categories.yaml` as a bootstrap step.
- **Data completeness report.** After encyclopedia conversion, a summary is
  always printed: counts of entries without abstract, without categories,
  without body content, and (if any) with broken wikilinks.

### Changed

- **Strict theme config parsing.** `theme`, `theme.colors`, and
  `theme.colors_dark` must be YAML mappings; non-mapping values now raise
  `ValueError` with a clear message instead of producing cryptic errors
  downstream.
- **Template directory resolution.** Both the local `config/templates/` and the
  bundled package templates are now always available in the Jinja2 search path,
  so `{% from "decor.html.j2" import ... %}` resolves correctly even when
  templates are not overridden locally.

### Removed

- **Dead cross-link schema fields.** `dictionary_ids` and `fauna_ids` from the
  encyclopedia schema, `fauna_ids` and `encyclopedia_ids` from the dictionary
  schema, and `dictionary_ids` from the fauna schema. These fields were defined
  but never populated or read; the cross-linker uses computed `_linked_*` fields
  instead. Existing data files with these fields are unaffected (aptoro silently
  ignores extra fields).

## [0.1.3] — 2025-12-01

### Fixed

- `copy_static_assets` no longer copies `__init__.py` marker files from the
  package's `static/js/` and `static/css/` directories into generated output.

## [0.1.2] — 2025-12-01

### Fixed

- Bundled templates now resolve correctly when no local template override
  exists, using `dataclasses.replace` to patch the kodudo batch config.

## [0.1.1] — 2025-11-01

### Added

- External CSS stylesheet (`terradoc.css`) extracted from inline styles.
- Full-width layout system with container, sticky nav, and box shadows.
- Typography system with configurable heading font and spacing tokens.
- Redesigned nav with larger brand area, active-page indicator, and mobile
  hamburger menu.
- Redesigned home page with hero image support and card grid.
- Improved article reading experience with infobox component and refined
  typography.
- Dictionary page: sticky header, panel backgrounds, refined spacing.
- Skeleton loading animations and improved empty states.
- Language picker templatised as a standalone Jinja2 template.
- Footer enhancements: optional text slot, more padding, better spacing.
- Smooth scroll, page fade-in animation, and `:focus-visible` outlines.
- Print stylesheet (hides nav, search, and footer).
- Dark mode support via optional `theme.colors_dark` config.
- Tablet-responsive breakpoints for intermediate screen sizes.
- `ThemeConfig` expanded with full color palette and font tokens; all
  hardcoded colour values replaced with CSS custom properties.

### Changed

- Removed Bororo-specific defaults; the engine is now fully project-agnostic.
- `module_labels` and `locale_labels` merge with defaults instead of replacing
  them, so projects only need to specify overrides.
- Module labels derived dynamically via `site_context()`.
- Schema resolution consolidated into a single `TerradocConfig.resolve_schema`
  method.
- Version single-sourced via `setuptools.dynamic` attr.
- User values in language picker HTML-escaped to prevent XSS.
- Jinja2 declared as a direct runtime dependency.

### Removed

- Unsupported `--output` CLI option removed from the `build` command.

## [0.1.0] — 2025-10-01

Initial release.

- Multi-module site generator: dictionary, encyclopedia, fauna, bibliography,
  recordings.
- Markdown-based encyclopedia with YAML front matter, wikilinks, and footnotes.
- TSV dictionary and YAML fauna converters with aptoro schema validation.
- BibTeX bibliography conversion with formatted citations.
- Cross-linker: dictionary/fauna by scientific name, dictionary/encyclopedia
  by title.
- Recording attachment to dictionary entries.
- Multi-locale support with per-locale page generation and language picker.
- `terradoc init` scaffolding and `terradoc build` pipeline.
- kodudo-based template rendering with Jinja2.
