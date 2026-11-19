"""v2 palette: five colour roles per site, each named after a material.

    theme:
      palette:
        ground:  {color: "#F4F1EA", material: "argila branca"}   # page background
        ink:     {color: "#111827", material: "carvão e resina"}  # text
        primary: {color: "#C81F2D", material: "urucum"}           # links, headings, buttons
        fill:    {color: "#D4A03A", material: "pena amarela"}     # bands, highlights (ink text only)
        muted:   {color: "#6B6F5A"}                               # secondary text

A role may also be a bare colour string. Without a palette, a site uses DEFAULT, the
project's neutral colours (also the fallbacks in td.css), and `check` says so.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

ROLES = ("ground", "ink", "primary", "fill", "muted")
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Pairings the v2 components use, as (foreground, background, minimum ratio, what it is).
# `fill` never carries primary text and never marks a control on its own (palettes.md).
PAIRS = (
    ("ink", "ground", 4.5, "text"),
    ("primary", "ground", 4.5, "links and headings"),
    ("muted", "ground", 4.5, "secondary text"),
    ("ground", "primary", 4.5, "text on buttons"),
    ("ink", "fill", 4.5, "text on highlights"),
)


@dataclass(frozen=True)
class Role:
    color: str
    material: str = ""


def parse(raw: object) -> dict[str, Role]:
    """The `theme.palette` mapping, validated; raises ValueError with a readable message."""
    if not isinstance(raw, dict):
        raise ValueError("theme.palette must be a mapping of roles (ground, ink, primary, fill, muted)")
    unknown = sorted(set(map(str, raw)) - set(ROLES))
    if unknown:
        raise ValueError(f"theme.palette: unknown role(s) {', '.join(unknown)} "
                         f"(roles: {', '.join(ROLES)})")
    out: dict[str, Role] = {}
    for role, value in raw.items():
        if isinstance(value, str):
            value = {"color": value}
        if not isinstance(value, dict) or "color" not in value:
            raise ValueError(f"theme.palette.{role}: expected a colour or {{color: '#rrggbb', material: ...}}")
        color = str(value["color"]).strip()
        if not HEX.match(color):
            raise ValueError(f"theme.palette.{role}: '{color}' is not a #rrggbb colour")
        out[str(role)] = Role(color.upper(), str(value.get("material", "") or ""))
    return out


# The project's neutral colours: no people's materials (D21). Same values as the fallbacks
# at the top of static_v2/td.css.
DEFAULT = {
    "ground": Role("#F7F4EE"), "ink": Role("#1D1B18"), "primary": Role("#8A3B12"),
    "fill": Role("#D9B36C"), "muted": Role("#625B52"),
}


def _channel(c: int) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a: str, b: str) -> float:
    """WCAG 2 contrast ratio between two #rrggbb colours."""
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def contrast_problems(palette: dict[str, Role]) -> list[str]:
    """One message per required pairing that fails, or a missing role."""
    missing = [r for r in ROLES if r not in palette]
    if missing:
        return [f"theme.palette is missing role(s): {', '.join(missing)}"]
    out = []
    for fg, bg, minimum, what in PAIRS:
        ratio = contrast(palette[fg].color, palette[bg].color)
        if ratio < minimum:
            out.append(f"theme.palette: {fg} on {bg} ({what}) has contrast {ratio:.2f}:1, "
                       f"needs {minimum}:1")
    return out


def colors(palette: dict[str, Role]) -> dict[str, str]:
    return {role: palette[role].color for role in ROLES if role in palette}
