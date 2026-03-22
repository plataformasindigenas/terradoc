"""Site builder for terradoc — renders HTML pages for all locales."""

import json
import shutil
from dataclasses import replace as dc_replace
from pathlib import Path

import kodudo  # type: ignore[import-untyped]
import yaml

from terradoc.config import TerradocConfig
from terradoc.markdown_utils import generate_toc


def get_module_intensity(config: TerradocConfig, page_name: str) -> str:
    """Return the intensity level for a module page."""
    return config.theme.module_intensity.get(page_name, "balanced")


def load_locale(locale: str, config: TerradocConfig) -> dict:
    path = config.locales_dir / f"{locale}.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_json_if_exists(path: Path) -> dict:
    """Load a JSON file if it exists, otherwise return an empty dict."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_locale_switches(locale: str, base_path: str, current_page_path: str,
                        config: TerradocConfig) -> list[dict[str, str | bool]]:
    """Build locale switcher metadata for the current page."""
    switches: list[dict[str, str | bool]] = []
    for code in config.locales:
        switches.append({
            "code": code,
            "label": config.locale_label(code),
            "href": f"{base_path}{code}/{current_page_path}",
            "is_current": code == locale,
        })
    return switches


def render_article_pages(locale: str, translations: dict, config: TerradocConfig):
    """Render individual encyclopedia article pages."""
    enc_file = config.data_dir / "encyclopedia.json"
    if not enc_file.exists():
        print(f"  [{locale}] No encyclopedia.json found, skipping article pages")
        return

    with open(enc_file, "r", encoding="utf-8") as f:
        enc_data = json.load(f)

    entries = enc_data["data"]
    if not entries:
        return

    all_titles = {e["id"]: e.get("title", e["id"]) for e in entries}
    enc_dir = config.docs_dir / locale / "encyclopedia"
    enc_dir.mkdir(parents=True, exist_ok=True)

    template_path = config.template_dir / "article.html.j2"
    modules = config.enabled_modules()
    theme_dict = config.theme.to_dict()
    site_dict = config.site_context()

    for entry in entries:
        entry_id = entry.get("id", "")
        if not entry_id:
            continue

        content_html = entry.get("content_html", "")
        toc_html = ""
        if content_html:
            toc_html, content_html = generate_toc(content_html, entry_id)
            entry["content_html"] = content_html

        html = kodudo.render(
            data=[entry],
            template=template_path,
            context={
                "entry": entry,
                "toc_html": toc_html,
                "all_titles": all_titles,
                "t": translations,
                "locale": locale,
                "locale_switches": get_locale_switches(
                    locale, "../../", f"encyclopedia/{entry_id}.html", config
                ),
                "base_path": "../../",
                "page": "encyclopedia",
                "current_page_path": f"encyclopedia/{entry_id}.html",
                "title": entry.get("title", ""),
                "site": site_dict,
                "theme": theme_dict,
                "modules": modules,
                "intensity": get_module_intensity(config, "encyclopedia"),
            },
            template_dirs=(config.template_dir, config.bundled_template_dir),
        )

        output_path = enc_dir / f"{entry_id}.html"
        output_path.write_text(html, encoding="utf-8")

    print(f"  [{locale}] Rendered {len(entries)} article pages in encyclopedia/")


def render_about_page(locale: str, translations: dict, config: TerradocConfig):
    """Render the about page for a given locale."""
    template_path = config.template_dir / "about.html.j2"
    if not template_path.exists():
        return

    modules = config.enabled_modules()
    theme_dict = config.theme.to_dict()
    site_dict = config.site_context()

    html = kodudo.render(
        data=[{}],
        template=template_path,
        context={
            "t": translations,
            "locale": locale,
            "locale_switches": get_locale_switches(
                locale, "../", "about.html", config
            ),
            "base_path": "../",
            "page": "about",
            "current_page_path": "about.html",
            "site": site_dict,
            "theme": theme_dict,
            "modules": modules,
            "intensity": "balanced",
        },
        template_dirs=(config.template_dir, config.bundled_template_dir),
    )

    output_path = config.docs_dir / locale / "about.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"  [{locale}] Rendered about")


def build_locale(locale: str, translations: dict, config: TerradocConfig):
    """Build all pages for a given locale."""
    locale_dir = config.docs_dir / locale
    locale_dir.mkdir(parents=True, exist_ok=True)

    modules = config.enabled_modules()
    theme_dict = config.theme.to_dict()
    site_dict = config.site_context()

    for config_path in sorted(config.config_dir.glob("*.yaml")):
        name = config_path.stem
        if name != "index" and not config.is_module_enabled(name):
            continue

        client_index = {}
        graph_data = {}
        if name == "encyclopedia":
            client_index = load_json_if_exists(config.data_dir / "encyclopedia_index.json")
            if config.is_graph_enabled("encyclopedia"):
                graph_data = load_json_if_exists(config.data_dir / "encyclopedia_graph.json")

        batch = kodudo.load_config(config_path)

        # If the template doesn't exist locally, resolve from bundled templates
        if not batch.config.resolved_template.exists():
            template_name = Path(batch.config.template).name
            bundled = config.template_dir / template_name
            if bundled.exists():
                batch = dc_replace(batch, config=dc_replace(
                    batch.config,
                    template=bundled,
                    template_dirs=(config.template_dir, config.bundled_template_dir),
                ))
        else:
            batch = dc_replace(batch, config=dc_replace(
                batch.config,
                template_dirs=(config.template_dir, config.bundled_template_dir),
            ))

        original_output = str(batch.config.output)
        output_filename = Path(original_output).name
        locale_output = f"../docs/{locale}/{output_filename}"

        kodudo.cook_from_config(
            batch.config,
            context={
                "t": translations,
                "locale": locale,
                "locale_switches": get_locale_switches(
                    locale, "../", output_filename, config
                ),
                "base_path": "../",
                "site": site_dict,
                "theme": theme_dict,
                "modules": modules,
                "page": name,
                "current_page_path": output_filename,
                "client_index": client_index,
                "graph_data": graph_data,
                "intensity": get_module_intensity(config, name),
            },
            output=locale_output,
        )
        print(f"  [{locale}] Rendered {name}")

    if config.is_module_enabled("encyclopedia"):
        render_article_pages(locale, translations, config)

    # Always render the about page (standalone, not a module)
    render_about_page(locale, translations, config)

    for name in ("dictionary-data", "encyclopedia-data", "encyclopedia-graph", "recordings-data"):
        src = config.docs_dir / f"{name}.json"
        if src.exists():
            dst = locale_dir / f"{name}.json"
            shutil.copy2(src, dst)


def build_language_picker(config: TerradocConfig):
    """Generate root docs/index.html with language selection."""
    site = config.site_context()
    theme_dict = config.theme.to_dict()

    locales = [
        {"code": loc, "label": config.locale_label(loc)}
        for loc in config.locales
    ]

    template_path = config.template_dir / "language_picker.html.j2"
    page_html = kodudo.render(
        data=[{}],
        template=template_path,
        context={
            "site": site,
            "theme": theme_dict,
            "locales": locales,
            "default_locale": config.default_locale,
        },
        template_dirs=(config.template_dir,),
    )

    (config.docs_dir / "index.html").write_text(page_html, encoding="utf-8")
    print("  Generated language picker at docs/index.html")


def copy_static_assets(config: TerradocConfig):
    """Copy bundled static assets (JS, CSS, fonts) to docs/."""
    import importlib.resources

    for subdir in ("js", "css", "fonts"):
        dest = config.docs_dir / subdir
        dest.mkdir(parents=True, exist_ok=True)
        package = f"terradoc.static.{subdir}"
        try:
            src_dir = importlib.resources.files(package)
        except ModuleNotFoundError:
            continue
        for src_file in src_dir.iterdir():
            if src_file.is_file() and src_file.name != "__init__.py":
                shutil.copy2(str(src_file), str(dest / src_file.name))
    print("  Copied static assets (js/, css/, fonts/) to docs/")


def write_robots_txt(docs_dir: Path):
    """Write a robots.txt file to the docs directory."""
    content = "User-agent: *\nAllow: /\nSitemap: sitemap.xml\n"
    (docs_dir / "robots.txt").write_text(content, encoding="utf-8")
    print("  Generated robots.txt")


def write_sitemap(docs_dir: Path, config: TerradocConfig, locales: list[str]):
    """Generate a sitemap.xml listing all HTML pages in the docs directory."""
    urls: list[str] = []
    for html_file in sorted(docs_dir.rglob("*.html")):
        rel = html_file.relative_to(docs_dir).as_posix()
        urls.append(rel)

    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for url in urls:
        lines.append(f"  <url><loc>{url}</loc></url>")
    lines.append("</urlset>")

    (docs_dir / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Generated sitemap.xml ({len(urls)} URLs)")


def build_404_page(config: TerradocConfig):
    """Render a custom 404 page to docs/404.html."""
    site = config.site_context()
    theme_dict = config.theme.to_dict()
    translations = {}
    if config.locales:
        translations = load_locale(config.default_locale, config)

    template_path = config.template_dir / "404.html.j2"
    if not template_path.exists():
        print("  Skipping 404 page (no template found)")
        return

    page_html = kodudo.render(
        data=[{}],
        template=template_path,
        context={
            "site": site,
            "theme": theme_dict,
            "t": translations,
            "locale": config.default_locale,
            "base_path": "",
            "page": "404",
            "modules": config.enabled_modules(),
        },
        template_dirs=(config.template_dir, config.bundled_template_dir),
    )

    (config.docs_dir / "404.html").write_text(page_html, encoding="utf-8")
    print("  Generated 404.html")


def build_site(config: TerradocConfig):
    """Build the complete site for all locales."""
    print("=== Building i18n Site ===\n")

    copy_static_assets(config)

    for locale in config.locales:
        print(f"Building locale: {locale}")
        translations = load_locale(locale, config)
        build_locale(locale, translations, config)
        print()

    build_language_picker(config)
    build_404_page(config)
    write_robots_txt(config.docs_dir)
    write_sitemap(config.docs_dir, config, config.locales)
    print("\n=== i18n Build Complete ===")
