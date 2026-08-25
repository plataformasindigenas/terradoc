"""Data validation against schemas using Pydantic (inlined from aptoro)."""

import re
import urllib.error
import urllib.request
from dataclasses import field as dataclass_field
from dataclasses import make_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, get_type_hints

from pydantic import AfterValidator, BaseModel, ConfigDict, create_model
from pydantic import ValidationError as PydanticValidationError
from pydantic.fields import FieldInfo

from .errors import FieldError, ValidationError
from .schema import BaseType, Field, FieldType, NestedField, Schema


# ── Dataclass generation ──

def _python_type_for_field_type(field_type: FieldType) -> type:
    base_map: dict[BaseType, type] = {
        BaseType.STR: str, BaseType.INT: int, BaseType.FLOAT: float,
        BaseType.BOOL: bool, BaseType.DICT: dict, BaseType.URL: str,
        BaseType.FILE: str, BaseType.DATETIME: str,
    }
    if field_type.base == BaseType.LIST:
        if field_type.item_type:
            item_type = _python_type_for_field_type(field_type.item_type)
            python_type: type = list[item_type]  # type: ignore
        else:
            python_type = list
    elif field_type.base == BaseType.DICT:
        if field_type.value_type:
            val_type = _python_type_for_field_type(field_type.value_type)
            python_type = dict[str, val_type]  # type: ignore
        else:
            python_type = dict
    elif field_type.base == BaseType.OBJECT:
        python_type = dict
    else:
        python_type = base_map.get(field_type.base, Any)
    if field_type.optional:
        python_type = python_type | None  # type: ignore
    return python_type


def _make_field_spec(f: Field) -> tuple[str, type, Any]:
    python_type = _python_type_for_field_type(f.field_type)
    if f.has_default:
        default = f.default
        if isinstance(default, (list, dict)):
            def factory(d=default):  # type: ignore
                return d.copy()
            return (f.name, python_type, dataclass_field(default_factory=factory))
        return (f.name, python_type, default)
    elif f.is_optional:
        return (f.name, python_type, None)
    else:
        return (f.name, python_type, dataclass_field())


def generate_dataclass(schema: Schema) -> type:
    fields_spec: list[tuple[str, type] | tuple[str, type, Any]] = []
    required_fields = []
    optional_fields = []
    required_nested: list[NestedField] = []
    optional_nested: list[NestedField] = []

    for f in schema.fields:
        if isinstance(f, Field):
            if f.is_required:
                required_fields.append(f)
            else:
                optional_fields.append(f)
        elif isinstance(f, NestedField):
            if f.optional:
                optional_nested.append(f)
            else:
                required_nested.append(f)

    for f in required_fields:
        fields_spec.append(_make_field_spec(f))
    for nf in required_nested:
        python_type: type = list[dict] if nf.is_list else dict  # type: ignore
        fields_spec.append((nf.name, python_type, dataclass_field()))
    for f in optional_fields:
        fields_spec.append(_make_field_spec(f))
    for nf in optional_nested:
        python_type = list[dict] | None if nf.is_list else dict | None  # type: ignore
        fields_spec.append((nf.name, python_type, None))

    class_name = "".join(word.capitalize() for word in schema.name.split("_"))
    return make_dataclass(class_name, fields_spec, frozen=True)


def create_instance(dataclass_type: type, data: dict[str, Any]) -> Any:
    hints = get_type_hints(dataclass_type)
    filtered_data = {k: v for k, v in data.items() if k in hints}
    return dataclass_type(**filtered_data)


# ── Pydantic validation ──

def validate_url(value: str) -> str:
    try:
        req = urllib.request.Request(value, headers={"User-Agent": "Aptoro/0.5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status >= 400:
                raise ValueError(f"URL returned status {response.status}")
    except (urllib.error.URLError, ValueError) as e:
        raise ValueError(f"URL validation failed: {e}") from e
    return value


def validate_file(value: str) -> str:
    path = Path(value)
    if not path.is_file():
        raise ValueError(f"File not found: {value}")
    return value


def validate_datetime(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        try:
            d = datetime.strptime(value, "%Y-%m-%d").date()
            dt = datetime.combine(d, datetime.min.time())
        except ValueError as e:
            raise ValueError(
                f"Invalid datetime format: {value}. "
                "Expected ISO 8601 (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"
            ) from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt.isoformat()


def _pydantic_type_for_field_type(field_type: FieldType) -> type:
    from typing import Literal

    base_map: dict[BaseType, type] = {
        BaseType.STR: str, BaseType.INT: int, BaseType.FLOAT: float, BaseType.BOOL: bool,
    }
    python_type: type
    if field_type.base == BaseType.DICT:
        if field_type.value_type:
            val_type = _pydantic_type_for_field_type(field_type.value_type)
            python_type = dict[str, val_type]  # type: ignore[valid-type]
        else:
            python_type = dict
    elif field_type.base == BaseType.OBJECT:
        python_type = dict
    elif field_type.base == BaseType.URL:
        python_type = Annotated[str, AfterValidator(validate_url)]  # type: ignore[assignment]
    elif field_type.base == BaseType.FILE:
        python_type = Annotated[str, AfterValidator(validate_file)]  # type: ignore[assignment]
    elif field_type.base == BaseType.DATETIME:
        python_type = Annotated[str, AfterValidator(validate_datetime)]  # type: ignore[assignment]
    elif field_type.base == BaseType.STR and field_type.pattern:
        compiled = re.compile(field_type.pattern)
        def make_validator(pat: re.Pattern[str]) -> Any:
            def validate_pattern(value: str) -> str:
                if not pat.fullmatch(value):
                    raise ValueError(f"String does not match pattern /{pat.pattern}/")
                return value
            return validate_pattern
        python_type = Annotated[str, AfterValidator(make_validator(compiled))]  # type: ignore[assignment]
    elif field_type.base == BaseType.STR and field_type.constraints:
        python_type = Literal[field_type.constraints]  # type: ignore[assignment]
    elif field_type.base == BaseType.INT or field_type.base == BaseType.FLOAT:
        python_type = base_map[field_type.base]
    elif field_type.base == BaseType.LIST:
        if field_type.item_type:
            item_type = _pydantic_type_for_field_type(field_type.item_type)
            python_type = list[item_type]  # type: ignore[valid-type]
        else:
            python_type = list
    else:
        python_type = base_map.get(field_type.base, Any)
    if field_type.optional:
        python_type = python_type | None  # type: ignore[assignment]
    return python_type


def _strip_null_defaults(record: dict[str, Any], schema: Schema) -> dict[str, Any]:
    result = record.copy()
    for field in schema.fields:
        if isinstance(field, Field) and (
            field.name in result and result[field.name] is None
            and field.has_default and not field.is_optional
        ):
            del result[field.name]
    return result


def _create_nested_pydantic_model(
    nested: NestedField, parent_name: str = ""
) -> type[BaseModel]:
    field_definitions: dict[str, tuple[type, FieldInfo]] = {}
    model_name = "".join(word.capitalize() for word in nested.name.split("_")) + "SubModel"
    for f in nested.fields:
        if isinstance(f, Field):
            python_type: type = _pydantic_type_for_field_type(f.field_type)
            if f.has_default:
                field_info = FieldInfo(default=f.default, validate_default=True)
            elif f.is_optional:
                field_info = FieldInfo(default=None)
            else:
                field_info = FieldInfo()
            field_definitions[f.name] = (python_type, field_info)
        elif isinstance(f, NestedField):
            sub_model = _create_nested_pydantic_model(f, model_name)
            nested_type: type
            if f.is_list:
                nested_type = list[sub_model]  # type: ignore[valid-type]
            else:
                nested_type = sub_model
            if f.optional:
                nested_type = nested_type | None  # type: ignore[assignment]
                field_info = FieldInfo(default=None)
            else:
                field_info = FieldInfo()
            field_definitions[f.name] = (nested_type, field_info)
    return create_model(  # type: ignore[no-any-return, call-overload]
        model_name,
        __config__=ConfigDict(strict=False, extra="ignore", coerce_numbers_to_str=True),
        **field_definitions,
    )


def _create_pydantic_model(schema: Schema) -> type[BaseModel]:
    from pydantic import Field as PydanticField
    field_definitions: dict[str, tuple[type, FieldInfo]] = {}
    for f in schema.fields:
        if isinstance(f, Field):
            python_type = _pydantic_type_for_field_type(f.field_type)
            if (f.field_type.base == BaseType.INT or f.field_type.base == BaseType.FLOAT) and (
                f.field_type.min_value is not None or f.field_type.max_value is not None
            ):
                field_info_kwargs: dict[str, int | float] = {}
                if f.field_type.min_value is not None:
                    field_info_kwargs["ge"] = f.field_type.min_value
                if f.field_type.max_value is not None:
                    field_info_kwargs["le"] = f.field_type.max_value
                if f.has_default:
                    field_info_kwargs["default"] = f.default
                    field_info_kwargs["validate_default"] = True
                field_info = PydanticField(**field_info_kwargs)  # type: ignore
            elif f.has_default:
                field_info = FieldInfo(default=f.default, validate_default=True)
            elif f.is_optional:
                field_info = FieldInfo(default=None)
            else:
                field_info = FieldInfo()
            field_definitions[f.name] = (python_type, field_info)
        elif isinstance(f, NestedField):
            sub_model = _create_nested_pydantic_model(f)
            nested_type: type
            if f.is_list:
                nested_type = list[sub_model]  # type: ignore[valid-type]
            else:
                nested_type = sub_model
            if f.optional:
                nested_type = nested_type | None  # type: ignore[assignment]
                field_info = FieldInfo(default=None)
            else:
                field_info = FieldInfo()
            field_definitions[f.name] = (nested_type, field_info)
    model_name = "".join(word.capitalize() for word in schema.name.split("_")) + "Model"
    return create_model(  # type: ignore[no-any-return, call-overload]
        model_name,
        __config__=ConfigDict(strict=False, extra="ignore", coerce_numbers_to_str=True),
        **field_definitions,
    )


def _convert_pydantic_error(error: dict[str, Any], row_index: int | None = None) -> FieldError:
    loc = error.get("loc", ())
    field_name = str(loc[0]) if loc else "unknown"
    error_type = error.get("type", "unknown")
    msg = error.get("msg", "validation error")
    input_value = error.get("input")
    if error_type == "literal_error":
        ctx = error.get("ctx", {})
        expected_values = ctx.get("expected", "")
        expected = f"one of [{expected_values}]"
    elif error_type == "missing":
        expected = "required field"
    elif error_type == "string_type":
        expected = "str"
    elif error_type == "int_type":
        expected = "int"
    elif error_type == "float_type":
        expected = "float"
    elif error_type == "bool_type":
        expected = "bool"
    elif error_type == "list_type":
        expected = "list"
    elif error_type == "dict_type":
        expected = "dict"
    else:
        expected = msg
    return FieldError(
        field=field_name, expected=expected,
        got=str(input_value) if input_value is not None else "null/missing",
        row=row_index, column=field_name,
    )


def validate(
    data: list[dict[str, Any]],
    schema: Schema,
    *,
    collect_errors: bool = False,
    source: str | None = None,
) -> list[Any]:
    pydantic_model = _create_pydantic_model(schema)
    dataclass_type = generate_dataclass(schema)
    validation_error = ValidationError(source=source, schema_name=schema.name)
    results: list[Any] = []

    for i, record in enumerate(data):
        try:
            record = _strip_null_defaults(record, schema)
            validated = pydantic_model.model_validate(record)
            instance = create_instance(dataclass_type, validated.model_dump())
            results.append(instance)
        except PydanticValidationError as e:
            for error in e.errors():
                error_dict: dict[str, Any] = dict(error)
                field_error = _convert_pydantic_error(error_dict, row_index=i + 1)
                validation_error.add_error(
                    field=field_error.field, expected=field_error.expected,
                    got=field_error.got, row=field_error.row, column=field_error.column)
            if not collect_errors:
                validation_error.raise_if_errors()

    pk_field = schema.get_field(schema.primary_key)
    if pk_field is not None and isinstance(pk_field, Field):
        seen: dict[Any, int] = {}
        for i, instance in enumerate(results):
            pk_value = getattr(instance, schema.primary_key, None)
            if pk_value is None:
                continue
            if pk_value in seen:
                validation_error.add_error(
                    field=schema.primary_key, expected="unique value (primary key)",
                    got=f"{pk_value!r} (duplicate of row {seen[pk_value]})",
                    row=i + 1, column=schema.primary_key)
            else:
                seen[pk_value] = i + 1

    validation_error.raise_if_errors()
    return results
