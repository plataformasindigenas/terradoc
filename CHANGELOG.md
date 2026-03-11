# Changelog

All notable changes to terradoc are documented here.

## [0.2.1] — 2026-03-11

Refines the terra theme with visual polish, adds a new module, and introduces
an opt-in knowledge graph for the encyclopedia.

### Added

- **Videos module.** New `videos` converter, template, and index teaser for
  YouTube-hosted video collections. Supports category filtering, thumbnail
  grid with play overlays, and oEmbed metadata.
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
- **Page badges.** Small split-circle moiety SVG badge on all inner page
  headings (dictionary, encyclopedia, fauna, bibliography, recordings,
  videos).
- **`--td-color-gold` CSS variable.** Configurable gold accent color for
  decorative elements (stat separators, fauna borders, section labels).

### Changed

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
