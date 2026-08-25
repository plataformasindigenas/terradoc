"""Inlined aptoro — minimal data ETL (read, validate, schema)."""

from .errors import ValidationError
from .readers import read
from .schema import Schema, load_schema
from .validation import validate

__all__ = ["ValidationError", "read", "load_schema", "Schema", "validate"]
