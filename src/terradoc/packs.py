"""v2 motif packs: a people's decoration, owned by the site (meta REDESIGN-PLAN.md, D19/D20).

    config/templates/v2/motifs/<name>/
      pack.yaml          people, and per element: title, description, sources, drawn_by,
                         approved: {by_role, date, note}
      band.svg.j2        a tile repeated along a band (under the header, between sections)
      texture.svg.j2     a page-background tile
      emblem.svg.j2      optional; only when the community has one

The SVG templates get `palette` (role -> #rrggbb). An element that is not approved, has no
sources, does not render or is not a plain drawing is left out, and the site shows its
palette there; `check` warns about it. Only a pack name that does not exist is an error.
`pack: none` turns decoration off. terradoc bundles one neutral pack, `weave`, which carries
no people's design.
"""
from __future__ import annotations

import hashlib
import importlib.resources
import math
import re
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ELEMENTS = ("band", "texture", "emblem")
MAX_BYTES = 4096
NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SVG_NS = "{http://www.w3.org/2000/svg}"
# A plain drawing: shapes, groups and local references only. No <style>, <script>, <image>,
# <foreignObject>, animation, text or links.
ALLOWED_TAGS = {"svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
                "defs", "pattern", "clipPath", "mask", "use", "title", "desc",
                "linearGradient", "radialGradient", "stop"}
_URL = re.compile(r"url\(\s*['\"]?([^)'\"]*)", re.I)


@dataclass
class Element:
    name: str
    template: Path
    meta: dict
    svg: str = ""
    file: str = ""      # written path from the site root
    width: float = 0
    height: float = 0


@dataclass
class Pack:
    name: str
    directory: Path | None
    people: str = ""
    elements: dict[str, Element] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)  # elements left out, and why
    missing: bool = False                               # the named pack does not exist

    def get(self, element: str) -> Element | None:
        return self.elements.get(element)


def pack_dirs(config) -> list[Path]:
    """Where a pack is looked up: the site's v2 templates first, then terradoc's."""
    site = config.config_dir / "templates" / "v2" / "motifs"
    bundled = Path(str(importlib.resources.files("terradoc.templates_v2"))) / "motifs"
    return [site, bundled]


def load(config) -> Pack:
    """The site's pack with its usable elements; problems listed, never raised."""
    name = (config.theme.pack or "").strip()
    if name in ("", "none"):
        return Pack("none", None)
    if not NAME.match(name):
        return Pack(name, None, missing=True,
                    problems=[f"theme.pack: '{name}' is not a pack name (letters, digits, - and _)"])
    directory = next((d / name for d in pack_dirs(config) if (d / name / "pack.yaml").is_file()), None)
    if directory is None:
        return Pack(name, None, missing=True,
                    problems=[f"theme.pack: no pack '{name}' (looked in config/templates/v2/motifs/ "
                              "and terradoc's own)"])
    pack = Pack(name, directory)
    try:
        meta = yaml.safe_load((directory / "pack.yaml").read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        pack.problems.append(f"{name}/pack.yaml: {exc}")
        return pack
    if not isinstance(meta, dict):
        pack.problems.append(f"{name}/pack.yaml: expected a mapping with 'people' and 'elements'")
        return pack
    pack.people = str(meta.get("people") or "")
    elements = meta.get("elements") or {}
    if not isinstance(elements, dict):
        pack.problems.append(f"{name}/pack.yaml: 'elements' must be a mapping")
        return pack
    for el, info in elements.items():
        if el not in ELEMENTS:
            pack.problems.append(f"{name}/pack.yaml: unknown element '{el}' (elements: {', '.join(ELEMENTS)})")
            continue
        info = info if isinstance(info, dict) else {}
        template = directory / f"{el}.svg.j2"
        if not template.is_file():
            pack.problems.append(f"{name}: {el} is listed in pack.yaml but {el}.svg.j2 is missing")
            continue
        approved = info.get("approved")
        if not (isinstance(approved, dict) and approved.get("by_role") and approved.get("date")):
            pack.problems.append(f"{name}: {el} has no 'approved: {{by_role, date}}' in pack.yaml; "
                                 "it is not used")
            continue
        if not info.get("sources"):
            pack.problems.append(f"{name}: {el} lists no 'sources' in pack.yaml; it is not used")
            continue
        pack.elements[el] = Element(el, template, info)
    for template in sorted(directory.glob("*.svg.j2")):
        el = template.name.removesuffix(".svg.j2")
        if el in ELEMENTS and el not in elements:
            pack.problems.append(f"{name}: {template.name} is not listed in pack.yaml; it is not used")
    return pack


def render(pack: Pack, palette: dict[str, str], out_root: Path, sub: str = "assets/pack") -> Pack:
    """Render the usable elements with the palette and write them (hashed names); an element
    that fails is dropped and listed in pack.problems."""
    from jinja2 import Environment, StrictUndefined

    env = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)
    for el in list(pack.elements.values()):
        try:
            svg = env.from_string(el.template.read_text(encoding="utf-8")).render(palette=palette)
        except Exception as exc:  # a broken drawing must not break the site
            pack.problems.append(f"{pack.name}: {el.name}.svg.j2 does not render ({exc}); not used")
            del pack.elements[el.name]
            continue
        svg = svg.strip() + "\n"
        problem, size = inspect_svg(svg)
        if problem:
            pack.problems.append(f"{pack.name}: {el.name}.svg.j2 {problem}; not used")
            del pack.elements[el.name]
            continue
        data = svg.encode("utf-8")
        name = f"{sub}/{el.name}.{hashlib.sha256(data).hexdigest()[:10]}.svg"
        (out_root / sub).mkdir(parents=True, exist_ok=True)
        (out_root / name).write_bytes(data)
        el.svg, el.file = svg, name
        el.width, el.height = size
    return pack


def problems(config, palette: dict[str, str]) -> tuple[list[str], bool]:
    """What `check` reports: (problems, pack missing). Renders into a scratch directory, so
    a drawing that would be dropped at build time is reported now."""
    pack = load(config)
    if pack.elements:
        with tempfile.TemporaryDirectory() as tmp:
            render(pack, palette, Path(tmp))
    return pack.problems, pack.missing


def _length(value: str | None) -> float | None:
    try:
        n = float(value or "")
    except ValueError:
        return None
    return n if math.isfinite(n) and n > 0 else None


def inspect_svg(svg: str) -> tuple[str, tuple[float, float]]:
    """("", (width, height)) for a plain drawing, else (what is wrong, (0, 0))."""
    if len(svg.encode("utf-8")) > MAX_BYTES:
        return f"is larger than {MAX_BYTES} bytes", (0, 0)
    if "<!DOCTYPE" in svg or "<!ENTITY" in svg:
        return "has a DOCTYPE or entities", (0, 0)
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        return f"is not well-formed XML ({exc})", (0, 0)
    if root.tag not in (f"{SVG_NS}svg", "svg"):
        return "does not start with <svg>", (0, 0)
    for node in root.iter():
        tag = node.tag.removeprefix(SVG_NS)
        if tag not in ALLOWED_TAGS:
            return f"has <{tag}>; only shapes, groups and local references are allowed", (0, 0)
        for attr, value in node.attrib.items():
            local = attr.rsplit("}", 1)[-1].lower()
            if local.startswith("on"):
                return "has event handlers", (0, 0)
            if local == "style":
                return "has a style attribute; use presentation attributes (fill, stroke)", (0, 0)
            if local == "href" and not value.startswith("#"):
                return "has external references", (0, 0)
            for url in _URL.findall(value):
                if not url.strip().startswith("#"):
                    return "has external references", (0, 0)
    width, height = _length(root.get("width")), _length(root.get("height"))
    if width is None or height is None:
        return "needs a positive width and height on <svg>", (0, 0)
    return "", (width, height)


def svg_problem(svg: str) -> str:
    return inspect_svg(svg)[0]
