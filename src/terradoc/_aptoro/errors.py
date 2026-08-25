"""Error types for the inlined aptoro data-validation library."""

from dataclasses import dataclass, field


class AptoroError(Exception):
    pass


class SchemaError(AptoroError):
    pass


class SourceError(AptoroError):
    pass


@dataclass
class FieldError:
    field: str
    expected: str
    got: str
    row: int | None = None
    column: str | None = None

    def __str__(self) -> str:
        location = ""
        if self.row is not None:
            location = f"\n  Location: row {self.row}"
            if self.column:
                location += f', column "{self.column}"'
        return f"  Field: {self.field}\n  Expected: {self.expected}\n  Got: {self.got!r}{location}"


@dataclass
class ValidationError(AptoroError):
    errors: list[FieldError] = field(default_factory=list)
    source: str | None = None
    schema_name: str | None = None

    def __str__(self) -> str:
        error_count = len(self.errors)
        lines = [f"Validation failed with {error_count} error(s)"]
        if self.source:
            lines.append(f"Source: {self.source}")
        if self.schema_name:
            lines.append(f"Schema: {self.schema_name}")
        lines.append("")
        for i, error in enumerate(self.errors, 1):
            lines.append(f"Error {i}/{error_count}:")
            lines.append(str(error))
            lines.append("")
        return "\n".join(lines)

    def add_error(self, field: str, expected: str, got: str,
                  row: int | None = None, column: str | None = None) -> None:
        self.errors.append(
            FieldError(field=field, expected=expected, got=got, row=row, column=column))

    def summary(self, *, max_errors: int = 10) -> str:
        error_count = len(self.errors)
        lines = [f"Validation failed with {error_count} error(s)"]
        if self.source:
            lines.append(f"Source: {self.source}")
        if self.schema_name:
            lines.append(f"Schema: {self.schema_name}")
        lines.append("")
        shown = min(error_count, max_errors)
        for i, error in enumerate(self.errors[:max_errors], 1):
            lines.append(f"Error {i}/{error_count}:")
            lines.append(str(error))
            lines.append("")
        remaining = error_count - shown
        if remaining > 0:
            lines.append(f"... and {remaining} more error(s)")
            lines.append("")
        return "\n".join(lines)

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def raise_if_errors(self) -> None:
        if self.has_errors():
            raise self
