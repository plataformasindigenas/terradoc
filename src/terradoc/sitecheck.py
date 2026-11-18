"""Checks on a built site (v2 gate): links, page weight, sitemap, file count.

    python -m terradoc.sitecheck <site dir> [--budget-kb 150] [--json]

Exit status 1 on a broken link, a page over budget or an invalid sitemap.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

BUDGET_KB = 150  # per page before photos and audio, gzipped (REDESIGN-PLAN.md, Budgets)
MAX_FILES = 20000  # sitepull's limit


class _Refs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str, dict]] = []  # (tag, url, attrs)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for key in ("href", "src"):
            if a.get(key):
                self.links.append((tag, a[key], a))
        if a.get("srcset"):
            for part in a["srcset"].split(","):
                url = part.strip().split(" ")[0]
                if url:
                    self.links.append((tag, url, a))


def _refs(html: str) -> list[tuple[str, str, dict]]:
    p = _Refs()
    p.feed(html)
    return p.links


def _target(site: Path, page: Path, url: str) -> Path | None:
    """The file a local URL points to, or None for external/anchor-only URLs. The result may
    lie outside `site`; callers check with _inside() before reading it."""
    parts = urlsplit(url)
    if parts.scheme or parts.netloc or url.startswith(("#", "mailto:", "tel:", "data:")):
        return None
    path = unquote(parts.path)
    if not path:
        return None
    target = (site / path.lstrip("/")) if path.startswith("/") else (page.parent / path)
    target = target.resolve()
    if target.is_dir():
        target = target / "index.html"
    return target


def _inside(site: Path, target: Path) -> bool:
    return target == site or site in target.parents


def broken_links(site: Path) -> list[str]:
    site = site.resolve()
    out = []
    for page in sorted(site.rglob("*.html")):
        for tag, url, _ in _refs(page.read_text(encoding="utf-8")):
            target = _target(site, page, url)
            if target is None:
                continue
            if not _inside(site, target):
                out.append(f"{page.relative_to(site)}: {url} leaves the site")
            elif not target.is_file():
                out.append(f"{page.relative_to(site)}: <{tag}> {url} not found")
    for css in sorted(site.rglob("*.css")):
        for url in re.findall(r"url\(([^)]+)\)", css.read_text(encoding="utf-8")):
            url = url.strip("'\" ")
            target = _target(site, css, url)
            if target is None:
                continue
            if not _inside(site, target):
                out.append(f"{css.relative_to(site)}: url({url}) leaves the site")
            elif not target.is_file():
                out.append(f"{css.relative_to(site)}: url({url}) not found")
    return out


def _gz(data: bytes) -> int:
    return len(gzip.compress(data, compresslevel=9, mtime=0))


def page_weights(site: Path) -> dict[str, int]:
    """Gzipped bytes per page before photos and audio: the HTML, its stylesheets and
    scripts, preloaded fonts and every font its stylesheets declare (an upper bound: the
    browser fetches only the faces a page uses)."""
    site = site.resolve()
    weights = {}
    for page in sorted(site.rglob("*.html")):
        html = page.read_bytes()
        total = _gz(html)
        seen: set[Path] = set()
        for tag, url, attrs in _refs(html.decode("utf-8")):
            critical = (tag == "link" and attrs.get("rel") in ("stylesheet", "preload")) or tag == "script"
            target = _target(site, page, url) if critical else None
            if target is None or target in seen or not _inside(site, target) or not target.is_file():
                continue
            seen.add(target)
            data = target.read_bytes()
            total += len(data) if target.suffix == ".woff2" else _gz(data)
            if target.suffix == ".css":
                for font in re.findall(r"url\(([^)]+\.woff2)\)", data.decode("utf-8")):
                    f = _target(site, target, font.strip("'\" "))
                    if f is not None and f not in seen and _inside(site, f) and f.is_file():
                        seen.add(f)
                        total += f.stat().st_size
        weights[page.relative_to(site).as_posix()] = total
    return weights


def sitemap_problems(site: Path) -> list[str]:
    path = site / "sitemap.xml"
    if not path.exists():
        return []
    import xml.etree.ElementTree as ET

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return [f"sitemap.xml: {exc}"]
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    # The site's own address, from robots.txt ("Sitemap: <base>/sitemap.xml"), so a site
    # published below a path (https://host/slug/) maps to the right files.
    base_path = ""
    robots = site / "robots.txt"
    if robots.is_file():
        m = re.search(r"^Sitemap:\s*(\S+)/sitemap\.xml\s*$", robots.read_text(encoding="utf-8"), re.M)
        if m:
            base_path = urlsplit(m.group(1)).path.rstrip("/")
    site_root = site.resolve()
    out = []
    for loc in root.findall("s:url/s:loc", ns):
        url = (loc.text or "").strip()
        parts = urlsplit(url)
        if not (parts.scheme and parts.netloc):
            out.append(f"sitemap.xml: {url} is not absolute")
            continue
        path = unquote(parts.path)
        if base_path and not path.startswith(base_path + "/"):
            out.append(f"sitemap.xml: {url} is outside the site's address")
            continue
        target = (site_root / path[len(base_path):].lstrip("/")).resolve()
        if not _inside(site_root, target) or not target.is_file():
            out.append(f"sitemap.xml: {url} has no file")
        if parts.path.endswith("404.html"):
            out.append(f"sitemap.xml: {url} is the error page")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("site", type=Path)
    ap.add_argument("--budget-kb", type=float, default=BUDGET_KB)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    files = [p for p in args.site.rglob("*") if p.is_file()]
    weights = page_weights(args.site)
    over = {p: w for p, w in weights.items() if w > args.budget_kb * 1024}
    links = broken_links(args.site)
    sitemap = sitemap_problems(args.site)
    report = {
        "files": len(files), "bytes": sum(p.stat().st_size for p in files),
        "heaviest": sorted(weights.items(), key=lambda kv: -kv[1])[:5],
        "over_budget": over, "broken_links": links, "sitemap": sitemap,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{report['files']} files, {report['bytes'] / 1e6:.1f} MB")
        for p, w in report["heaviest"]:
            print(f"  {w / 1024:6.1f} KB  {p}")
        for p, w in over.items():
            print(f"::error::{p}: {w / 1024:.1f} KB gzipped, budget {args.budget_kb:g} KB")
        for line in links[:50] + sitemap[:50]:
            print(f"::error::{line}")
    bad = bool(over or links or sitemap or len(files) > MAX_FILES)
    if len(files) > MAX_FILES:
        print(f"::error::{len(files)} files, over sitepull's MAX_FILES ({MAX_FILES})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
