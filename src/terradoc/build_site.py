"""Site builder for terradoc — renders HTML pages for all locales."""

import json
import shutil
from dataclasses import replace as dc_replace
from pathlib import Path

from terradoc import _kodudo as kodudo
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
    enc_file = config.bundle_dir / "encyclopedia.json"
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

    template_path = config.find_template("article.html.j2")
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
            template_dirs=config.template_dirs,
        )

        output_path = enc_dir / f"{entry_id}.html"
        output_path.write_text(html, encoding="utf-8")

    print(f"  [{locale}] Rendered {len(entries)} article pages in encyclopedia/")


def render_about_page(locale: str, translations: dict, config: TerradocConfig):
    """Render the about page for a given locale."""
    template_path = config.find_template("about.html.j2")
    if template_path is None:
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
        template_dirs=config.template_dirs,
    )

    output_path = config.docs_dir / locale / "about.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"  [{locale}] Rendered about")


def remap_bundle_input(page_config, config: TerradocConfig) -> Path:
    """Point a page config's generated-JSON input at the export bundle.

    Inputs that live in data/ and end in .json are build products (the
    sources are TSV/YAML/Markdown), so they are read from config.bundle_dir.
    Anything else is left untouched.
    """
    resolved = page_config.resolved_input
    if resolved.suffix == ".json" and resolved.parent.resolve() == config.data_dir.resolve():
        return config.bundle_dir.resolve() / resolved.name
    return page_config.input


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
            client_index = load_json_if_exists(config.bundle_dir / "encyclopedia_index.json")
            if config.is_graph_enabled("encyclopedia"):
                graph_data = load_json_if_exists(config.bundle_dir / "encyclopedia_graph.json")

        batch = kodudo.load_config(config_path)

        # If the template doesn't exist locally, resolve from bundled templates
        if not batch.config.resolved_template.exists():
            template_name = Path(batch.config.template).name
            bundled = config.find_template(template_name)
            if bundled is not None:
                batch = dc_replace(batch, config=dc_replace(
                    batch.config,
                    template=bundled,
                    template_dirs=config.template_dirs,
                ))
        else:
            batch = dc_replace(batch, config=dc_replace(
                batch.config,
                template_dirs=config.template_dirs,
            ))

        original_output = str(batch.config.output)
        output_filename = Path(original_output).name
        # Page configs say ../docs/<page>.html and ../data/<x>.json; remap both
        # in memory so --out / --bundle-dir work without editing site repos.
        locale_output = config.docs_dir.resolve() / locale / output_filename
        batch = dc_replace(batch, config=dc_replace(
            batch.config, input=remap_bundle_input(batch.config, config),
        ))

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
    """Generate root docs/index.html, which sends visitors to their language.

    No picker is shown: the page redirects to the locale the visitor last chose with the
    language switch, else the first of the browser's languages the site has, else
    default_locale. The locale links stay in the page for clients that do not redirect.
    """
    site = config.site_context()
    theme_dict = config.theme.to_dict()

    locales = [
        {"code": loc, "label": config.locale_label(loc)}
        for loc in config.locales
    ]

    template_path = config.find_template("language_picker.html.j2")
    page_html = kodudo.render(
        data=[{}],
        template=template_path,
        context={
            "site": site,
            "theme": theme_dict,
            "locales": locales,
            # Redirect only to a locale that is built.
            "default_locale": (config.default_locale if config.default_locale in config.locales
                               else config.locales[0]),
        },
        template_dirs=config.template_dirs,
    )

    (config.docs_dir / "index.html").write_text(page_html, encoding="utf-8")
    print("  Generated language redirect at docs/index.html")


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


def copy_audio_files(config: TerradocConfig):
    """Mirror data/audio/*.webm → docs/audio/. Files starting with '_' (reports
    like _import_report.md) are skipped. With data/audio/manifest.tsv, only the
    files it lists with consent are published."""
    from terradoc.checks import CONSENT_VALUES
    from terradoc.cross_linker import read_audio_manifest

    src_dir = config.data_dir / "audio"
    if not src_dir.exists():
        return
    manifest = read_audio_manifest(src_dir)
    allowed = None if manifest is None else {
        row["file"] for row in manifest if row["consent"] in CONSENT_VALUES}
    dest_dir = config.docs_dir / "audio"
    dest_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for src_file in sorted(src_dir.iterdir()):
        if not src_file.is_file() or src_file.name.startswith("_"):
            continue
        if src_file.suffix.lower() != ".webm":
            continue
        if allowed is not None and src_file.name not in allowed:
            continue
        shutil.copy2(str(src_file), str(dest_dir / src_file.name))
        n += 1
    if n:
        print(f"  Copied {n} audio files to docs/audio/")


def write_robots_txt(docs_dir: Path, base_url: str = ""):
    """Write a robots.txt file to the docs directory (Sitemap only with an absolute URL)."""
    content = "User-agent: *\nAllow: /\n"
    if base_url:
        content += f"Sitemap: {base_url.rstrip('/')}/sitemap.xml\n"
    (docs_dir / "robots.txt").write_text(content, encoding="utf-8")
    print("  Generated robots.txt")


def write_sitemap(docs_dir: Path, config: TerradocConfig, locales: list[str]):
    """Generate sitemap.xml: absolute URLs of the content pages.

    The protocol needs absolute URLs, so without ``base_url`` no sitemap is written (and a
    stale one is removed). The error page and the root language redirect are left out.
    """
    from urllib.parse import quote
    from xml.sax.saxutils import escape

    target = docs_dir / "sitemap.xml"
    if not config.base_url:
        target.unlink(missing_ok=True)
        print("  No sitemap.xml (set base_url in terradoc.yaml)")
        return
    base = config.base_url.rstrip("/")
    skip = {"404.html", "index.html"}
    urls = [
        f"{base}/{quote(rel)}"
        for rel in (p.relative_to(docs_dir).as_posix() for p in sorted(docs_dir.rglob("*.html")))
        if rel not in skip
    ]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lines += [f"  <url><loc>{escape(u)}</loc></url>" for u in urls]
    lines.append("</urlset>")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Generated sitemap.xml ({len(urls)} URLs)")


def build_404_page(config: TerradocConfig):
    """Render a custom 404 page to docs/404.html (links are root-relative)."""
    site = config.site_context()
    theme_dict = config.theme.to_dict()
    translations = {}
    if config.locales:
        translations = load_locale(config.default_locale, config)

    template_path = config.find_template("404.html.j2")
    if template_path is None:
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
            # Served for a missing path at any depth, so links are root-relative
            # (a site lives at its domain's root); pages are under /<locale>/.
            "base_path": "/",
            "nav_prefix": f"/{config.default_locale}/",
            "page": "404",
            "modules": config.enabled_modules(),
        },
        template_dirs=config.template_dirs,
    )

    (config.docs_dir / "404.html").write_text(page_html, encoding="utf-8")
    print("  Generated 404.html")


def build_site(config: TerradocConfig):
    """Build the complete site for all locales."""
    print("=== Building i18n Site ===\n")

    copy_static_assets(config)
    copy_audio_files(config)

    for locale in config.locales:
        print(f"Building locale: {locale}")
        translations = load_locale(locale, config)
        build_locale(locale, translations, config)
        print()

    build_language_picker(config)
    build_404_page(config)
    write_robots_txt(config.docs_dir, config.base_url)
    write_sitemap(config.docs_dir, config, config.locales)
    print("\n=== i18n Build Complete ===")


# ── 0.11: render step (bundle → site), static/ and release info ──────────

def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_project_static(config: TerradocConfig) -> dict[str, str]:
    """Copy <project>/static/ verbatim into the site root.

    Returns {relative path: sha256} so the caller can prove afterwards that
    no generated file overwrote a static one. Symlinks are refused: the site
    must be plain files.
    """
    src_root = config.static_dir
    copied: dict[str, str] = {}
    if src_root.is_symlink():
        raise ValueError("static/ is a symlink; it must be a real directory")
    if not src_root.is_dir():
        return copied
    for src in sorted(src_root.rglob("*")):
        rel = src.relative_to(src_root).as_posix()
        if src.is_symlink():
            raise ValueError(f"static/{rel} is a symlink; only regular files are allowed")
        if src.is_dir():
            continue
        dest = config.docs_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied[rel] = _sha256(src)
    print(f"  Copied {len(copied)} files from static/")
    return copied


def verify_static_untouched(config: TerradocConfig, copied: dict[str, str]) -> None:
    clobbered = [rel for rel, digest in copied.items()
                 if _sha256(config.docs_dir / rel) != digest]
    if clobbered:
        raise ValueError(
            "generated files overwrote files from static/ (rename them): "
            + ", ".join(sorted(clobbered)[:10])
        )


def _git(config: TerradocConfig, *args: str) -> str:
    import subprocess

    try:
        out = subprocess.run(["git", "-C", str(config.base_dir), *args],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def write_release_info(config: TerradocConfig, *, owned: bool = False) -> Path:
    """Write .release.json: what this site was built from (no timestamps, so
    identical inputs give an identical file)."""
    import os

    from terradoc.export import read_manifest, terradoc_version

    files = [p for p in config.docs_dir.rglob("*") if p.is_file() and p.name != ".release.json"]
    try:
        modules = read_manifest(config).get("modules", {})
    except FileNotFoundError:
        modules = {}
    info = {
        "project": config.meta_prefix,
        "terradoc_version": terradoc_version(),
        "source_commit": os.environ.get("GITHUB_SHA") or _git(config, "rev-parse", "HEAD"),
        "source_ref": os.environ.get("GITHUB_REF_NAME") or _git(config, "rev-parse", "--abbrev-ref", "HEAD"),
        "files": len(files),
        "bytes": sum(p.stat().st_size for p in files),
        "modules": modules,  # record counts, compared by `terradoc guard`
        # True only if every render into this directory started from an empty
        # one, i.e. everything in it came from terradoc. --clean requires it.
        "owned_by_terradoc": owned,
    }
    path = config.docs_dir / ".release.json"
    path.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    return path


def _overlaps(a: Path, b: Path) -> bool:
    """True if a and b are the same directory or one contains the other."""
    return a == b or a in b.parents or b in a.parents


def assert_safe_to_clean(config: TerradocConfig) -> None:
    """Refuse to empty an output directory unless it is plainly ours.

    `--clean` deletes the output directory, so it must not be (or contain, or
    sit inside) the project, its sources, its templates or the bundle, and a
    non-empty directory is only deleted if a previous render marked it with
    .release.json.
    """
    if config.output_dir is None:
        raise ValueError("--clean needs --out (refusing to delete the project's docs/)")
    out = config.docs_dir.resolve()
    base = config.base_dir.resolve()
    if out == base or out in base.parents:
        raise ValueError(f"--clean refused: --out {out} is the project directory or contains it")
    protected = {
        "data/": config.data_dir, "config/": config.config_dir, "static/": config.static_dir,
        "locales/": config.locales_dir, "the bundle": config.bundle_dir,
        "the templates": config.local_template_dir,
    }
    for label, path in protected.items():
        if _overlaps(out, path.resolve()):
            raise ValueError(f"--clean refused: --out {out} overlaps {label} ({path})")
    if out.exists() and any(out.iterdir()) and not _dir_owned(out):
        raise ValueError(
            f"--clean refused: {out} holds files terradoc did not create (it was not built "
            "into an empty directory by terradoc >= 0.11). Check it, delete it yourself once, "
            "and --clean will work from then on."
        )


def _dir_owned(out: Path) -> bool:
    """Did every render into `out` start from an empty directory?"""
    marker = out / ".release.json"
    if not marker.is_file():
        return False
    try:
        return json.loads(marker.read_text(encoding="utf-8")).get("owned_by_terradoc") is True
    except (OSError, ValueError):
        return False


def render_site(config: TerradocConfig, *, clean: bool = False) -> None:
    """Render the site from the export bundle into config.docs_dir."""
    from terradoc.export import read_manifest
    from terradoc.index_builder import copy_data_to_docs

    read_manifest(config)  # fail early, clearly, if export has not run

    # The bundle may be older than the sources: re-check what must never be
    # published from a stale bundle (consent revoked since the export), and
    # static/ (symlinks, collisions with generated files).
    from terradoc.checks import format_issues, render_preflight

    issues = render_preflight(config)
    if issues:
        raise ValueError("render refused:\n" + format_issues(issues))

    if clean:
        assert_safe_to_clean(config)
        if config.docs_dir.exists():
            shutil.rmtree(config.docs_dir)
    config.docs_dir.mkdir(parents=True, exist_ok=True)
    started_empty = not any(config.docs_dir.iterdir())
    owned = started_empty or _dir_owned(config.docs_dir)

    copied = copy_project_static(config)
    if config.theme.templates == "v2":
        from terradoc.build_v2 import build_site_v2

        build_site_v2(config)
    else:
        copy_data_to_docs(config)
        print()
        build_site(config)
    write_release_info(config, owned=owned)
    verify_static_untouched(config, copied)
