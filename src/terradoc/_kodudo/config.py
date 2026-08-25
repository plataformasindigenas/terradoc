"""Configuration types, loader, and expansion (inlined from kodudo)."""

import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigError

_RESERVED_FOREACH_NAMES = frozenset({"data", "meta", "config"})


@dataclass(frozen=True)
class Config:
    input: Path
    template: Path
    output: Path
    format: str | None = None
    template_dirs: tuple[Path, ...] = ()
    context_file: Path | None = None
    context: dict[str, Any] | None = None
    base_path: Path | None = None
    foreach: str | None = None

    def get_format(self) -> str:
        if self.format:
            return self.format
        stem = self.template.stem
        if stem.endswith(".html"):
            return "html"
        if stem.endswith(".md"):
            return "markdown"
        return "text"

    def resolve_path(self, path: Path) -> Path:
        if path.is_absolute():
            return path
        if self.base_path:
            return self.base_path / path
        return path

    @property
    def resolved_input(self) -> Path:
        return self.resolve_path(self.input)

    @property
    def resolved_template(self) -> Path:
        return self.resolve_path(self.template)

    @property
    def resolved_output(self) -> Path:
        return self.resolve_path(self.output)

    @property
    def resolved_context_file(self) -> Path | None:
        if self.context_file:
            return self.resolve_path(self.context_file)
        return None

    @property
    def resolved_template_dirs(self) -> tuple[Path, ...]:
        return tuple(self.resolve_path(p) for p in self.template_dirs)


@dataclass(frozen=True)
class OutputSpec:
    output: str
    input: str | None = None
    template: str | None = None
    format: str | None = None
    template_dirs: tuple[str, ...] | None = None
    context_file: str | None = None
    context: dict[str, Any] | None = None


@dataclass(frozen=True)
class BatchConfig:
    config: Config
    outputs: tuple[OutputSpec, ...] | None = None


def interpolate_path(path_str: str, variables: dict[str, Any]) -> str:
    def _resolve(match: re.Match[str]) -> str:
        expr = match.group(1)
        parts = expr.split(".")
        current: Any = variables
        for part in parts:
            if not isinstance(current, dict):
                raise ConfigError(f"Cannot resolve '{expr}': '{part}' is not a key in a non-mapping value")
            if part not in current:
                raise ConfigError(f"Cannot resolve '{expr}': key '{part}' not found")
            current = current[part]
        return str(current)
    return re.sub(r"\{([^}]+)\}", _resolve, path_str)


def expand_config(
    config: Config,
    outputs: tuple[OutputSpec, ...] | None = None,
    data: tuple[dict[str, Any], ...] | None = None,
) -> list[Config]:
    has_outputs = outputs is not None and len(outputs) > 0
    has_foreach = config.foreach is not None
    if not has_outputs and not has_foreach:
        return [config]
    base_configs: list[Config]
    if has_outputs:
        assert outputs is not None
        base_configs = [_apply_output_spec(config, spec) for spec in outputs]
    else:
        base_configs = [config]
    if not has_foreach:
        return base_configs
    assert config.foreach is not None
    if data is None:
        raise ConfigError("foreach requires data but none was provided")
    if len(data) == 0:
        return []
    expanded: list[Config] = []
    for base in base_configs:
        for record in data:
            variables = {config.foreach: record}
            new_output = interpolate_path(str(base.output), variables)
            merged_context = dict(base.context or {})
            merged_context[config.foreach] = record
            expanded.append(replace(base, output=Path(new_output), context=merged_context))
    return expanded


def _apply_output_spec(config: Config, spec: OutputSpec) -> Config:
    overrides: dict[str, Any] = {"output": Path(spec.output)}
    if spec.input is not None:
        overrides["input"] = Path(spec.input)
    if spec.template is not None:
        overrides["template"] = Path(spec.template)
    if spec.format is not None:
        overrides["format"] = spec.format
    if spec.template_dirs is not None:
        overrides["template_dirs"] = tuple(Path(p) for p in spec.template_dirs)
    if spec.context_file is not None:
        overrides["context_file"] = Path(spec.context_file)
    if spec.context is not None:
        merged = dict(config.context or {})
        merged.update(spec.context)
        overrides["context"] = merged
    return replace(config, **overrides)


# ── Loader ──

def load_config(path: str | Path) -> BatchConfig:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in config file: {e}") from e
    except OSError as e:
        raise ConfigError(f"Cannot read config file: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError("Config file must contain a YAML mapping")
    return _parse_config(raw, base_path=path.parent)


def _parse_config(raw: dict[str, Any], base_path: Path) -> BatchConfig:
    if "input" not in raw:
        raise ConfigError("Config must have 'input' field")
    if "template" not in raw:
        raise ConfigError("Config must have 'template' field")
    has_output = "output" in raw
    has_outputs = "outputs" in raw
    if has_output and has_outputs:
        raise ConfigError("'output' and 'outputs' are mutually exclusive")
    if not has_output and not has_outputs:
        raise ConfigError("Config must have 'output' or 'outputs' field")

    template_dirs_raw = raw.get("template_dirs", [])
    if not isinstance(template_dirs_raw, list):
        raise ConfigError("'template_dirs' must be a list")
    template_dirs = tuple(Path(p) for p in template_dirs_raw)

    format_value = raw.get("format")
    if format_value is not None and format_value not in ("html", "markdown", "text"):
        raise ConfigError(f"Invalid format: {format_value}")

    context = raw.get("context")
    if context is not None and not isinstance(context, dict):
        raise ConfigError("'context' must be a mapping")

    foreach = raw.get("foreach")
    if foreach is not None:
        if not isinstance(foreach, str):
            raise ConfigError("'foreach' must be a string")
        if foreach in _RESERVED_FOREACH_NAMES:
            raise ConfigError(f"'foreach' variable name '{foreach}' is reserved.")

    output_specs: tuple[OutputSpec, ...] | None = None
    if has_outputs:
        output_specs = _parse_outputs(raw["outputs"])

    output_path = Path(raw["output"]) if has_output else Path(".")

    config = Config(
        input=Path(raw["input"]), template=Path(raw["template"]),
        output=output_path, format=format_value, template_dirs=template_dirs,
        context_file=Path(raw["context_file"]) if raw.get("context_file") else None,
        context=context, base_path=base_path, foreach=foreach,
    )
    return BatchConfig(config=config, outputs=output_specs)


def _parse_outputs(raw_outputs: Any) -> tuple[OutputSpec, ...]:
    if not isinstance(raw_outputs, list):
        raise ConfigError("'outputs' must be a list")
    specs: list[OutputSpec] = []
    for i, entry in enumerate(raw_outputs):
        if not isinstance(entry, dict):
            raise ConfigError(f"outputs[{i}] must be a mapping")
        if "output" not in entry:
            raise ConfigError(f"outputs[{i}] must have 'output' field")
        td = entry.get("template_dirs")
        template_dirs: tuple[str, ...] | None = None
        if td is not None:
            if not isinstance(td, list):
                raise ConfigError(f"outputs[{i}].template_dirs must be a list")
            template_dirs = tuple(td)
        ctx = entry.get("context")
        if ctx is not None and not isinstance(ctx, dict):
            raise ConfigError(f"outputs[{i}].context must be a mapping")
        specs.append(OutputSpec(
            output=entry["output"], input=entry.get("input"),
            template=entry.get("template"), format=entry.get("format"),
            template_dirs=template_dirs, context_file=entry.get("context_file"),
            context=ctx,
        ))
    return tuple(specs)
