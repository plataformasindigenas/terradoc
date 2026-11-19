"""CLI entry point for terradoc."""

import importlib.resources
import shutil
from pathlib import Path

import click

from terradoc.config import load_config


DEFAULT_FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#3D352F"/>
  <circle cx="32" cy="26" r="12" fill="#C75B39"/>
  <path d="M18 46h28" stroke="#F9F6F2" stroke-width="6" stroke-linecap="round"/>
</svg>
"""


@click.group()
@click.version_option()
def main():
    """Terradoc — Build indigenous documentation sites."""
    pass


def _load(config_path: str, out: str | None = None, bundle_dir: str | None = None,
          templates: str | None = None):
    cfg_path = Path(config_path)
    if not cfg_path.exists():
        click.echo(f"Config file not found: {cfg_path}", err=True)
        raise SystemExit(1)
    try:
        cfg = load_config(cfg_path)
    except ValueError as exc:  # a malformed terradoc.yaml: one line, not a traceback
        raise click.ClickException(str(exc)) from exc
    if out:
        cfg.output_dir = Path(out).resolve()
    if bundle_dir:
        cfg.bundle_dir_override = Path(bundle_dir).resolve()
    if templates:
        cfg.theme.templates = templates
    from terradoc.config import TEMPLATE_SETS
    if cfg.theme.templates not in TEMPLATE_SETS:  # render runs no checks: refuse here too
        raise click.ClickException(
            f"template set '{cfg.theme.templates}' is not available in this terradoc"
            + (" (v1 was removed in terradoc 0.23.0)" if cfg.theme.templates == "v1" else "")
            + f" (it has: {', '.join(TEMPLATE_SETS)})")
    return cfg


def _config_option(f):
    return click.option("--config", "-c", "config_path", default="terradoc.yaml",
                        help="Path to terradoc.yaml config file")(f)


def _bundle_option(f):
    return click.option("--bundle-dir", default=None, type=click.Path(file_okay=False),
                        help="Where the export bundle is written/read (default: data/)")(f)


def _out_options(f):
    f = click.option("--templates", default=None,
                     help="Template set to render with (overrides theme.templates); only v2 since 0.23.0")(f)
    f = click.option("--clean", is_flag=True,
                     help="Empty the output directory first (only with --out)")(f)
    return click.option("--out", default=None, type=click.Path(file_okay=False),
                        help="Output directory for the site (default: docs/)")(f)


class _friendly_errors:
    """Turn expected failures into a one-line message and exit status 1."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        from terradoc.export import CheckFailed

        if exc_type is not None and issubclass(exc_type, (ValueError, FileNotFoundError, CheckFailed)):
            raise click.ClickException(str(exc)) from exc
        return False


FORMATS = ["text", "github", "json", "markdown"]


def _emit(issues, fmt: str, *, prefix: str = "", codeowners: str | None = None,
          run_url: str = "") -> None:
    from terradoc.checks import codeowners_for, format_issues, format_markdown

    if fmt == "markdown":
        files = [(prefix + i.file) if i.file else None for i in issues if i.level == "error"]
        mentions = codeowners_for(files, Path(codeowners)) if codeowners else []
        click.echo(format_markdown(issues, mentions=mentions, run_url=run_url), nl=False)
    else:
        click.echo(format_issues(issues, fmt, prefix if fmt == "github" else ""))


def _report(cfg, fmt: str, codeowners: str | None = None, run_url: str = "") -> bool:
    """Run all checks, print the report; return True if there are no errors."""
    from terradoc.checks import annotation_prefix, run_checks

    issues = run_checks(cfg)
    _emit(issues, fmt, prefix=annotation_prefix(cfg), codeowners=codeowners, run_url=run_url)
    return not any(i.level == "error" for i in issues)


def _codeowners_option(f):
    f = click.option("--run-url", default="", help="Link to the CI run (markdown format)")(f)
    return click.option("--codeowners", default=None, type=click.Path(dir_okay=False),
                        help="CODEOWNERS file; markdown output then @-mentions the owners "
                             "of the files with errors")(f)


@main.command()
@_config_option
@click.option("--format", "fmt", default="text", type=click.Choice(FORMATS),
              help="Report format (github = Actions annotations, markdown = issue body)")
@_codeowners_option
def check(config_path: str, fmt: str, codeowners: str | None, run_url: str):
    """Validate sources (schemas, consent, media, encyclopedia); write nothing.

    Exit status 1 if there is any error; warnings never fail.
    """
    cfg = _load(config_path)
    if not _report(cfg, fmt, codeowners, run_url):
        raise SystemExit(1)


@main.command()
@click.option("--current", required=True, type=click.Path(exists=True, file_okay=False),
              help="The newly built site")
@click.option("--previous", default=None, type=click.Path(exists=True, file_okay=False),
              help="The release it replaces")
@click.option("--baseline", default=None, type=click.Path(exists=True, file_okay=False),
              help="A fixed reference release (guards against slow erosion)")
@click.option("--confirm-shrink", is_flag=True, help="Shrinking is intended: report, do not block")
@click.option("--format", "fmt", default="text", type=click.Choice(FORMATS))
@_codeowners_option
def guard(current: str, previous: str | None, baseline: str | None, confirm_shrink: bool,
          fmt: str, codeowners: str | None, run_url: str):
    """Compare a built site with the release it replaces (shrink / file loss).

    Exit status 1 if the new release loses too much without --confirm-shrink.
    """
    from terradoc.guard import compare_releases

    with _friendly_errors():
        issues = compare_releases(Path(current), Path(previous) if previous else None,
                                  Path(baseline) if baseline else None,
                                  confirm_shrink=confirm_shrink)
    _emit(issues, fmt, codeowners=codeowners, run_url=run_url)
    if any(i.level == "error" for i in issues):
        raise SystemExit(1)


@main.command()
@_config_option
@_bundle_option
def export(config_path: str, bundle_dir: str | None):
    """Write the normalised JSON bundle (experimental format)."""
    from terradoc.export import export_bundle

    cfg = _load(config_path, bundle_dir=bundle_dir)
    with _friendly_errors():
        export_bundle(cfg)
    click.echo(f"=== Export Complete: {cfg.bundle_dir} ===")


@main.command()
@_config_option
@_bundle_option
@_out_options
def render(config_path: str, bundle_dir: str | None, out: str | None, clean: bool,
           templates: str | None):
    """Render the site from an existing export bundle."""
    from terradoc.render import render_site

    cfg = _load(config_path, out=out, bundle_dir=bundle_dir, templates=templates)
    with _friendly_errors():
        render_site(cfg, clean=clean)
    click.echo("\n=== Render Complete ===")


@main.command()
@_config_option
@_bundle_option
@_out_options
@click.option("--format", "fmt", default="text", type=click.Choice(FORMATS),
              help="Format of the check report printed first")
def build(config_path: str, bundle_dir: str | None, out: str | None, clean: bool, fmt: str,
          templates: str | None):
    """Build the complete site: check, export, render."""
    from terradoc.render import render_site
    from terradoc.export import export_bundle

    cfg = _load(config_path, out=out, bundle_dir=bundle_dir, templates=templates)
    if not _report(cfg, fmt):
        click.echo("Build stopped: fix the errors above.", err=True)
        raise SystemExit(1)
    click.echo()
    with _friendly_errors():
        if clean:  # refuse before doing any work
            from terradoc.render import assert_safe_to_clean
            assert_safe_to_clean(cfg)
        export_bundle(cfg, run_checks=False)  # just checked above
        render_site(cfg, clean=clean)
    click.echo("\n=== Build Complete ===")


@main.command()
@click.argument("name", default="my-project")
@click.option("--eject-templates", is_flag=True,
              help="Copy terradoc's templates into config/templates/v2/ for local "
                   "customisation. A local copy shadows every terradoc template "
                   "update, so prefer config options, locale keys and single-file overrides.")
def init(name: str, eject_templates: bool):
    """Scaffold a new terradoc project (v2 templates, the neutral `weave` pack)."""
    project_dir = Path(name)
    if project_dir.exists():
        click.echo(f"Directory '{name}' already exists", err=True)
        raise SystemExit(1)

    project_dir.mkdir()
    (project_dir / "data" / "encyclopedia").mkdir(parents=True)
    (project_dir / "locales").mkdir()
    # static/ is copied verbatim into the site root by `terradoc build`
    (project_dir / "static" / "images").mkdir(parents=True)

    if eject_templates:
        dest = project_dir / "config" / "templates" / "v2"
        src = Path(str(importlib.resources.files("terradoc.templates_v2")))
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__init__.py", "__pycache__"))

    (project_dir / "static" / "images" / "favicon.svg").write_text(
        DEFAULT_FAVICON_SVG, encoding="utf-8"
    )

    config_content = f"""project_name: "{name}"
project_subtitle: ""
site_title: "{name}"
site_tagline: ""
culture_name: ""
meta_prefix: "{name.lower().replace(' ', '_').replace('-', '_')}"
# BCP 47 code of the language the site documents (e.g. bor, unk, mpu): vernacular text
# gets it as its lang attribute.
language_code: ""
# The site's public address, e.g. https://example.terradoc.org (canonical links, sitemap).
base_url: ""
locales: ["pt", "en"]
locale_labels:
  pt: "Português"
  en: "English"
default_locale: "pt"
featured_article_id: ""
bib_file: "references.bib"

modules:
  dictionary: {{ enabled: true }}
  fauna: {{ enabled: false }}
  ethnobotany: {{ enabled: false }}
  encyclopedia: {{ enabled: true }}
  bibliography: {{ enabled: false }}
  recordings: {{ enabled: false }}
  corpus: {{ enabled: false }}
  videos: {{ enabled: false }}

module_labels:
  dictionary: "Dictionary"
  encyclopedia: "Encyclopedia"
  fauna: "Fauna"
  ethnobotany: "Ethnobotany"
  bibliography: "Bibliography"
  recordings: "Recordings"
  corpus: "Corpus"
  videos: "Videos"

theme:
  templates: v2
  # The neutral pack: no people's patterns. A people's own pack (band, texture, emblem) lives
  # in config/templates/v2/motifs/<name>/ and is recorded, with sources, in CULTURA.md.
  pack: weave
  # Five colour roles, each named after a material (terradoc.palette). These are the
  # project's neutral colours; `terradoc check` refuses combinations that are hard to read.
  palette:
    ground: {{color: "#F7F4EE"}}
    ink: {{color: "#1D1B18"}}
    primary: {{color: "#8A3B12"}}
    fill: {{color: "#D9B36C"}}
    muted: {{color: "#625B52"}}
  favicon: "images/favicon.svg"
  # hero_image: "images/home.jpg"   # in static/
  # hero_credit: ""
  # hero_alt: ""
"""
    (project_dir / "terradoc.yaml").write_text(config_content, encoding="utf-8")

    # terradoc brings the interface strings; a site's locale files hold its own texts.
    for loc in ("pt", "en"):
        (project_dir / "locales" / f"{loc}.yaml").write_text(
            "# The site's own texts (HTML allowed in about_*); terradoc brings the interface.\n"
            'home_sentence: ""\n'
            'about_mission: ""\n'
            'about_partners: ""\n'
            'about_contact: ""\n',
            encoding="utf-8",
        )

    click.echo(f"Created new terradoc project in '{name}/'")
    click.echo(f"  Edit {name}/terradoc.yaml to configure your project")
    click.echo(f"  Add data to {name}/data/")
    click.echo(f"  Run: cd {name} && terradoc build")


@main.command()
@click.option("--config", "-c", "config_path", default="terradoc.yaml",
              help="Path to terradoc.yaml config file")
@click.option("--output", "-o", "output_path", default=None,
              help="Write to file instead of stdout (e.g. data/categories.yaml)")
def categories(config_path: str, output_path: str | None):
    """Dump all category paths from encyclopedia entries."""
    cfg_path = Path(config_path)
    cfg = load_config(cfg_path if cfg_path.exists() else None)

    entries_dir = cfg.data_dir / "encyclopedia"
    if not entries_dir.exists():
        click.echo(f"No encyclopedia directory: {entries_dir}", err=True)
        raise SystemExit(1)

    from terradoc.check_entries import _parse_front_matter

    all_categories: set[str] = set()
    for path in sorted(entries_dir.rglob("*.md")):
        if path.name == "README.md":
            continue
        try:
            fm, _ = _parse_front_matter(path)
        except Exception:
            continue
        cats = fm.get("categories") or fm.get("keywords") or []
        if isinstance(cats, list):
            for cat in cats:
                all_categories.add(str(cat))

    sorted_cats = sorted(all_categories)

    import yaml
    content = yaml.dump(sorted_cats, default_flow_style=False, allow_unicode=True)

    if output_path:
        out = Path(output_path)
        out.write_text(content, encoding="utf-8")
        click.echo(f"Wrote {len(sorted_cats)} categories to {out}")
    else:
        click.echo(content.rstrip())

    click.echo(f"  Total unique category paths: {len(sorted_cats)}", err=True)
