"""Jinja2 environment and template rendering (inlined from kodudo)."""

import importlib.resources

from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PrefixLoader, TemplateNotFound, TemplateSyntaxError, UndefinedError, select_autoescape

from .errors import RenderError


def format_number(value: Any, locale: str = "pt") -> str:
    """A number as the interface language writes it: 4.865 and 7,0 in Portuguese, 4,865 and 7.0
    in English. Languages other than English use the Portuguese convention."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    decimals = 0 if number == int(number) and not isinstance(value, float) else 1
    text = f"{number:,.{decimals}f}"
    if str(locale).split("-")[0].lower() == "en":
        return text
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def create_environment(
    template_dirs: tuple[Path, ...] = (),
    autoescape_for: tuple[str, ...] = ("html", "xml"),
) -> Environment:
    search_paths = [str(p) for p in template_dirs] if template_dirs else ["."]
    # "terradoc/<name>" always means terradoc's own template, so a site's override of a
    # page can extend the original: {% extends "terradoc/dictionary.html.j2" %}.
    bundled = str(importlib.resources.files("terradoc.templates"))
    loader = ChoiceLoader([
        FileSystemLoader(search_paths),
        PrefixLoader({"terradoc": FileSystemLoader(bundled)}),
    ])
    env = Environment(
        loader=loader,
        autoescape=select_autoescape(autoescape_for),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["number"] = format_number
    return env


def render(
    env: Environment,
    template_name: str,
    *,
    data: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    meta: dict[str, Any],
    config: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> str:
    try:
        template = env.get_template(template_name)
    except TemplateNotFound as e:
        raise RenderError(f"Template not found: {template_name}") from e
    except TemplateSyntaxError as e:
        raise RenderError(f"Template syntax error in {e.filename}:{e.lineno}: {e.message}") from e

    template_vars: dict[str, Any] = {
        "data": list(data),
        "meta": meta,
        "config": config,
    }
    if context:
        template_vars.update(context)

    try:
        return template.render(**template_vars)
    except UndefinedError as e:
        raise RenderError(f"Undefined variable in template: {e}") from e
    except Exception as e:
        raise RenderError(f"Render failed: {e}") from e
