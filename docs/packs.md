# Packs: each platform's own visual twist

Every terradoc site shares one interface. What makes a site recognisably *theirs* is its
**palette** (five colours, each named after a material), its photographs, and its **pack**: a
band under the header and between sections, a very light page texture, and, only when the
community has one, an emblem beside the site's name. A site with only a palette must look
finished; every pack element is optional.

## The rule

A pack belongs to the people it comes from, and it lives **in that people's site
repository**, not in terradoc. terradoc ships one pack, `weave`: generic, culturally neutral
geometry, which is also the default. No site uses another people's pack.

Patterns are drawn from the published research, as abstractions, never copies of a specific
object or a design owned by a clan or a family. Each site records in `CULTURA.md`:
- where each element comes from (the practice and the published sources);
- who approved it, and when;
- what was left out on purpose, and why.

Name roles rather than private individuals when the community prefers that.

## Palette

```yaml
theme:
  palette:
    ground:  {color: "#F4F1EA", material: "argila branca"}   # page background
    ink:     {color: "#111827", material: "carvão e resina"}  # text
    primary: {color: "#C81F2D", material: "urucum"}           # links, headings, buttons
    fill:    {color: "#D4A03A", material: "pena amarela"}     # bands, highlights (no text on it)
    muted:   {color: "#6B6F5A"}                               # secondary text
```

`terradoc check` refuses a palette whose pairs are hard to read (under 4.5:1). Without a
palette the site uses the project's neutral colours, and `check` says so.

## Making a pack

```
config/templates/v2/motifs/<name>/
    pack.yaml          people, and per element: title, description, sources, drawn_by,
                       approved: {by_role, date, note}
    band.svg.j2        a tile repeated along the band
    texture.svg.j2     a page-background tile (keep it very faint)
    emblem.svg.j2      optional; only when the community has one
```

Then `theme: {pack: <name>}` in `terradoc.yaml` (`pack: none` turns decoration off).

The SVG templates receive `palette` (role → `#rrggbb`), so a pack follows the site's colours:
`fill="{{ palette.primary }}"`. Each element must be a plain drawing: shapes, groups and local
references only (no text, images, scripts, styles, links or animation), at most 4 KB. An
element that is not approved, has no sources, does not render or is not a plain drawing is left
out with a `check` warning, and the site shows its palette there. Start from
`src/terradoc/templates_v2/motifs/weave/`.

## Overriding other templates

Templates are looked up file by file, first in the site's `config/templates/v2/`, then in
terradoc's. `terradoc/<name>` always means terradoc's own copy, so a site can change one
block of a page and keep the rest:

```jinja
{# config/templates/v2/pages/dictionary_index.html.j2 #}
{% extends "terradoc/pages/dictionary_index.html.j2" %}
{% block head %}{{ super() }}<meta name="robots" content="noindex">{% endblock %}
```

**Supported blocks** (the contract: kept across terradoc releases, and changes are announced
in the changelog):

| Template | Block | What it holds |
|---|---|---|
| `base.html.j2` | `title` | the page title before " · site title" |
| `base.html.j2` | `head` | extra elements at the end of `<head>` |
| `base.html.j2` | `main` | the page body, inside `<main>` |

Override as little as possible: everything outside these blocks may change in any release,
and every file a site overrides is one that terradoc upgrades no longer reach. The
`sites-gate` workflow builds every platform with each terradoc commit, which shows what a
release would change.

Until 0.23.0 terradoc also had the v1 templates, with motif packs in
`config/templates/motifs/` (`hero_background`, `hero_motif`, `hero_divider`, `page_badge`,
`grain_pattern`). They were removed; `terradoc check` names any leftovers.
