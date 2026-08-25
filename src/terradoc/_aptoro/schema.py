"""Schema types and YAML parser for the inlined aptoro library."""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from .errors import SchemaError


class BaseType(Enum):
    STR = "str"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    LIST = "list"
    DICT = "dict"
    URL = "url"
    FILE = "file"
    DATETIME = "datetime"
    OBJECT = "object"


@dataclass(frozen=True)
class FieldType:
    base: BaseType
    optional: bool = False
    constraints: tuple[str, ...] | None = None
    pattern: str | None = None
    item_type: "FieldType | None" = None
    value_type: "FieldType | None" = None
    default: Any = None
    has_default: bool = False
    min_value: int | float | None = None
    max_value: int | float | None = None

    def __str__(self) -> str:
        result = self.base.value
        if self.item_type:
            result = f"{result}[{self.item_type}]"
        elif self.value_type:
            result = f"{result}[str, {self.value_type}]"
        elif self.min_value is not None or self.max_value is not None:
            min_str = str(self.min_value) if self.min_value is not None else ""
            max_str = str(self.max_value) if self.max_value is not None else ""
            result = f"{result}[{min_str}..{max_str}]"
        elif self.pattern:
            result = f"{result}[/{self.pattern}/]"
        elif self.constraints:
            result = f"{result}[{'|'.join(self.constraints)}]"
        if self.optional:
            result = f"{result}?"
        if self.has_default:
            result = f"{result} = {self.default!r}"
        return result


@dataclass(frozen=True)
class Field:
    name: str
    field_type: FieldType

    @property
    def is_optional(self) -> bool:
        return self.field_type.optional

    @property
    def is_required(self) -> bool:
        return not self.field_type.optional and not self.field_type.has_default

    @property
    def has_default(self) -> bool:
        return self.field_type.has_default

    @property
    def default(self) -> Any:
        return self.field_type.default


@dataclass(frozen=True)
class NestedField:
    name: str
    is_list: bool
    fields: tuple["Field | NestedField", ...]
    optional: bool = False


@dataclass
class Schema:
    name: str
    fields: tuple[Field | NestedField, ...]
    description: str | None = None
    version: str | None = None
    primary_key: str = "id"
    extends: tuple[str, ...] = field(default_factory=tuple)

    def get_field(self, name: str) -> Field | NestedField | None:
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def has_field(self, name: str) -> bool:
        return self.get_field(name) is not None

    @property
    def required_fields(self) -> tuple[Field, ...]:
        return tuple(f for f in self.fields if isinstance(f, Field) and f.is_required)

    @property
    def optional_fields(self) -> tuple[Field, ...]:
        return tuple(f for f in self.fields if isinstance(f, Field) and f.is_optional)

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)

    def to_dict(self) -> dict[str, Any]:
        def _field_to_value(f: "Field | NestedField") -> str | dict[str, Any]:
            if isinstance(f, Field):
                return str(f.field_type)
            if f.is_list:
                return {"type": "list", "optional": f.optional,
                        "items": {nf.name: _field_to_value(nf) for nf in f.fields}}
            return {"type": "object", "optional": f.optional,
                    "fields": {nf.name: _field_to_value(nf) for nf in f.fields}}

        result: dict[str, Any] = {
            "schema_name": self.name,
            "fields": {f.name: _field_to_value(f) for f in self.fields},
        }
        if self.description:
            result["description"] = self.description
        if self.version:
            result["version"] = self.version
        if self.primary_key != "id":
            result["primary_key"] = self.primary_key
        return result


# ── Parser ──

TYPE_PATTERN = re.compile(
    r"""
    ^
    (?P<base>str|int|float|bool|list|dict|object|url|file|datetime)
    (?:\[(?P<inner>[^\[\]]*(?:\[[^\]]*\][^\[\]]*)*)\])?
    (?P<optional>\?)?
    (?:\s*=\s*(?P<default>.+))?
    $
    """,
    re.VERBOSE,
)

RANGE_PATTERN = re.compile(r"^(?P<min>-?\d+\.?\d*)?\.\.(?P<max>-?\d+\.?\d*)?$")


def parse_type_string(type_str: str) -> FieldType:
    type_str = type_str.strip()
    match = TYPE_PATTERN.match(type_str)
    if not match:
        raise SchemaError(f"Invalid type specification: {type_str!r}")

    base_str = match.group("base")
    inner = match.group("inner")
    optional = match.group("optional") is not None
    default_str = match.group("default")

    try:
        base = BaseType(base_str)
    except ValueError:
        raise SchemaError(f"Unknown base type: {base_str!r}")

    constraints: tuple[str, ...] | None = None
    pattern: str | None = None
    item_type: FieldType | None = None
    value_type: FieldType | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None

    if inner:
        if base == BaseType.LIST:
            item_type = parse_type_string(inner)
        elif base == BaseType.DICT:
            parts = [p.strip() for p in inner.split(",", 1)]
            if len(parts) == 2:
                key_type_str, value_type_str = parts
                if key_type_str != "str":
                    raise SchemaError(f"dict keys must be 'str', got {key_type_str!r}")
                value_type = parse_type_string(value_type_str)
            elif len(parts) == 1 and parts[0] == "str":
                value_type = parse_type_string("str")
            else:
                raise SchemaError(f"Invalid dict type specification: dict[{inner}].")
        elif base == BaseType.STR:
            if inner.startswith("/") and inner.endswith("/") and len(inner) >= 2:
                raw_pattern = inner[1:-1]
                try:
                    re.compile(raw_pattern)
                except re.error as e:
                    raise SchemaError(f"Invalid regex pattern: {inner!r}: {e}")
                pattern = raw_pattern
            else:
                parts = [p.strip() for p in inner.split("|")]
                if all(parts):
                    constraints = tuple(parts)
                else:
                    raise SchemaError(f"Invalid constraint specification: {inner!r}.")
        elif base in (BaseType.INT, BaseType.FLOAT):
            range_match = RANGE_PATTERN.match(inner)
            if range_match:
                min_str = range_match.group("min")
                max_str = range_match.group("max")
                if min_str is not None:
                    min_value = int(min_str) if base == BaseType.INT else float(min_str)
                if max_str is not None:
                    max_value = int(max_str) if base == BaseType.INT else float(max_str)
            else:
                raise SchemaError(f"Invalid range specification: {inner!r}.")
        else:
            raise SchemaError(f"Type {base_str} does not support inner type/constraints")

    default: Any = None
    has_default = False
    if default_str is not None:
        has_default = True
        default = _parse_default_value(default_str, base)

    return FieldType(
        base=base, optional=optional, constraints=constraints, pattern=pattern,
        item_type=item_type, value_type=value_type, default=default,
        has_default=has_default, min_value=min_value, max_value=max_value,
    )


def _parse_default_value(value_str: str, base_type: BaseType) -> Any:
    value_str = value_str.strip()
    if value_str == "[]":
        return []
    if value_str == "{}":
        return {}
    if (value_str.startswith('"') and value_str.endswith('"')) or (
        value_str.startswith("'") and value_str.endswith("'")):
        return value_str[1:-1]
    if value_str.lower() == "true":
        return True
    if value_str.lower() == "false":
        return False
    if value_str.lower() in ("null", "none"):
        return None
    if base_type == BaseType.INT:
        try:
            return int(value_str)
        except ValueError:
            raise SchemaError(f"Invalid integer default: {value_str!r}")
    if base_type == BaseType.FLOAT:
        try:
            return float(value_str)
        except ValueError:
            raise SchemaError(f"Invalid float default: {value_str!r}")
    return value_str


def _parse_field(name: str, value: Any) -> Field | NestedField:
    if isinstance(value, str):
        field_type = parse_type_string(value)
        return Field(name=name, field_type=field_type)
    if isinstance(value, dict):
        if "type" in value and value.get("type") == "list" and "items" in value:
            items = value["items"]
            if isinstance(items, dict):
                nested_fields = tuple(_parse_field(n, v) for n, v in items.items())
                return NestedField(name=name, is_list=True, fields=nested_fields,
                                   optional=value.get("optional", False))
        if "type" in value and value.get("type") == "object" and "fields" in value:
            fields_def = value["fields"]
            if isinstance(fields_def, dict):
                nested_fields = tuple(_parse_field(n, v) for n, v in fields_def.items())
                return NestedField(name=name, is_list=False, fields=nested_fields,
                                   optional=value.get("optional", False))
        raise SchemaError(f"Invalid nested field definition for {name!r}.")
    raise SchemaError(
        f"Invalid field value for {name!r}: expected string or dict, got {type(value).__name__}")


def parse_schema(data: dict[str, Any], base_path: Path | None = None) -> Schema:
    if "name" not in data:
        raise SchemaError("Schema must have a 'name' field")
    if "fields" not in data:
        raise SchemaError("Schema must have a 'fields' section")

    name = data["name"]
    description = data.get("description")
    version = data.get("version")
    primary_key = data.get("primary_key", "id")

    extends_raw = data.get("extends", [])
    if isinstance(extends_raw, str):
        extends_raw = [extends_raw]
    extends = tuple(extends_raw)

    inherited_fields: dict[str, Field | NestedField] = {}
    if extends and base_path:
        for parent_path in extends:
            parent_schema = load_schema(base_path / parent_path)
            for f in parent_schema.fields:
                inherited_fields[f.name] = f

    fields_data = data["fields"]
    if not isinstance(fields_data, dict):
        raise SchemaError("'fields' must be a mapping of field names to types")

    own_fields: dict[str, Field | NestedField] = {}
    for field_name, field_value in fields_data.items():
        own_fields[field_name] = _parse_field(field_name, field_value)

    all_fields = {**inherited_fields, **own_fields}
    fields = tuple(all_fields.values())

    return Schema(name=name, fields=fields, description=description,
                  version=version, primary_key=primary_key, extends=extends)


def load_schema(path: str | Path) -> Schema:
    path = Path(path)
    if not path.exists():
        raise SchemaError(f"Schema file not found: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise SchemaError(f"Invalid YAML in schema file: {e}")
    except OSError as e:
        raise SchemaError(f"Cannot read schema file: {e}")
    if not isinstance(data, dict):
        raise SchemaError("Schema file must contain a YAML mapping")
    return parse_schema(data, base_path=path.parent)
