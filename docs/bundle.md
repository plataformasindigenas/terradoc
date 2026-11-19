# The export bundle (experimental)

`terradoc export --bundle-dir DIR` writes everything `terradoc render` needs to
build a site, as plain JSON. The aim is that another renderer (for example an
11ty or Hugo site) can consume the bundle without running terradoc's Python.

> **Status: experimental** (`"bundle_schema": "0-experimental"`). The layout below
> describes terradoc 0.11 as it is, not a promise. It will be frozen (and the
> schema version bumped to `1`) only once a second renderer actually consumes it.
> Do not build on it outside the Plataformas project yet.

## Files

| File | Content |
|---|---|
| `manifest.json` | `bundle_schema`, `terradoc_version`, `project` (the `meta_prefix`), `modules` (record count per enabled module), `files` |
| `<module>.json` | one per enabled module: `{"meta": {...}, "data": [records]}`, records validated against the module schema and cross-linked (e.g. dictionary ↔ fauna/ethnobotany via scientific names) |
| `encyclopedia.json` | full entries, including `content_html` (rendered Markdown) |
| `encyclopedia_index.json` | lightweight index for listing/search pages |
| `encyclopedia_graph.json` | only when `modules.encyclopedia.graph: true` |
| `index.json` | module counts for the landing page |

Only **enabled** modules are exported. The bundle is not published on the sites;
in CI it is kept as a build artifact.

## Not in the bundle (yet)

A renderer also needs, today, things terradoc reads straight from the project:
`terradoc.yaml` (site identity, theme, module labels and order), `locales/*.yaml`
(the site's own texts on top of terradoc's interface strings), and `static/`. Folding
these in (or documenting them as part of the contract) is the main open question
before the format can be frozen.
