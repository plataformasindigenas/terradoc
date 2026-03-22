# Changelog

All notable changes to terradoc are documented here.

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
