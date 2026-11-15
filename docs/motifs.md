# Motif packs: each platform's own visual twist

Every terradoc site shares one interface. What makes a site recognisably *theirs* is its
palette, its photographs, and its **motif pack**: the hero background, the frame around the
hero photos, the section divider, the small badge beside page titles, and the background grain.

## The rule

A motif pack belongs to the people it comes from, and it lives **in that people's site
repository**, not in terradoc. terradoc ships one pack, `weave`: generic, culturally neutral
geometry, which is also the default. No site uses another people's pack.

Each site that has its own pack records in `CULTURA.md`:
- where the motif comes from (the object, practice or published source);
- who in the community agreed to its use, and when;
- what it must not be used for.

Name roles rather than private individuals when the community prefers that.

## Making a pack

```
config/templates/motifs/<name>/
    background.html.j2   hero background (animated or still)
    motif.html.j2        frame around the hero photo cluster (shown only with theme.hero_images)
    divider.html.j2      divider under the hero and the page header
    badge.html.j2        badge beside page titles; receives `size`
    grain.css.j2         CSS for `.td-style-terra::before` (the page grain)
```

Then, in `terradoc.yaml`:

```yaml
theme:
  hero_background: "<name>"
  hero_motif: "<name>"
  hero_divider: "<name>"
  page_badge: "<name>"
  grain_pattern: "<name>"
```

The settings are independent, so a site can mix packs: for example its own badge with the
neutral divider. `none` turns a part off; `grain_pattern: dots` keeps the default grain.

`terradoc check` fails if a named pack lacks the file a setting needs. Start from
`src/terradoc/templates/motifs/weave/` and use the colour variables (`var(--td-color-primary)`,
`--td-color-accent`, `--td-color-dark`) rather than fixed colours, so that the pack follows the
site's palette.

## Overriding other templates

Templates are looked up file by file, first in the site's `config/templates/`, then in
terradoc's. `terradoc/<name>` always means terradoc's own copy, so a site can change one
block of a page and keep the rest:

```jinja
{# config/templates/dictionary.html.j2 #}
{% extends "terradoc/dictionary.html.j2" %}
{% block extra_styles %}{{ super() }} .entry-word { letter-spacing: .02em; }{% endblock %}
```

**Supported blocks** (the contract: kept across terradoc releases, and changes are announced
in the changelog):

| Template | Block | What it holds |
|---|---|---|
| `base.html.j2` | `title` | the page title before " - site title" |
| `base.html.j2` | `extra_styles` | extra CSS inside the page's `<style>` |
| `base.html.j2` | `content` | the page body |
| `base.html.j2` | `footer` | the whole `<footer>` |
| `base.html.j2` | `scripts` | scripts at the end of the page |

Override as little as possible: everything outside these blocks may change in any release,
and every file a site overrides is one that terradoc upgrades no longer reach. The
`sites-gate` workflow builds every platform with each terradoc commit, which shows what a
release would change.
