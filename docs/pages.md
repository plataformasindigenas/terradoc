# Pages: a site's own Markdown pages

Since 0.24.0 a site can publish pages of its own next to (or instead of) the data modules: a
team page, a credits page, a privacy page. The Plataformas Indígenas portal is a terradoc site
made only of pages.

```
data/pages/<locale>/<slug>.md       one file per page and locale
data/pages/<locale>/home.md         optional: shown on the home page, under the hero
```

```markdown
---
title: Equipe                       # required (except home.md); the heading and menu label
description: Quem faz o projeto.    # optional: the lede and the meta description
nav: 2                              # optional: listed in the menu, in this order
aliases: [equipe.html]              # optional: old addresses that forward here
---
Text in Markdown, as in encyclopedia articles (no HTML).
```

- A page is published at `<locale>/<slug>.html`. **The slug is the same in every locale**, and
  every locale needs the page: the language switch keeps the address and changes only the
  locale. `terradoc check` reports a page missing in a locale.
- Slugs use `a-z`, `0-9` and `-`, and cannot be a module's name or one terradoc uses itself
  (`index`, `about`, `404`, `offline`, `specimen`).
- **Pictures** come from `static/` and are published as responsive WebP, with their size:
  `![what it shows](images/team/ana.jpg "credit")`. The title, if any, is shown as the credit.
  A picture from another site is a `check` error (link to it instead): pages load nothing from
  other services.
- A **list in which every item shows a picture** is laid out as cards (team, partners,
  steps).
- `{#name}` on the line before a heading sets its anchor (`page.html#name`); other attributes
  are dropped.
- **Aliases** are paths from the site root (`equipe.html`, `en/team.html`). terradoc writes a
  small forwarding page at each one (relative, so a preview forwards inside the preview; not in
  the sitemap; `noindex`, canonical to the new page). A static file at the same path is a
  `check` error.

## A site of pages only

Disable every module (`modules: {dictionary: {enabled: false}, …}`, all eight). The home
page then shows the hero, `home_sentence` and `home.md`; there is no module list, and no
about page unless the site writes `about_*` texts. Such a site is the project's own, not a
people's: `check` does not ask for a palette (the neutral one is used) or a `language_code`.
Use `theme: {pack: none}` (D21: the project layer carries no grafismo).

## The project link

The footer's "Plataformas Indígenas" link (string `ui_project`) goes to `project_url`
(default `https://terradoc.org/`).
