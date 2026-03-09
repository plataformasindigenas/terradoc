"""Tests for decorative macros (decor.html.j2)."""

import importlib.resources
from pathlib import Path

import jinja2


def _get_env():
    """Create a Jinja2 environment with the bundled templates."""
    template_dir = Path(str(importlib.resources.files("terradoc.templates")))
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_dir)),
        autoescape=False,
    )


def _render_macro(macro_call: str) -> str:
    """Render a macro call from decor.html.j2 and return the output."""
    env = _get_env()
    template_str = (
        '{% from "decor.html.j2" import '
        'spine_divider, motif_divider, section_accent, badge_circle, '
        'hero_decor, progress_dots, section_spine, category_marker '
        '%}' + macro_call
    )
    template = env.from_string(template_str)
    return template.render().strip()


# ── hero_decor ──


def test_hero_decor_balanced():
    """hero_decor at balanced renders HTML with accent color."""
    html = _render_macro('{{ hero_decor(intensity="balanced") }}')
    assert "var(--td-color-accent)" in html
    assert "aria-hidden" in html


def test_hero_decor_minimal():
    """hero_decor at minimal renders a simpler version."""
    html = _render_macro('{{ hero_decor(intensity="minimal") }}')
    assert "40px" in html or "width:40px" in html
    assert "aria-hidden" in html


def test_hero_decor_rich():
    """hero_decor at rich renders a fuller version."""
    html = _render_macro('{{ hero_decor(intensity="rich") }}')
    assert "120px" in html or "width:120px" in html


# ── motif_divider ──


def test_motif_divider_patterns():
    """Each motif_divider pattern renders valid SVG."""
    for pattern in ("line", "dot", "diamond"):
        html = _render_macro(f'{{{{ motif_divider(pattern="{pattern}", intensity="balanced") }}}}')
        assert "<svg" in html
        assert "td-decor-motif" in html


def test_motif_divider_minimal_hidden():
    """motif_divider at minimal renders nothing."""
    html = _render_macro('{{ motif_divider(intensity="minimal") }}')
    assert html == ""


# ── badge_circle ──


def test_badge_circle_with_label():
    """badge_circle renders label text inside."""
    html = _render_macro('{{ badge_circle(label="42", intensity="balanced") }}')
    assert "42" in html
    assert "td-decor-badge" in html


def test_badge_circle_minimal_hidden():
    """badge_circle at minimal renders nothing."""
    html = _render_macro('{{ badge_circle(label="X", intensity="minimal") }}')
    assert html == ""


# ── section_accent ──


def test_section_accent_returns_style():
    """section_accent returns a valid CSS border string."""
    css = _render_macro('{{ section_accent(intensity="balanced") }}')
    assert "border-left:" in css
    assert "solid" in css


def test_section_accent_minimal():
    """section_accent at minimal returns thinner border."""
    css = _render_macro('{{ section_accent(intensity="minimal") }}')
    assert "2px" in css
    assert "border-light" in css


def test_section_accent_rich():
    """section_accent at rich returns thicker accent border."""
    css = _render_macro('{{ section_accent(intensity="rich") }}')
    assert "5px" in css
    assert "accent" in css


# ── progress_dots ──


def test_progress_dots_count():
    """progress_dots renders correct number of dots."""
    html = _render_macro('{{ progress_dots(total=5, current=3, intensity="balanced") }}')
    assert html.count("border-radius:50%") == 5


def test_progress_dots_minimal_hidden():
    """progress_dots at minimal renders nothing."""
    html = _render_macro('{{ progress_dots(intensity="minimal") }}')
    assert html == ""


# ── category_marker ──


def test_category_marker_shapes():
    """circle, square, diamond all render."""
    for shape in ("circle", "square", "diamond"):
        html = _render_macro(f'{{{{ category_marker(shape="{shape}", intensity="balanced") }}}}')
        assert "td-decor-marker" in html
        assert html != ""


def test_category_marker_minimal_hidden():
    """category_marker at minimal renders nothing."""
    html = _render_macro('{{ category_marker(intensity="minimal") }}')
    assert html == ""


# ── spine_divider ──


def test_spine_divider_balanced():
    """spine_divider at balanced renders a vertical line."""
    html = _render_macro('{{ spine_divider(intensity="balanced") }}')
    assert "td-decor-spine" in html


def test_spine_divider_minimal_hidden():
    """spine_divider at minimal renders nothing."""
    html = _render_macro('{{ spine_divider(intensity="minimal") }}')
    assert html == ""


# ── section_spine ──


def test_section_spine_balanced():
    """section_spine at balanced returns CSS border."""
    css = _render_macro('{{ section_spine(intensity="balanced") }}')
    assert "border-left:" in css


# ── All non-structural macros hidden at minimal ──


def test_all_macros_hidden_at_minimal():
    """Non-structural macros render empty at minimal intensity."""
    non_structural = [
        'spine_divider(intensity="minimal")',
        'motif_divider(intensity="minimal")',
        'badge_circle(intensity="minimal")',
        'progress_dots(intensity="minimal")',
        'category_marker(intensity="minimal")',
    ]
    for call in non_structural:
        html = _render_macro("{{ " + call + " }}")
        assert html == "", f"{call} should render empty at minimal"
