"""Jinja2 environment and template rendering (inlined from kodudo)."""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateSyntaxError, UndefinedError, select_autoescape

from .errors import RenderError


def create_environment(
    template_dirs: tuple[Path, ...] = (),
    autoescape_for: tuple[str, ...] = ("html", "xml"),
) -> Environment:
    search_paths = [str(p) for p in template_dirs] if template_dirs else ["."]
    loader = FileSystemLoader(search_paths)
    return Environment(
        loader=loader,
        autoescape=select_autoescape(autoescape_for),
        trim_blocks=True,
        lstrip_blocks=True,
    )


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
