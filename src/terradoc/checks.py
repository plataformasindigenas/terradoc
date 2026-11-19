"""`terradoc check`: validate a project's sources without writing anything.

Every problem becomes an :class:`Issue` with a file and, where known, a line,
so CI can show it next to the offending row. Errors block publication;
warnings are reported and do not.

Rules (see the platforms' pipeline plan, section 5):

- schema validation of every enabled tabular module (all rows, not just the first failure);
- encyclopedia front matter (ids, titles, lists, categories, see_also targets);
- consent: every ``videos`` / ``recordings`` row must say ``consent: approved``
  (community consent to publish) or ``consent: external`` (someone else's
  public media that we only embed);
- media: every ``images/...`` or ``audio/...`` path referenced by the data or
  the theme must exist in ``static/``;
- theme: the palette (roles, contrast), the pack (``config/templates/v2/motifs/<name>/``
  or terradoc's neutral ``weave``; never another people's), v1 leftovers (settings,
  page configs, patterns: removed in 0.23.0);
- orthography (warnings): dictionary headwords whose first letter is not in the
  site's ``alphabet``;
- fonts (error, after the dry export): characters the site shows that the text face lacks;
- locales (warnings): UI keys of the default locale missing from another locale;
- a dry export into a throwaway bundle, so anything the build would trip on
  (bad BibTeX, HTML in Markdown, broken cross-links) is caught here too.
"""

from __future__ import annotations

import contextlib
import csv
import unicodedata
import io
import os
import json
import re
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable

import yaml

from terradoc import _aptoro as aptoro
from terradoc.config import TerradocConfig

CONSENT_MODULES = ("videos", "recordings")
CONSENT_VALUES = ("approved", "external")
TABULAR_EXTENSIONS = (".yaml", ".yml", ".tsv")
MEDIA_RE = re.compile(
    r"^(?:images|audio|video|media)/[^\s]+\.(?:jpe?g|png|svg|webp|gif|avif|mp3|mp4|m4a|webm|ogg|oga|wav)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Issue:
    level: str  # "error" | "warning"
    rule: str
    message: str
    file: str | None = None
    line: int | None = None

    def location(self) -> str:
        if self.file and self.line:
            return f"{self.file}:{self.line}"
        return self.file or "-"


# ── helpers ──────────────────────────────────────────────────────────────

def _rel(config: TerradocConfig, path: Path) -> str:
    try:
        return path.resolve().relative_to(config.base_dir.resolve()).as_posix()
    except ValueError:
        return str(path)


def _source_file(config: TerradocConfig, slug: str) -> Path | None:
    for ext in TABULAR_EXTENSIONS:
        candidate = config.data_dir / f"{slug}{ext}"
        if candidate.exists():
            return candidate
    return None


def _yaml_item_lines(path: Path) -> list[int]:
    """1-based line of each top-level list item in a YAML file (best effort)."""
    try:
        node = yaml.compose(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return []
    if isinstance(node, yaml.SequenceNode):
        return [item.start_mark.line + 1 for item in node.value]
    return []


def _tsv_row_lines(path: Path) -> list[int]:
    """1-based starting line of each data row, parsed exactly like aptoro's
    reader (csv.DictReader, tab, '"'): blank lines are skipped and quoted
    fields may span lines, so 'row + 1' is not enough."""
    lines: list[int] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter="\t", quotechar='"')
        header_seen = False
        while True:
            start = reader.line_num + 1
            try:
                row = next(reader)
            except StopIteration:
                break
            except csv.Error:
                break
            if not row:
                continue  # DictReader skips blank lines
            if not header_seen:
                header_seen = True
                continue
            lines.append(start)
    return lines


def _source_lines(path: Path) -> list[int]:
    """Starting line of each record (1-based) in a TSV or YAML-list source."""
    if path.suffix == ".tsv":
        return _tsv_row_lines(path)
    return _yaml_item_lines(path)


def _row_line(path: Path, row: int | None, lines: list[int]) -> int | None:
    """Map aptoro's 1-based row number to a line in the source file."""
    if row is None or not (0 < row <= len(lines)):
        return None
    return lines[row - 1]


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _iter_strings(v)


def _media_exists(config: TerradocConfig, rel: str) -> bool:
    rel = rel.split("#", 1)[0].split("?", 1)[0]
    return (config.static_dir / rel).is_file()


def _read_front_matter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data = yaml.safe_load(parts[1])
    return data if isinstance(data, dict) else {}


# ── rules ────────────────────────────────────────────────────────────────

def _check_preflight(config: TerradocConfig) -> list[Issue]:
    from terradoc.convert import REQUIRED_DATA_PATHS

    issues = []
    for name in config.modules:
        if not config.is_module_enabled(name):
            continue
        schema = config.resolve_schema(name)
        if not schema.exists():
            issues.append(Issue("error", "preflight", f"module '{name}': schema not found ({schema})"))
        for rel in REQUIRED_DATA_PATHS.get(name, ()):
            if not (config.data_dir / rel).exists():
                issues.append(Issue("error", "preflight",
                                    f"module '{name}': required path missing", _rel(config, config.data_dir / rel)))
    return issues


def _load_rows(config: TerradocConfig, slug: str) -> tuple[Path | None, list[dict], list[Issue]]:
    path = _source_file(config, slug)
    if path is None:
        return None, [], []
    try:
        rows = aptoro.read(str(path))
    except Exception as exc:  # unreadable TSV/YAML
        line = getattr(exc, "line", None)
        return path, [], [Issue("error", "read", f"cannot read file: {exc}", _rel(config, path), line)]
    return path, [dict(r) for r in rows], []


def _check_tabular(config: TerradocConfig) -> tuple[list[Issue], dict[str, tuple[Path, list[dict]]]]:
    from terradoc.convert import SPECIAL_CONVERTERS

    issues: list[Issue] = []
    loaded: dict[str, tuple[Path, list[dict]]] = {}
    for name in config.modules:
        if not config.is_module_enabled(name) or name in SPECIAL_CONVERTERS:
            continue
        path, rows, read_issues = _load_rows(config, name)
        issues += read_issues
        if path is None or read_issues:
            continue
        loaded[name] = (path, rows)
        schema_path = config.resolve_schema(name)
        if not schema_path.exists():
            continue  # reported by preflight
        schema = aptoro.load_schema(str(schema_path))
        try:
            aptoro.validate(rows, schema, collect_errors=True)
        except aptoro.ValidationError as exc:
            yaml_lines = _source_lines(path)
            for err in exc.errors:
                column = f" column '{err.column}'" if err.column else ""
                got = str(err.got)
                dup = re.search(r"\(duplicate of row (\d+)\)", got)
                if dup:  # say where the first occurrence is, as a line number
                    first = _row_line(path, int(dup.group(1)), yaml_lines)
                    where = f"line {first}" if first else f"row {dup.group(1)}"
                    msg = f"duplicate {err.field} {got.split(' (')[0]} (first used on {where})"
                else:
                    msg = f"{err.field}:{column} expected {err.expected}, got {err.got!r}"
                issues.append(Issue("error", "schema", msg, _rel(config, path),
                                    _row_line(path, err.row, yaml_lines)))
    return issues, loaded


def _check_encyclopedia(config: TerradocConfig) -> list[Issue]:
    if not config.is_module_enabled("encyclopedia"):
        return []
    from terradoc.check_entries import collect_entry_errors

    return [Issue("error", "encyclopedia", msg, _rel(config, path) if path else None)
            for path, msg in collect_entry_errors(config.data_dir)]


def _check_consent(config: TerradocConfig, loaded: dict[str, tuple[Path, list[dict]]]) -> list[Issue]:
    issues = []
    for name in CONSENT_MODULES:
        if name not in loaded:
            continue
        path, rows = loaded[name]
        yaml_lines = _source_lines(path)
        for i, row in enumerate(rows, start=1):
            value = row.get("consent")
            if value not in CONSENT_VALUES:
                ident = str(row.get("id") or row.get("youtube_id") or f"row {i}")
                if row.get("title"):
                    ident += f" ({row['title']})"
                issues.append(Issue(
                    "error", "consent",
                    f"{ident}: 'consent' must be one of {', '.join(CONSENT_VALUES)} "
                    f"(got {value!r}); unconsented media is never published",
                    _rel(config, path), _row_line(path, i, yaml_lines)))
    return issues


SPEAKER_ID_RE = re.compile(r"^[a-z]{1,4}[0-9]{1,3}$")  # e.g. s01: an id, never a name


def _check_audio_manifest(config: TerradocConfig, loaded: dict[str, tuple[Path, list[dict]]]) -> list[Issue]:
    """data/audio/manifest.tsv: every file listed and present, entries exist, consent given."""
    from terradoc.cross_linker import AUDIO_MANIFEST_COLUMNS, read_audio_manifest

    audio_dir = config.data_dir / "audio"
    rows = read_audio_manifest(audio_dir)
    if rows is None:
        return []
    where = _rel(config, audio_dir / "manifest.tsv")
    issues = []
    with (audio_dir / "manifest.tsv").open(encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
    if tuple(header) != AUDIO_MANIFEST_COLUMNS:
        return [Issue("error", "audio", f"columns must be {' '.join(AUDIO_MANIFEST_COLUMNS)} "
                      f"(got {' '.join(header)})", where, 1)]
    ids = {str(r.get("id")) for r in loaded["dictionary"][1]} if "dictionary" in loaded else None
    seen, listed = set(), set()
    for line, row in enumerate(rows, start=2):
        name, entry_id = row["file"], row["entry_id"]
        listed.add(name)
        if (name, entry_id) in seen:
            issues.append(Issue("error", "audio", f"{name} → {entry_id} is listed twice", where, line))
        seen.add((name, entry_id))
        if "/" in name or not (audio_dir / name).is_file():
            issues.append(Issue("error", "audio", f"missing file '{name}' in data/audio/", where, line))
        if ids is not None and entry_id not in ids:
            issues.append(Issue("error", "audio", f"{name}: no dictionary entry with id {entry_id!r}", where, line))
        if row["consent"] not in CONSENT_VALUES:
            issues.append(Issue("error", "consent",
                f"{name}: 'consent' must be one of {', '.join(CONSENT_VALUES)} (got {row['consent']!r}); "
                "unconsented media is never published", where, line))
        if row["speaker"] and not SPEAKER_ID_RE.match(row["speaker"]):
            issues.append(Issue("error", "audio",
                f"{name}: speaker {row['speaker']!r} must be an id such as s01, not a name", where, line))
    for path in sorted(audio_dir.glob("*.webm")):
        if path.name not in listed:
            issues.append(Issue("error", "audio", f"{path.name} is not in the manifest (it would not be "
                                "published); add a row with its entry id", where))
    return issues


def _check_photo_fields(config: TerradocConfig, path: Path, row: dict, line: int | None) -> list[Issue]:
    """pic_link is a file shipped with the site or an http(s) address;
    pic_source, shown as the credit's link, must be an http(s) address."""
    issues = []
    link, source = row.get("pic_link"), row.get("pic_source")
    if (isinstance(link, str) and re.match(r"(?i)^[a-z][a-z0-9+.-]*:", link.strip())
            and not re.match(r"^https?://", link.strip())):
        issues.append(Issue("error", "media", f"pic_link '{link.strip()}': only a file or an http(s) address",
                            _rel(config, path), line))
    if source is not None and not (isinstance(source, str) and re.match(r"^https?://\S+$", source.strip())):
        issues.append(Issue("error", "schema", f"pic_source '{source}' must be an http(s) address",
                            _rel(config, path), line))
    if source is not None and not row.get("pic_credit"):
        issues.append(Issue("warning", "schema", "pic_source without pic_credit: the link has no text",
                            _rel(config, path), line))
    return issues


def _check_media(config: TerradocConfig, loaded: dict[str, tuple[Path, list[dict]]]) -> list[Issue]:
    issues = []
    for value in sorted(set(config.theme.media().values())):
        if MEDIA_RE.match(value) and not _media_exists(config, value):
            issues.append(Issue("error", "media", f"theme references missing file '{value}'", "terradoc.yaml"))

    for name, (path, rows) in loaded.items():
        yaml_lines = _source_lines(path)
        for i, row in enumerate(rows, start=1):
            for value in _iter_strings(row):
                if MEDIA_RE.match(value.strip()) and not _media_exists(config, value.strip()):
                    issues.append(Issue("error", "media", f"missing file '{value.strip()}'",
                                        _rel(config, path), _row_line(path, i, yaml_lines)))
            if name in ("ethnobotany", "fauna"):
                issues += _check_photo_fields(config, path, row, _row_line(path, i, yaml_lines))

    if config.is_module_enabled("encyclopedia"):
        for md in sorted((config.data_dir / "encyclopedia").rglob("*.md")):
            if md.name == "README.md":
                continue
            try:
                fm = _read_front_matter(md)
            except yaml.YAMLError:
                continue  # reported by the encyclopedia rule
            for value in _iter_strings(fm):
                if MEDIA_RE.match(value.strip()) and not _media_exists(config, value.strip()):
                    issues.append(Issue("error", "media", f"missing file '{value.strip()}'", _rel(config, md)))
    return issues


def _generated_names(config: TerradocConfig) -> tuple[set[str], tuple[str, ...]]:
    """Paths the render step writes: exact files (with the pages' forwarding aliases), and
    directory prefixes."""
    from terradoc import pages_v2

    files = {"index.html", "404.html", "robots.txt", "sitemap.xml", ".release.json", "sw.js",
             "offline.html", "specimen.html"}
    files |= {a for p in pages_v2.load(config)[0] for a in p.aliases}
    prefixes = tuple(f"{loc}/" for loc in config.locales) + ("assets/",)
    return files, prefixes


def _check_static(config: TerradocConfig) -> list[Issue]:
    """static/ must be plain files, and none may collide with generated output."""
    root = config.static_dir
    if root.is_symlink():
        return [Issue("error", "static", "static/ is a symlink; it must be a real directory", "static")]
    if not root.is_dir():
        return []
    issues = []
    files, prefixes = _generated_names(config)
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_symlink():
            issues.append(Issue("error", "static", "symlinks are not allowed in static/", f"static/{rel}"))
            continue
        if p.is_dir():
            continue
        if rel in files or rel.startswith(prefixes):
            issues.append(Issue("error", "static",
                                "this path is generated by terradoc; rename the file", f"static/{rel}"))
    return issues


def _check_theme(config: TerradocConfig) -> list[Issue]:
    from difflib import get_close_matches

    from terradoc.config import REMOVED_THEME_KEYS, TEMPLATE_SETS, THEME_KEYS

    issues = []
    yaml_file = "terradoc.yaml"
    for key in config.unknown_theme_keys:
        if key in REMOVED_THEME_KEYS:
            issues.append(Issue("error", "theme",
                f"theme.{key}: a setting of the v1 templates, removed in terradoc 0.23.0; delete it",
                yaml_file))
            continue
        near = get_close_matches(key, sorted(THEME_KEYS), n=1)
        hint = f" (did you mean '{near[0]}'?)" if near else " (a newer terradoc may know it)"
        issues.append(Issue("error", "theme", f"theme.{key}: unknown setting{hint}", yaml_file))
    if config.theme.templates not in TEMPLATE_SETS:
        gone = " (v1 was removed in terradoc 0.23.0)" if config.theme.templates == "v1" else ""
        issues.append(Issue("error", "theme",
            f"theme.templates: '{config.theme.templates}' is not available in this terradoc{gone} "
            f"(it has: {', '.join(TEMPLATE_SETS)})", yaml_file))
    return issues + _check_theme_v2(config)


def _check_theme_v2(config: TerradocConfig) -> list[Issue]:
    """v2: palette roles and contrast, the motif pack, overrides left from v1, and what the
    v2 pages need from terradoc.yaml (meta REDESIGN-PLAN.md)."""
    from terradoc import packs, palette

    issues = []
    yaml_file = "terradoc.yaml"
    if config.theme.palette:
        try:
            roles = palette.parse(config.theme.palette)
        except ValueError as exc:
            issues.append(Issue("error", "theme", str(exc), yaml_file))
            roles = None
        if roles is not None:
            for problem in palette.contrast_problems(roles):
                issues.append(Issue("error", "theme", problem, yaml_file))
    else:
        if config.enabled_modules():  # a site of pages only (the portal) is the project's own: neutral
            issues.append(Issue("warning", "theme",
                "theme.palette is not set; the site uses the project's neutral colours. Name each "
                "role after its material: see terradoc.palette", yaml_file))
        roles = dict(palette.DEFAULT)
    # A pack that does not exist is an error; an element left out is a warning (the site
    # shows its palette there).
    pack_problems, pack_missing = packs.problems(config, palette.colors(roles) if roles else {})
    for problem in pack_problems:
        issues.append(Issue("error" if pack_missing else "warning", "theme", problem, yaml_file))
    if (config.static_dir / "assets").exists():
        issues.append(Issue("error", "theme",
            "static/assets/ is reserved for the files v2 generates (CSS, fonts, pack, images); "
            "move its files elsewhere in static/", yaml_file))
    old = config.config_dir / "templates"
    if old.is_dir():
        stale = sorted(p.name for p in old.glob("*.j2"))
        if stale:
            issues.append(Issue("error", "theme",
                f"config/templates/ has v1 page overrides ({', '.join(stale)}) that v2 does not "
                "use; move what is still needed to config/templates/v2/, then delete them", yaml_file))
        if (old / "motifs").is_dir():
            issues.append(Issue("error", "theme",
                "config/templates/motifs/ holds v1 patterns, which terradoc no longer reads (v1 was "
                "removed in 0.23.0); the v2 pack lives in config/templates/v2/motifs/. Delete it", yaml_file))
    page_configs = sorted(p.name for p in config.config_dir.glob("*.yaml")) if config.config_dir.is_dir() else []
    if page_configs:
        issues.append(Issue("error", "theme",
            f"config/ has v1 page configs ({', '.join(page_configs)}), which terradoc no longer "
            "reads (v1 was removed in 0.23.0); delete them", yaml_file))
    if not config.language_code and config.enabled_modules():
        issues.append(Issue("warning", "theme",
            "language_code is not set: vernacular text gets no lang attribute (e.g. bor, unk, mpu)", yaml_file))
    for key in ("hero_image", "favicon"):
        value = getattr(config.theme, key)
        if value and not _inside(config.static_dir, value):
            issues.append(Issue("error", "theme",
                f"theme.{key}: '{value}' must be a path inside static/ (no '..', not absolute)", yaml_file))
    if config.theme.hero_image and _inside(config.static_dir, config.theme.hero_image):
        if not (config.static_dir / config.theme.hero_image).is_file():
            issues.append(Issue("error", "theme",
                f"theme.hero_image: static/{config.theme.hero_image} does not exist", yaml_file))
        elif Path(config.theme.hero_image).suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            issues.append(Issue("error", "theme",
                "theme.hero_image: a photograph (.jpg, .png, .webp) is needed for the v2 home", yaml_file))
        if not config.theme.hero_credit:
            issues.append(Issue("warning", "theme", "theme.hero_credit: the hero photograph has no credit", yaml_file))
        if not config.theme.hero_alt:
            issues.append(Issue("warning", "theme",
                "theme.hero_alt: say what the hero photograph shows, for screen readers", yaml_file))
    from terradoc.fonts import TEXT_FACES
    if config.theme.font_vernacular not in TEXT_FACES:
        issues.append(Issue("error", "theme",
            f"theme.font_vernacular: '{config.theme.font_vernacular}' is not available "
            f"(v2 has: {', '.join(TEXT_FACES)})", yaml_file))
    return issues


def _inside(base: Path, rel: str) -> bool:
    """True if `rel` is a relative path that stays inside `base`."""
    if Path(rel).is_absolute():
        return False
    root = base.resolve()
    target = (base / rel).resolve()
    return target == root or root in target.parents


def _nfc_lower(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


def _first_letter(word: str, letters: list[str]) -> str | None:
    w = _nfc_lower(word).lstrip("-")
    for letter in letters:  # longest first
        if w.startswith(letter):
            return letter
    # an accented letter outside the alphabet counts as its plain letter, as on the page
    base = "".join(c for c in unicodedata.normalize("NFD", w[:1]) if not unicodedata.combining(c))
    return base if base and base in letters else None


def _check_alphabet(config: TerradocConfig, loaded: dict[str, tuple[Path, list[dict]]]) -> list[Issue]:
    if not config.alphabet:
        return []
    issues = []
    norm = [_nfc_lower(x) for x in config.alphabet]
    dups = sorted({x for x in norm if norm.count(x) > 1})
    if dups:
        issues.append(Issue("error", "alphabet", f"alphabet: letters listed twice: {', '.join(dups)}", "terradoc.yaml"))
    if "dictionary" not in loaded:
        return issues
    path, rows = loaded["dictionary"]
    letters = sorted(set(norm), key=len, reverse=True)
    lines = _source_lines(path)
    for i, row in enumerate(rows, start=1):
        word = str(row.get("entry") or "")
        if word.strip("- ") and _first_letter(word, letters) is None:
            issues.append(Issue("warning", "alphabet",
                f"'{word}' starts with a letter that is not in the alphabet (terradoc.yaml); "
                "it is listed after the alphabet's letters", _rel(config, path), _row_line(path, i, lines)))
    return issues


def _check_locales(config: TerradocConfig) -> list[Issue]:
    if not config.locales:
        return []
    def keys(loc: str) -> set[str] | None:
        path = config.locales_dir / f"{loc}.yaml"
        if not path.is_file():
            return None
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return set(data) if isinstance(data, dict) else set()
    base = keys(config.default_locale)
    issues = []
    for loc in config.locales:
        have = keys(loc)
        rel = _rel(config, config.locales_dir / f"{loc}.yaml")
        if have is None:
            issues.append(Issue("warning", "locale", f"locale '{loc}' has no file; its pages will show empty labels", rel))
            continue
        if base is None or loc == config.default_locale:
            continue
        missing = sorted(base - have)
        if missing:
            listed = ", ".join(missing[:12]) + (f" and {len(missing) - 12} more" if len(missing) > 12 else "")
            issues.append(Issue("warning", "locale",
                f"{len(missing)} key(s) of '{config.default_locale}' missing in '{loc}' (shown empty or in a "
                f"fallback on '{loc}' pages): {listed}", rel))
    return issues


def _check_dry_export(config: TerradocConfig) -> list[Issue]:
    """Run the real export into a throwaway bundle; report anything it raises."""
    from terradoc.export import export_bundle

    with tempfile.TemporaryDirectory(prefix="terradoc-check-") as tmp:
        dry = replace(config, bundle_dir_override=Path(tmp))
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                export_bundle(dry, run_checks=False)
        except Exception as exc:
            return [Issue("error", "export", f"{type(exc).__name__}: {exc}")]
        return _check_fonts(dry)
    return []


def _check_fonts(config: TerradocConfig) -> list[Issue]:
    """The text face (theme.font_vernacular) must have every character the site shows in the
    ranges terradoc ships (Latin, IPA, Greek, combining marks), or the build stops. Uses the
    renderer's own collection (exported data, settings, locale strings, templates), so check
    and build see the same text. `config` points at a freshly exported bundle."""
    from terradoc import fonts
    from terradoc.build_v2 import load_strings, site_characters

    if config.theme.font_vernacular not in fonts.TEXT_FACES:
        return []  # reported by the theme check
    strings = {loc: load_strings(loc, config) for loc in config.locales}
    lacking = fonts.missing(site_characters(config, strings), config.theme.font_vernacular)
    if not lacking:
        return []
    listed = ", ".join(f"{ch} (U+{ord(ch):04X})" for ch in lacking[:12])
    more = f" and {len(lacking) - 12} more" if len(lacking) > 12 else ""
    return [Issue("error", "font",
        f"the text font ({config.theme.font_vernacular}) lacks characters the site uses "
        f"(data, settings or locale strings): {listed}{more}; the build would stop. "
        "Try theme.font_vernacular: charis or andika", "terradoc.yaml")]


def render_preflight(config: TerradocConfig) -> list[Issue]:
    """The checks `render` repeats against the sources (cheap; no export)."""
    loaded = {}
    for name in CONSENT_MODULES:
        if config.is_module_enabled(name):
            path, rows, read_issues = _load_rows(config, name)
            if read_issues:
                return read_issues
            if path is not None:
                loaded[name] = (path, rows)
    return [i for i in _check_consent(config, loaded) + _check_static(config) + _check_theme(config)
            if i.level == "error"]


def _check_pages(config: TerradocConfig) -> list[Issue]:
    """data/pages/: front matter, a page in every locale, aliases, pictures from static/."""
    from terradoc import pages_v2

    pages, problems = pages_v2.load(config)
    issues = [Issue("error", "pages", msg, file) for file, msg in problems]
    for page in pages:
        rel = _rel(config, page.source)
        for src in pages_v2.image_sources(page):
            if not _media_exists(config, src) or not _inside(config.static_dir, src):
                issues.append(Issue("error", "pages", f"missing picture '{src}' (pictures come from static/)", rel))
        uncredited = [src for src, credit in pages_v2.local_images(page) if not credit]
        if uncredited:
            issues.append(Issue("warning", "pages", f"{len(uncredited)} picture(s) without a credit "
                                f"(D27; write it after the path: ![…](images/x.jpg \"credit\")): "
                                + ", ".join(uncredited[:6]) + (" …" if len(uncredited) > 6 else ""), rel))
        for src in pages_v2.external_images(page):
            issues.append(Issue("error", "pages", f"picture from another site '{src}': pages show pictures "
                                                  "from static/ only (link to others instead)", rel))
    return issues


def run_checks(config: TerradocConfig) -> list[Issue]:
    issues = _check_preflight(config)
    tab_issues, loaded = _check_tabular(config)
    issues += tab_issues
    issues += _check_encyclopedia(config)
    issues += _check_pages(config)
    issues += _check_consent(config, loaded)
    issues += _check_audio_manifest(config, loaded)
    issues += _check_media(config, loaded)
    issues += _check_static(config)
    issues += _check_theme(config)
    issues += _check_alphabet(config, loaded)
    issues += _check_locales(config)
    if not any(i.level == "error" for i in issues):
        issues += _check_dry_export(config)
    return issues


# ── reporting ────────────────────────────────────────────────────────────

def _gh_escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _gh_escape_property(text: str) -> str:
    return _gh_escape(text).replace(":", "%3A").replace(",", "%2C")


def annotation_prefix(config: TerradocConfig) -> str:
    """Path of the project relative to the Actions workspace ('' at the root),
    so annotations attach to the right file when a project is in a subdir."""
    workspace = os.environ.get("GITHUB_WORKSPACE")
    if not workspace:
        return ""
    try:
        rel = config.base_dir.resolve().relative_to(Path(workspace).resolve()).as_posix()
    except ValueError:
        return ""
    return "" if rel == "." else rel + "/"


def _codeowners_rules(path: Path) -> list[tuple[str, list[str]]]:
    rules = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        owners = [o for o in parts[1:] if o.startswith("@")]
        if owners:
            rules.append((parts[0], owners))
    return rules


def _glob_re(pat: str) -> "re.Pattern[str]":
    """gitignore-style glob: '*' and '?' stay within a path segment, '**' crosses them."""
    out, i = [], 0
    while i < len(pat):
        if pat.startswith("**/", i):
            out.append("(?:.*/)?"); i += 3
        elif pat.startswith("**", i):
            out.append(".*"); i += 2
        elif pat[i] == "*":
            out.append("[^/]*"); i += 1
        elif pat[i] == "?":
            out.append("[^/]"); i += 1
        else:
            out.append(re.escape(pat[i])); i += 1
    return re.compile("".join(out))


def _codeowners_match(pattern: str, file: str) -> bool:
    """CODEOWNERS (gitignore-style) matching, as GitHub documents it:
    a pattern with a slash (other than a trailing one) is relative to the repo
    root; without one it matches at any depth; a trailing slash means a
    directory and everything below it."""
    if pattern == "*":
        return True
    directory = pattern.endswith("/")
    pat = pattern.rstrip("/")
    rooted = "/" in pat
    pat = pat.lstrip("/")
    body = _glob_re(pat).pattern
    prefix = "" if rooted else "(?:.*/)?"
    # 'docs/*' covers only direct children (GitHub's documented example);
    # a literal last segment ('apps', 'docs/') also covers everything below it.
    last = pat.rsplit("/", 1)[-1]
    suffix = "/.*" if directory else ("" if "*" in last or "?" in last else "(?:/.*)?")
    return re.fullmatch(prefix + body + suffix, file) is not None


def codeowners_for(files: Iterable[str], codeowners: Path | None) -> list[str]:
    """Owners of the given files: the LAST matching CODEOWNERS rule wins, as on GitHub.
    Issues without a file are attributed to the '*' rule, if any."""
    if codeowners is None or not codeowners.is_file():
        return []
    rules = _codeowners_rules(codeowners)
    owners: list[str] = []
    for file in files:
        matched: list[str] = []
        for pattern, rule_owners in rules:
            if (pattern == "*" if file is None else _codeowners_match(pattern, file)):
                matched = rule_owners
        for o in matched:
            if o not in owners:
                owners.append(o)
    return owners


def _md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def format_markdown(issues: list[Issue], *, mentions: list[str] = (), run_url: str = "") -> str:
    """Issue/step-summary body: Portuguese first, English second, one table."""
    errors = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warning"]
    lines = []
    if errors:
        lines.append("### ❌ Publicação bloqueada / Publication blocked")
        lines.append("")
        lines.append(f"O site **não** foi atualizado: {len(errors)} erro(s). O site no ar continua "
                     "na última versão boa. Corrija os pontos abaixo e envie de novo.  ")
        lines.append(f"The site was **not** updated: {len(errors)} error(s). The live site stays on "
                     "the last good version. Fix the points below and push again.")
    else:
        lines.append("### ✅ Tudo certo / All good")
    lines.append("")
    if issues:
        lines.append("| | Arquivo / File | Linha / Line | Problema / Problem |")
        lines.append("|---|---|---|---|")
        for i in errors + warnings:
            mark = "❌" if i.level == "error" else "⚠️"
            lines.append(f"| {mark} | `{_md_cell(i.file or '-')}` | {i.line or ''} | "
                         f"[{i.rule}] {_md_cell(i.message)} |")
        lines.append("")
    if run_url:
        lines.append(f"Detalhes / Details: {run_url}")
        lines.append("")
    if mentions:
        lines.append("cc " + " ".join(mentions))
    return "\n".join(lines).rstrip() + "\n"


def format_issues(issues: list[Issue], fmt: str = "text", path_prefix: str = "") -> str:
    errors = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warning"]
    if fmt == "markdown":
        return format_markdown(issues)
    if fmt == "json":
        return json.dumps({
            "ok": not errors,
            "errors": len(errors),
            "warnings": len(warnings),
            "issues": [asdict(i) for i in issues],
        }, ensure_ascii=False, indent=2)
    lines = []
    if fmt == "github":
        for i in issues:
            props = []
            if i.file:
                props.append(f"file={_gh_escape_property(path_prefix + i.file)}")
            if i.line:
                props.append(f"line={i.line}")
            props.append(f"title={_gh_escape_property('terradoc ' + i.rule)}")
            lines.append(f"::{i.level} {','.join(props)}::{_gh_escape(i.message)}")
    else:
        for i in issues:
            lines.append(f"{i.level.upper():7} [{i.rule}] {i.location()}: {i.message}")
    lines.append(f"terradoc check: {len(errors)} error(s), {len(warnings)} warning(s)")
    return "\n".join(lines)
