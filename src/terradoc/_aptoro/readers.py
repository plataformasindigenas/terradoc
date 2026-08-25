"""Data readers for various formats (inlined from aptoro)."""

import csv
import glob as _glob
from io import StringIO
from pathlib import Path
from typing import Any, Protocol

import yaml
from urllib.error import URLError
from urllib.request import urlopen

from .errors import SourceError


class Reader(Protocol):
    def read(self, content: str) -> list[dict[str, Any]]: ...


def fetch_content(source: str) -> str:
    if source.startswith(("http://", "https://")):
        return _fetch_url(source)
    return _read_file(source)


def _fetch_url(url: str) -> str:
    try:
        with urlopen(url, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return str(response.read().decode(charset))
    except URLError as e:
        raise SourceError(f"Cannot fetch URL {url}: {e}")
    except TimeoutError:
        raise SourceError(f"Timeout fetching URL: {url}")
    except UnicodeDecodeError as e:
        raise SourceError(f"Cannot decode content from {url}: {e}")


def _read_file(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        raise SourceError(f"File not found: {path}")
    try:
        return file_path.read_text(encoding="utf-8")
    except OSError as e:
        raise SourceError(f"Cannot read file {path}: {e}")
    except UnicodeDecodeError as e:
        raise SourceError(f"Cannot decode file {path}: {e}")


def detect_format(source: str) -> str:
    clean_source = source.split("?")[0]
    lower = clean_source.lower()
    if lower.endswith(".tsv"):
        return "tsv"
    if lower.endswith(".csv"):
        return "csv"
    if lower.endswith(".json"):
        return "json"
    if lower.endswith((".yaml", ".yml")):
        return "yaml"
    if lower.endswith(".toml"):
        return "toml"
    if lower.endswith(".md"):
        return "frontmatter"
    raise SourceError(
        f"Cannot detect format from source: {source}. Please specify format explicitly.")


# ── YAML Reader ──

class YAMLReader:
    def __init__(self, *, data_key: str | None = None):
        self.data_key = data_key

    def read(self, content: str) -> list[dict[str, Any]]:
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise SourceError(f"YAML parsing error: {e}")
        if data is None:
            return []
        return self._extract_records(data)

    def _extract_records(self, data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return self._validate_records(data)
        if isinstance(data, dict):
            if self.data_key:
                if self.data_key not in data:
                    raise SourceError(f"Key '{self.data_key}' not found in YAML")
                return self._validate_records(data[self.data_key])
            for key in ("data", "records", "items", "results"):
                if key in data and isinstance(data[key], list):
                    return self._validate_records(data[key])
            raise SourceError(
                "YAML mapping must contain 'data', 'records', 'items', or 'results' key")
        raise SourceError(f"Expected YAML sequence or mapping, got {type(data).__name__}")

    def _validate_records(self, records: list[Any]) -> list[dict[str, Any]]:
        result = []
        for i, record in enumerate(records):
            if not isinstance(record, dict):
                raise SourceError(f"Record at index {i} is not a mapping: {type(record).__name__}")
            result.append(record)
        return result


# ── CSV Reader ──

class CSVReader:
    def __init__(self, *, delimiter: str = ",", quotechar: str = '"',
                 infer_types: bool = True):
        self.delimiter = delimiter
        self.quotechar = quotechar
        self.infer_types = infer_types

    def read(self, content: str) -> list[dict[str, Any]]:
        try:
            reader = csv.DictReader(
                StringIO(content), delimiter=self.delimiter, quotechar=self.quotechar)
            records = []
            for row in reader:
                if self.infer_types:
                    row = {k: _infer_type(v) for k, v in row.items()}
                records.append(row)
            return records
        except csv.Error as e:
            raise SourceError(f"CSV parsing error: {e}")


def _infer_type(value: str | None) -> Any:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    lower = value.lower()
    if lower in ("true", "yes", "1"):
        return True
    if lower in ("false", "no", "0"):
        return False
    return value


# ── Frontmatter Reader ──

class FrontmatterReader:
    def __init__(self, *, body_key: str = "body_md") -> None:
        self.body_key = body_key

    def read(self, content: str) -> list[dict[str, Any]]:
        if not content.startswith("---\n") and not content.startswith("---\r\n"):
            raise SourceError("Content does not start with front-matter delimiter '---'")
        rest = content[content.index("\n") + 1:]
        end_idx = rest.find("\n---")
        if end_idx == -1:
            raise SourceError("Missing closing front-matter delimiter '---'")
        front_matter_str = rest[:end_idx]
        after_closing = rest[end_idx + 4:]
        if after_closing.startswith("\n"):
            body = after_closing[1:]
        elif after_closing.startswith("\r\n"):
            body = after_closing[2:]
        else:
            body = after_closing
        try:
            data = yaml.safe_load(front_matter_str)
        except yaml.YAMLError as e:
            raise SourceError(f"Invalid YAML in front matter: {e}")
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise SourceError(
                f"Front matter must be a YAML mapping, got {type(data).__name__}")
        record = dict(data)
        record[self.body_key] = body.strip()
        return [record]


# ── Reader registry + read() ──

_READERS: dict[str, type[Reader]] = {
    "csv": CSVReader,
    "yaml": YAMLReader,
    "yml": YAMLReader,
    "frontmatter": FrontmatterReader,
}


def get_reader(format: str, **kwargs: Any) -> Reader:
    format = format.lower()
    if format not in _READERS:
        supported = ", ".join(sorted(_READERS.keys()))
        raise SourceError(f"Unsupported format: {format}. Supported: {supported}")
    return _READERS[format](**kwargs)


def _is_glob(source: str) -> bool:
    if source.startswith(("http://", "https://")):
        return False
    return any(c in source for c in ("*", "?", "["))


def read(source: str, *, format: str | None = None, **kwargs: Any) -> list[dict[str, Any]]:
    if _is_glob(source):
        if format is None:
            format = detect_format(source)
        if format == "tsv":
            kwargs.setdefault("delimiter", "\t")
            format = "csv"
        paths = sorted(_glob.glob(source, recursive=True))
        if not paths:
            raise SourceError(f"No files matched pattern: {source}")
        reader = get_reader(format, **kwargs)
        results: list[dict[str, Any]] = []
        for path in paths:
            content = fetch_content(path)
            results.extend(reader.read(content))
        return results

    if format is None:
        format = detect_format(source)
    if format == "tsv":
        kwargs.setdefault("delimiter", "\t")
        format = "csv"
    content = fetch_content(source)
    reader = get_reader(format, **kwargs)
    return reader.read(content)
