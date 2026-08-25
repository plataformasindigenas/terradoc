"""Inlined kodudo — cook data into documents via Jinja2 templates."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from .config import BatchConfig, Config, OutputSpec, expand_config, load_config
from .data import LoadedData, load_data
from .errors import ConfigError, RenderError
from .rendering import create_environment
from .rendering import render as _render

__all__ = [
    "cook", "cook_from_config", "render", "load_config", "load_data",
    "BatchConfig", "Config", "OutputSpec", "LoadedData",
    "expand_config", "ConfigError", "RenderError",
]


def cook(config_path: str | Path) -> list[Path]:
    batch = load_config(config_path)
    return cook_from_config(batch.config, outputs=batch.outputs)


def cook_from_config(
    config: Config,
    *,
    outputs: tuple[OutputSpec, ...] | None = None,
    context: dict[str, Any] | None = None,
    output: str | Path | None = None,
) -> list[Path]:
    if context is not None or output is not None:
        overrides: dict[str, Any] = {}
        if output is not None:
            overrides["output"] = Path(output)
        if context is not None:
            merged = dict(config.context or {})
            merged.update(context)
            overrides["context"] = merged
        config = replace(config, **overrides)

    loaded = load_data(config.resolved_input)
    expanded = expand_config(config, outputs=outputs, data=loaded.raw)

    result_paths: list[Path] = []
    for cfg in expanded:
        output_path = _cook_single(cfg, loaded)
        result_paths.append(output_path)
    return result_paths


def _cook_single(config: Config, loaded: LoadedData) -> Path:
    context: dict[str, Any] = {}
    if config.resolved_context_file:
        context = _load_context_file(config.resolved_context_file)
    if config.context:
        context.update(config.context)

    template_path = config.resolved_template
    template_dirs = (template_path.parent,) + config.resolved_template_dirs
    env = create_environment(template_dirs)

    config_dict = {
        "input": str(config.resolved_input),
        "output": str(config.resolved_output),
        "format": config.get_format(),
    }

    result = _render(
        env, template_path.name, data=loaded.raw,
        meta=loaded.meta, config=config_dict, context=context,
    )

    output_path = config.resolved_output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result, encoding="utf-8")
    return output_path


def render(
    data: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    template: str | Path,
    *,
    meta: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    template_dirs: tuple[Path, ...] = (),
) -> str:
    template = Path(template)
    dirs = (template.parent,) + template_dirs
    env = create_environment(dirs)
    return _render(
        env, template.name, data=tuple(data),
        meta=meta or {}, config={}, context=context,
    )


def _load_context_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Context file not found: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            content = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in context file: {e}") from e
    except OSError as e:
        raise ConfigError(f"Cannot read context file: {e}") from e
    if content is None:
        return {}
    if not isinstance(content, dict):
        raise ConfigError("Context file must contain a YAML mapping")
    return content
