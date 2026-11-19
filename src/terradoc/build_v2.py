"""v2 site build: routes in code, people layer (palette, fonts, pack), pages.

v1 (build_site.build_site) renders pages listed in each site's config/*.yaml; v2 does not
read those. Its routes are defined here, so every page knows its depth, its locale
switches and its canonical address. Pages that v2 does not have yet are rendered from
`pages/pending.html.j2`, so links and the sitemap stay complete while P2/P3 replace them.

Output layout:
    index.html                 language redirect
    404.html                   root-relative links
    <locale>/index.html        home
    <locale>/dictionary/index.html, <locale>/<module>.html, <locale>/about.html
    assets/site.<hash>.css     project CSS + this site's palette, fonts and pack
    assets/td.<hash>.js
    assets/fonts/              subset fonts (+ LICENSES.md)
    assets/pack/               rendered pack elements
    assets/img/                responsive WebP copies of referenced images
"""
from __future__ import annotations

import hashlib
import importlib.resources
import json
import re
import shutil
from urllib.parse import quote
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PrefixLoader, StrictUndefined, select_autoescape

from terradoc import fonts, images, packs
from terradoc import palette as palette_mod
from terradoc.config import TerradocConfig

# Where each module's main page lives in v2 (relative to the locale directory).
MODULE_PATHS = {"dictionary": "dictionary/index.html"}


def module_path(slug: str) -> str:
    return MODULE_PATHS.get(slug, f"{slug}.html")


@dataclass
class Route:
    path: str                    # from the site root, e.g. "pt/dictionary/index.html"
    template: str
    page: str                    # page id (body class, aria-current)
    title: str
    locale: str | None = None
    context: dict = field(default_factory=dict)
    sitemap: bool = True


@dataclass
class Assets:
    css: str = ""
    js: str = ""
    preload: list[str] = field(default_factory=list)
    band: str = ""
    texture: str = ""
    emblem: str = ""
    icon: str = ""
    inline_css: str = ""         # for pages served from anywhere (404): no fonts, no pack
    dict_js: str = ""
    search_index: str = ""
    hero: images.Derived | None = None
    fonts: list = field(default_factory=list)
    pack: packs.Pack | None = None
    css_bytes: int = 0


def prefix(path: str) -> str:
    """Relative prefix from a page at `path` back to the site root."""
    return "../" * path.count("/")


def bundled_dir() -> Path:
    return Path(str(importlib.resources.files("terradoc.templates_v2")))


def static_v2(name: str) -> bytes:
    return (importlib.resources.files("terradoc.static_v2") / name).read_bytes()


def environment(config: TerradocConfig) -> Environment:
    """Site overrides (config/templates/v2/) first, then terradoc's v2 set; `terradoc/<name>`
    always means terradoc's own v2 template, so an override can extend it."""
    from terradoc._kodudo.rendering import format_number

    dirs = [str(p) for p in (config.local_template_dir,) if p.is_dir()] + [str(bundled_dir())]
    env = Environment(
        loader=ChoiceLoader([FileSystemLoader(dirs),
                             PrefixLoader({"terradoc": FileSystemLoader(str(bundled_dir()))})]),
        autoescape=select_autoescape(("html", "xml", "j2")),
        undefined=StrictUndefined,
        trim_blocks=True, lstrip_blocks=True,
    )
    env.filters["number"] = format_number
    from terradoc.dictionary_v2 import gloss
    env.globals["gloss"] = gloss
    return env


class Strings(dict):
    """Interface strings; a missing key renders as empty text instead of failing."""

    def __missing__(self, key):
        return ""

    def __getattr__(self, key):
        return self[key]


def load_strings(locale: str, config: TerradocConfig) -> Strings:
    """terradoc's interface strings for `locale` (English for a locale it has none for),
    with the site's locales/<locale>.yaml on top."""
    base = bundled_dir() / "strings" / f"{locale}.yaml"
    strings = {}
    if not base.is_file():
        base = bundled_dir() / "strings" / "en.yaml"
        strings["html_lang"] = locale
    strings = {**(yaml.safe_load(base.read_text(encoding="utf-8")) or {}), **strings}
    site = config.locales_dir / f"{locale}.yaml"
    if site.is_file():
        strings.update(yaml.safe_load(site.read_text(encoding="utf-8")) or {})
    return Strings({str(k): v for k, v in strings.items()})


def site_palette(config: TerradocConfig) -> dict[str, palette_mod.Role]:
    if config.theme.palette:
        return palette_mod.parse(config.theme.palette)
    return palette_mod.from_v1(config.theme.colors)


def _hashed(data: bytes, stem: str, ext: str) -> str:
    return f"{stem}.{hashlib.sha256(data).hexdigest()[:10]}.{ext}"


def site_characters(config: TerradocConfig, strings: dict[str, Strings]) -> set[str]:
    """Every character a v2 page can show: data, interface strings, settings, and the
    templates and stylesheet themselves (separators like "·")."""
    texts: list[str] = [config.site_title, config.project_name, config.site_tagline,
                        config.project_subtitle, *config.alphabet, *config.module_labels.values(),
                        *config.locale_labels.values(), config.theme.hero_credit,
                        config.theme.hero_alt, static_v2("td.css").decode("utf-8"),
                        *config.keyboard, *config.search_folds, *config.search_folds.values()]
    for d in (config.local_template_dir, bundled_dir()):
        if d.is_dir():
            texts.extend(p.read_text(encoding="utf-8") for p in sorted(d.rglob("*.j2")))
    for s in strings.values():
        texts.extend(fonts.strings_in(dict(s)))
    for path in sorted(config.bundle_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        with open(path, encoding="utf-8") as f:
            texts.extend(fonts.strings_in(json.load(f)))
    return fonts.collect(texts)


def build_assets(config: TerradocConfig, strings: dict[str, Strings]) -> Assets:
    out = config.docs_dir
    assets = Assets()
    # assets/ is terradoc's (check refuses static/assets/): start it empty, so old hashed
    # files do not pile up in a directory built without --clean.
    # assets/img/ is kept (encoding WebP is slow; names carry a hash of the source) and
    # pruned of unused files at the end of the build (prune_images).
    if (out / "assets").is_dir():
        for p in (out / "assets").iterdir():
            if p.name == "img" and p.is_dir():
                continue
            shutil.rmtree(p) if p.is_dir() else p.unlink()

    chars = site_characters(config, strings)
    text_face = config.theme.font_vernacular or "gentium"
    lacking = fonts.missing(chars, text_face)
    if lacking:
        listed = " ".join(f"{c} (U+{ord(c):04X})" for c in lacking[:20])
        raise ValueError(f"the v2 text font lacks {len(lacking)} character(s) the site uses: {listed}")
    assets.fonts = fonts.build(chars, out / "assets" / "fonts", text_face)
    short = fonts.missing_in_built(chars, assets.fonts, out / "assets" / "fonts")
    if short:  # the subsetter dropped something it should have kept
        raise ValueError("font subsets lack characters the site uses: "
                         + "; ".join(f"{k}: {''.join(v[:20])}" for k, v in short.items()))
    (out / "assets" / "fonts" / "LICENSES.md").write_text(fonts.licence_text(), encoding="utf-8")
    assets.preload = [f"assets/fonts/{b.name}" for b in assets.fonts if b.face.critical]

    colors = palette_mod.colors(site_palette(config))
    pack = packs.render(packs.load(config), colors, out)
    assets.pack = pack
    vars_ = [f"--{role}:{value}" for role, value in colors.items()]
    rules = []
    band, texture, emblem = pack.get("band"), pack.get("texture"), pack.get("emblem")
    if band:
        assets.band = band.file
        vars_ += [f"--band-img:url({band.file.removeprefix('assets/')})",
                  f"--band-h:{band.height:g}px", "--band-bg:transparent"]
    if texture:
        assets.texture = texture.file
        rules.append(f"body{{background-image:url({texture.file.removeprefix('assets/')})}}")
    if emblem:
        assets.emblem = emblem.file
    fallback = {"gentium": "Gentium, \"Gentium Plus\"", "charis": "\"Charis SIL\", Charis",
                "andika": "Andika"}.get(text_face, "")
    vars_.append(f"--font-text:td-text,{fallback},Georgia,serif")
    people = ":root{" + ";".join(vars_) + "}\n" + "\n".join(rules) + "\n"
    assets.inline_css = (static_v2("td.css").decode("utf-8") + ":root{"
                         + ";".join(f"--{r}:{v}" for r, v in colors.items()) + "}\n")
    css = (static_v2("td.css").decode("utf-8")
           + "\n/* people layer: " + config.meta_prefix + " */\n"
           + fonts.font_face_css(assets.fonts, "fonts/") + people).encode("utf-8")
    assets.css = "assets/" + _hashed(css, "site", "css")
    assets.css_bytes = len(css)
    (out / assets.css).write_bytes(css)
    js = static_v2("td.js")
    assets.js = "assets/" + _hashed(js, "td", "js")
    (out / assets.js).write_bytes(js)
    js = static_v2("td-dict.js")
    assets.dict_js = "assets/" + _hashed(js, "td-dict", "js")
    (out / assets.dict_js).write_bytes(js)

    if config.theme.favicon and (config.static_dir / config.theme.favicon).is_file():
        assets.icon = config.theme.favicon
    elif emblem:
        assets.icon = emblem.file

    hero = config.theme.hero_image
    if hero and (config.static_dir / hero).is_file():
        try:
            assets.hero = images.derive(config.static_dir / hero, hero, out)
        except (OSError, ValueError) as exc:  # not a photograph Pillow can read
            raise ValueError(f"theme.hero_image: static/{hero} cannot be read as a photograph ({exc})") from exc
    return assets


DICT_JS_STRINGS = ("ui_dict_loading", "ui_dict_failed", "ui_retry", "ui_dict_none", "ui_dict_results",
                   "ui_dict_results_one", "ui_dict_more", "ui_dict_hint", "ui_has_audio")


def dictionary_routes(config: TerradocConfig, loc: str, t: Strings, data, assets: Assets,
                      site: "SiteData | None" = None) -> list[Route]:
    from terradoc import dictionary_v2 as dv

    words, letters = data
    title = t["nav_dictionary"] or config.module_label("dictionary")
    bar = dv.letter_bar(config, letters)
    shared = {"letter_bar": bar, "keyboard": dv.keyboard_keys(config), "dict_root": "",
              "search_index": assets.search_index, "current_letter": None}
    out = [Route(f"{loc}/dictionary/index.html", "pages/dictionary_index.html.j2", "dictionary", title, loc,
                 {**shared, "total": len(words), "folds": dv.folds_for_script(config),
                  "js_strings": {k: t[k] for k in DICT_JS_STRINGS}})]
    for L in letters:
        label = t.ui_dict_other if L.letter == dv.OTHER else L.label
        out.append(Route(f"{loc}/dictionary/{L.file}", "pages/dictionary_letter.html.j2", "dictionary",
                         f"{title}: {label}", loc, {**shared, "letter": L, "current_letter": L.letter}))
    by_letter = {w.id: L for L in letters for w in L.words}
    labels = related_labels(config, t)
    for w in words:
        path = f"{loc}/dictionary/{w.file}"
        related = site.links.related("dictionary", w.id, labels) if site else []
        ctx = dv.entry_context(config, w, t, prefix(path), config.docs_dir, related)
        ctx["back_href"] = f"{quote(by_letter[w.id].file)}#e-{w.id}"
        out.append(Route(path, "pages/dictionary_entry.html.j2", "dictionary",
                         w.entry + (f" {w.homonym}" if w.homonym else ""), loc, ctx))
    out.append(Route(f"{loc}/dictionary.html", "pages/dictionary_compat.html.j2", "dictionary", title, loc,
                     {"search_index": assets.search_index}, sitemap=False))
    return out


def related_labels(config: TerradocConfig, t: Strings) -> dict[str, str]:
    return {k: t[f"nav_{k}"] or config.module_label(k) for k in ("dictionary", "fauna", "ethnobotany", "encyclopedia")}


def routes(config: TerradocConfig, strings: dict[str, Strings], assets: Assets | None = None,
           dict_data=None, site: "SiteData | None" = None) -> list[Route]:
    out: list[Route] = []
    for loc in config.locales:
        t = strings[loc]
        out.append(Route(f"{loc}/index.html", "pages/home.html.j2", "home", config.site_title or config.project_name, loc))
        for mod in config.enabled_modules():
            slug = mod["slug"]
            title = t[f"nav_{slug}"] or mod["name"]
            if slug == "dictionary" and dict_data and dict_data[0] and assets is not None:
                out.extend(dictionary_routes(config, loc, t, dict_data, assets, site))
                continue
            built = content_routes(config, loc, t, slug, title, site) if site else None
            if built is not None:
                out.extend(built)
                continue
            out.append(Route(f"{loc}/{module_path(slug)}", "pages/pending.html.j2", slug, title, loc))
        out.append(Route(f"{loc}/about.html", "pages/about.html.j2", "about", t["nav_about"] or t.ui_about, loc,
                         {"sections": about_sections(t)}))
    return out


# ── P3: the other modules ────────────────────────────────────────────────────

@dataclass
class SiteData:
    """Everything the v2 pages other than the dictionary show, loaded once per build."""
    links: object = None
    fauna: list = field(default_factory=list)
    ethnobotany: list = field(default_factory=list)
    encyclopedia: list = field(default_factory=list)
    corpus: list = field(default_factory=list)
    bibliography: list = field(default_factory=list)
    videos: list = field(default_factory=list)
    pictures: dict = field(default_factory=dict)     # static path -> images.Derived
    uncredited: dict = field(default_factory=dict)   # module -> count of pictures shown without credit


def load_site_data(config: TerradocConfig, dict_words) -> SiteData:
    from terradoc import content_v2 as cv

    site = SiteData(links=cv.Links())
    on = config.is_module_enabled
    for w in dict_words:
        site.links.add("dictionary", w.id, w.file, w.entry, True, w.homonym)
    site.links.add_rows("dictionary", [(w.id, w.row) for w in dict_words])
    if on("fauna"):
        site.fauna = cv.load_species(config, "fauna")
    if on("ethnobotany"):
        site.ethnobotany = cv.load_species(config, "ethnobotany")
    if on("encyclopedia"):
        site.encyclopedia = cv.load_encyclopedia(config)
    if on("corpus"):
        site.corpus = cv.load_corpus(config)
    if on("bibliography"):
        site.bibliography = cv.load_bibliography(config)
    if on("videos"):
        site.videos = cv.load_videos(config, config.docs_dir)
    for kind in ("fauna", "ethnobotany", "encyclopedia"):
        items = getattr(site, kind)
        for i in items:
            site.links.add(kind, i.id, i.file, i.name, i.vernacular)
        site.links.add_rows(kind, [(i.id, i.row) for i in items])
    return site


def static_image(config: TerradocConfig, rel: str) -> Path | None:
    """A picture path from the data, confined to static/ (None if it is not a file there)."""
    if not rel:
        return None
    path = (config.static_dir / rel).resolve()
    root = config.static_dir.resolve()
    return path if root in path.parents and path.is_file() else None


def derive_pictures(config: TerradocConfig, site: SiteData) -> None:
    """WebP copies of every local picture the pages show (in parallel), then each item's
    `picture`: {img, external, credit, source}."""
    from terradoc import content_v2 as cv

    wanted = []
    for kind in ("fauna", "ethnobotany"):
        wanted += [cv.picture_parts(i.row.get("pic_link"))[0] for i in getattr(site, kind)]
    for i in site.encyclopedia:
        wanted += [cv.picture_parts(img.get("url"))[0] for img in i.row.get("images") or [] if isinstance(img, dict)]
    wanted += [cv.picture_parts(v["thumbnail"])[0] for v in site.videos]
    jobs = [(p, rel) for rel in wanted if rel for p in [static_image(config, rel)] if p]
    site.pictures, failed = images.derive_many(jobs, config.docs_dir)
    for rel, error in sorted(failed.items()):
        print(f"  picture not shown (cannot be read as an image): static/{rel}: {error}")

    def pic(link, credit, source, module):
        local, external = cv.picture_parts(link)
        credit, source = re.sub(r"^(foto|photo|imagem|image)\s*:\s*", "", cv.clean(credit), flags=re.I), str(source or "")
        source = source if source.startswith(("http://", "https://")) else ""
        if local and local in site.pictures:
            if not credit:
                site.uncredited[module] = site.uncredited.get(module, 0) + 1
            return {"img": site.pictures[local], "external": "", "credit": credit, "source": source}
        if external:  # another site's file: linked, never loaded with the page (privacy, D27)
            return {"img": None, "external": external, "credit": credit, "source": source,
                    "host": cv.host_of(external)}
        return None

    for kind in ("fauna", "ethnobotany"):
        for i in getattr(site, kind):
            i.row["_picture"] = pic(i.row.get("pic_link"), i.row.get("pic_credit"), i.row.get("pic_source"), kind)
    for i in site.encyclopedia:
        pictures = []
        for img in i.row.get("images") or []:
            p = pic(img.get("url"), img.get("credit"), img.get("source"), "encyclopedia") \
                if isinstance(img, dict) else None
            if p:
                p["alt"] = cv.clean(img.get("alt"))
                pictures.append(p)
        i.row["_pictures"] = pictures
    for v in site.videos:
        local, _ = cv.picture_parts(v["thumbnail"])
        v["poster"] = site.pictures.get(local)


def prune_images(out: Path, site: SiteData | None, assets: Assets) -> None:
    keep = set()
    for d in list(site.pictures.values() if site else []) + ([assets.hero] if assets.hero else []):
        keep.update(p for p, _ in d.webp)
    folder = out / "assets" / "img"
    if folder.is_dir():
        for f in folder.iterdir():
            if f"assets/img/{f.name}" not in keep:
                f.unlink()


def about_sections(t: Strings) -> list[dict]:
    """The site's about_* strings (written by the team, HTML allowed), in v1's order."""
    out = []
    for key in ("mission", "partners", "contact", "citation", "credits"):
        body = t[f"about_{key}"]
        if body:
            out.append({"key": key, "heading": t[f"about_{key}_heading"] or t[f"ui_about_{key}"],
                        "body": body, "plain": key == "citation"})
    return out


def species_fields(kind: str, row: dict, t: Strings) -> list[tuple[str, str, str]]:
    """(key, label, value) of the filled fields of an animal or plant, in reading order
    (names and the scientific name are in the page header)."""
    from terradoc import content_v2 as cv

    keys = (("category", "ui_family"), ("info", "ui_info")) if kind == "fauna" else (
        ("family", "ui_family"), ("usage", "ui_usage"), ("types_of_use", "ui_types_of_use"),
        ("descriptions_of_use", "ui_description_of_use"), ("fruiting_period", "ui_fruiting"),
        ("environment", "ui_environment"))
    return [(key, t[label], cv.clean(row.get(key))) for key, label in keys if cv.clean(row.get(key))]


def content_routes(config: TerradocConfig, loc: str, t: Strings, slug: str, title: str,
                   site: SiteData) -> list[Route] | None:
    """Routes of one module, or None when v2 has no page for it yet (pending page)."""
    from terradoc import content_v2 as cv

    labels = related_labels(config, t)
    out: list[Route] = []
    if slug in ("fauna", "ethnobotany"):
        items = getattr(site, slug)
        sections = cv.groups(items, t[f"ui_{slug}_ungrouped"])
        cv.link_chain([i for g in sections for i in g["items"]])  # previous / next follow the list
        out.append(Route(f"{loc}/{slug}.html", "pages/species_list.html.j2", slug, title, loc,
                         {"kind": slug, "groups": sections, "total": len(items)}))
        for i in items:
            out.append(Route(f"{loc}/{slug}/{i.file}", "pages/species.html.j2", slug, i.name, loc, {
                "kind": slug, "item": i, "row": i.row, "picture": i.row.get("_picture"),
                "fields": species_fields(slug, i.row, t),
                "abundance": [a for a in i.row.get("abundance") or [] if isinstance(a, dict)],
                "related": site.links.related(slug, i.id, labels),
                "back_href": f"../{slug}.html#i-{i.id}", "module_title": title}))
        return out
    if slug == "encyclopedia":
        cats = cv.top_categories(site.encyclopedia)
        out.append(Route(f"{loc}/encyclopedia.html", "pages/encyclopedia_list.html.j2", slug, title, loc,
                         {"items": site.encyclopedia, "categories": cats}))
        titles = {i.id: i for i in site.encyclopedia}
        bib = {b["key"]: b for b in site.bibliography}
        for i in site.encyclopedia:
            path = f"{loc}/encyclopedia/{i.file}"
            refs = []
            for r in i.row.get("resolved_references") or []:
                if not isinstance(r, dict):
                    continue
                key = str(r.get("key") or "")
                refs.append({"bib": bib.get(key), "key": key,
                             "text": cv.delatex(r.get("formatted") or key).replace("*", "")})
            pictures = i.row.get("_pictures") or []
            out.append(Route(path, "pages/article.html.j2", slug, i.name, loc, {
                "item": i, "row": i.row, "module_title": title,
                "html": cv.rewrite_article_html(i.row.get("content_html") or "", prefix(path)),
                "lead_picture": pictures[0] if pictures else None, "gallery": pictures[1:],
                "infobox": [(t[f"infobox_{k}"] or cv.humanize(str(k)), cv.clean(v))
                            for k, v in (i.row.get("infobox") or {}).items() if cv.clean(v)],
                "categories": [str(c) for c in i.row.get("categories") or [] if c],
                "references": refs, "has_bibliography": config.is_module_enabled("bibliography"),
                "see_also": [titles[s] for s in i.row.get("see_also") or [] if s in titles and s != i.id],
                "examples": [e for e in i.row.get("examples") or [] if isinstance(e, dict)],
                "related": site.links.related("encyclopedia", i.id, labels),
                "external": str(i.row.get("url") or "") if str(i.row.get("url") or "").startswith("http") else ""}))
        return out
    if slug == "bibliography":
        out.append(Route(f"{loc}/bibliography.html", "pages/bibliography.html.j2", slug, title, loc,
                         {"refs": site.bibliography}))
        return out
    if slug == "videos":
        out.append(Route(f"{loc}/videos.html", "pages/videos.html.j2", slug, title, loc,
                         {"video_groups": cv.video_groups(site.videos), "total": len(site.videos),
                          "all_audio": bool(site.videos) and all(v["audio"] for v in site.videos)}))
        return out
    if slug == "corpus":
        out.append(Route(f"{loc}/corpus.html", "pages/corpus_list.html.j2", slug, title, loc,
                         {"items": site.corpus}))
        for i in site.corpus:
            out.append(Route(f"{loc}/corpus/{i.file}", "pages/corpus_text.html.j2", slug, i.name, loc,
                             {"item": i, "row": i.row, "module_title": title, "text_lang": i.row["_lang"]}))
        return out
    return None


def page_context(config: TerradocConfig, route: Route, strings: dict[str, Strings],
                 assets: Assets, *, root: str | None = None) -> dict:
    loc = route.locale or (config.default_locale if config.default_locale in config.locales
                           else config.locales[0])
    t = strings[loc]
    root = prefix(route.path) if root is None else root
    loc_root = f"{root}{loc}/"
    tail = route.path.split("/", 1)[1] if route.locale else "index.html"
    base = config.base_url.rstrip("/")
    switches = [{
        "code": code, "label": config.locale_label(code), "current": code == loc,
        "hreflang": strings[code]["html_lang"] or code,
        "href": f"{root}{code}/{quote(tail)}",
        "absolute": f"{base}/{code}/{quote(tail)}" if base and route.locale else "",
    } for code in config.locales]
    nav = [{"label": t[f"nav_{m['slug']}"] or m["name"], "href": f"{loc_root}{module_path(m['slug'])}",
            "current": route.page == m["slug"]} for m in config.enabled_modules()]
    nav.append({"label": t["nav_about"] or t.ui_about, "href": f"{loc_root}about.html",
                "current": route.page == "about"})
    site = {"title": config.site_title or config.project_name,
            "tagline": config.site_tagline or config.project_subtitle,
            "alphabet": config.alphabet, "language_code": config.language_code}
    ctx = {
        "t": t, "locale": loc, "root": root, "loc_root": loc_root, "page": route.page,
        "title": route.title, "description": t["meta_description"] or site["tagline"],
        "site": site, "nav": nav, "locale_switches": switches, "assets": assets,
        "canonical": f"{base}/{quote(route.path)}" if base and route.sitemap else "",
        "search_action": (f"{loc_root}{module_path('dictionary')}"
                          if config.is_module_enabled("dictionary") else ""),
    }
    if route.page == "home":
        ctx.update({
            "sentence": t["home_sentence"] or t["index_hero_subtitle"],
            "hero": assets.hero, "hero_credit": config.theme.hero_credit,
            "hero_alt": config.theme.hero_alt,
            "modules": [{"label": n["label"], "href": n["href"],
                         "description": t[f"card_{m['slug']}_desc"]}
                        for n, m in zip(nav, config.enabled_modules())],
        })
    ctx.update(route.context)
    return ctx


def specimen_context(config: TerradocConfig) -> dict:
    """Words for the font specimen (specimen.html, screenshotted in CI): the headwords with
    the most combining marks, and IPA with the most distinct characters."""
    import unicodedata

    path = config.bundle_dir / "dictionary.json"
    rows = json.loads(path.read_text(encoding="utf-8"))["data"] if path.is_file() else []

    def marks(text: str) -> int:
        return sum(unicodedata.combining(c) > 0 for c in unicodedata.normalize("NFD", text))

    words = sorted({str(r.get("entry") or "") for r in rows} - {""}, key=lambda w: (-marks(w), w))[:24]
    ipa = sorted({str(r.get("ipa") or "") for r in rows} - {""}, key=lambda w: (-len(set(w)), w))[:12]
    letters = list(config.alphabet) or sorted({w[:1].lower() for w in words if w})
    return {"letters": letters, "words": words, "ipa": ipa}


def write_sitemap_v2(out: Path, config: TerradocConfig, pages: list[Route]) -> None:
    """sitemap.xml from the route list (never from whatever is in the directory). Without
    base_url there are no absolute URLs, so no sitemap."""
    from urllib.parse import quote
    from xml.sax.saxutils import escape

    target = out / "sitemap.xml"
    if not config.base_url:
        target.unlink(missing_ok=True)
        print("  No sitemap.xml (set base_url in terradoc.yaml)")
        return
    base = config.base_url.rstrip("/")
    urls = [f"{base}/{quote(r.path)}" for r in pages if r.sitemap]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lines += [f"  <url><loc>{escape(u)}</loc></url>" for u in urls]
    lines.append("</urlset>")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Generated sitemap.xml ({len(urls)} URLs)")


def write_service_worker(out: Path, assets: Assets) -> None:
    """sw.js at the site root. It stores only the shell at install (CSS, the page script, the
    two critical fonts, offline.html); the search index and the rest are stored when used.
    Its version is a hash of those files and of the search index and dictionary script, so
    a release that changes any of them replaces the stored copies."""
    shell = [assets.css, assets.js, *assets.preload, "offline.html"]
    precache = [f for f in shell if f and (out / f).is_file()]
    versioned = precache + [f for f in (assets.dict_js, assets.search_index) if f and (out / f).is_file()]
    digest = hashlib.sha256()
    for f in versioned:
        digest.update(f.encode() + b"\0" + (out / f).read_bytes())
    sw = (static_v2("sw.js").decode("utf-8")
          .replace("'__VERSION__'", json.dumps(digest.hexdigest()[:10]))
          .replace("__PRECACHE__", json.dumps(precache))
          .replace("'__OFFLINE__'", json.dumps("offline.html")))
    (out / "sw.js").write_text(sw, encoding="utf-8")


def build_site_v2(config: TerradocConfig) -> dict:
    """Render the v2 site into config.docs_dir; returns a small report (sizes, counts)."""
    from terradoc.build_site import copy_audio_files, write_robots_txt

    print("=== Building site (templates v2) ===\n")
    out = config.docs_dir
    out.mkdir(parents=True, exist_ok=True)
    strings = {loc: load_strings(loc, config) for loc in config.locales}
    assets = build_assets(config, strings)
    for problem in assets.pack.problems if assets.pack else []:
        print(f"  pack: {problem}")
    env = environment(config)
    copy_audio_files(config)  # before the entry pages, which link only recordings that exist

    from terradoc import dictionary_v2 as dv

    dict_data = dv.load(config) if config.is_module_enabled("dictionary") else ([], [])
    if dict_data[0]:
        assets.search_index = dv.write_index(dict_data[0], out)
    site = load_site_data(config, dict_data[0])
    derive_pictures(config, site)
    for module, n in sorted(site.uncredited.items()):
        print(f"  {module}: {n} picture(s) shown without a credit (D27: add pic_credit / credit)")
    pages = routes(config, strings, assets, dict_data, site)
    for route in pages:
        html = env.get_template(route.template).render(**page_context(config, route, strings, assets))
        target = out / route.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
    print(f"  Rendered {len(pages)} pages")

    default = config.default_locale if config.default_locale in config.locales else config.locales[0]
    root_route = Route("index.html", "pages/language.html.j2", "language", config.site_title, None, sitemap=False)
    ctx = page_context(config, root_route, strings, assets, root="")
    ctx.update({"codes": list(config.locales), "default_locale": default})
    (out / "index.html").write_text(env.get_template(root_route.template).render(**ctx), encoding="utf-8")
    # The error page may be served for a missing path at any depth and under any mount
    # (previews.terradoc.org/<slug>/<branch>/), so it carries its CSS inline and links to
    # the site's public address (or the domain root without base_url).
    nf = Route("404.html", "pages/404.html.j2", "404", strings[default].ui_404_title, None, sitemap=False)
    absolute = config.base_url.rstrip("/") + "/" if config.base_url else "/"
    ctx = page_context(config, nf, strings, assets, root=absolute)
    ctx["standalone"] = True
    (out / "404.html").write_text(env.get_template(nf.template).render(**ctx), encoding="utf-8")

    specimen = Route("specimen.html", "pages/specimen.html.j2", "specimen", "Specimen", None, sitemap=False)
    ctx = page_context(config, specimen, strings, assets, root="")
    ctx.update(specimen_context(config))
    (out / "specimen.html").write_text(env.get_template(specimen.template).render(**ctx), encoding="utf-8")

    offline = Route("offline.html", "pages/offline.html.j2", "offline", "", None, sitemap=False)
    ctx = page_context(config, offline, strings, assets, root="")
    ctx.update({"strings_by_locale": strings, "has_dictionary": bool(assets.search_index)})
    (out / "offline.html").write_text(env.get_template(offline.template).render(**ctx), encoding="utf-8")
    prune_images(out, site, assets)
    write_service_worker(out, assets)
    write_robots_txt(out, config.base_url)
    write_sitemap_v2(out, config, pages)
    report = {
        "pages": len(pages) + 3,
        "css_bytes": assets.css_bytes,
        "fonts": {b.name: b.size for b in assets.fonts},
        "pack": {"name": assets.pack.name if assets.pack else "none",
                 "elements": sorted(assets.pack.elements) if assets.pack else [],
                 "problems": assets.pack.problems if assets.pack else []},
    }
    print(f"  CSS {assets.css_bytes / 1024:.1f} KB; fonts "
          + ", ".join(f"{b.face.family} {b.face.weight}{'i' if b.face.style == 'italic' else ''} "
                      f"{b.size / 1024:.1f} KB" for b in assets.fonts))
    print("\n=== v2 build complete ===")
    return report
