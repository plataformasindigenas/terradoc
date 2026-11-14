"""CLI entry point for terradoc."""

import importlib.resources
import shutil
from pathlib import Path

import click

from terradoc.config import THEME_PRESETS, load_config


STARTER_PAGE_CONFIGS = {
    "index.yaml": """input: ../data/index.json
template: templates/index.html.j2
output: ../docs/index.html
""",
    "dictionary.yaml": """input: ../data/dictionary.json
template: templates/dictionary.html.j2
output: ../docs/dictionary.html
""",
    "fauna.yaml": """input: ../data/fauna.json
template: templates/fauna.html.j2
output: ../docs/fauna.html
""",
    "ethnobotany.yaml": """input: ../data/ethnobotany.json
template: templates/ethnobotany.html.j2
output: ../docs/ethnobotany.html
""",
    "encyclopedia.yaml": """input: ../data/encyclopedia_index.json
template: templates/encyclopedia.html.j2
output: ../docs/encyclopedia.html
""",
    "bibliography.yaml": """input: ../data/bibliography.json
template: templates/bibliography.html.j2
output: ../docs/bibliography.html
""",
    "recordings.yaml": """input: ../data/recordings.json
template: templates/recordings.html.j2
output: ../docs/recordings.html
""",
    "corpus.yaml": """input: ../data/corpus.json
template: templates/corpus.html.j2
output: ../docs/corpus.html
""",
    "videos.yaml": """input: ../data/videos.json
template: templates/videos.html.j2
output: ../docs/videos.html
""",
}

DEFAULT_LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" role="img" aria-label="Project logo">
  <rect width="128" height="128" rx="24" fill="#3D352F"/>
  <circle cx="64" cy="52" r="24" fill="#C75B39"/>
  <path d="M32 94h64" stroke="#F9F6F2" stroke-width="10" stroke-linecap="round"/>
</svg>
"""

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


def _load(config_path: str, out: str | None = None, bundle_dir: str | None = None):
    cfg_path = Path(config_path)
    if not cfg_path.exists():
        click.echo(f"Config file not found: {cfg_path}", err=True)
        raise SystemExit(1)
    cfg = load_config(cfg_path)
    if out:
        cfg.output_dir = Path(out).resolve()
    if bundle_dir:
        cfg.bundle_dir_override = Path(bundle_dir).resolve()
    return cfg


def _config_option(f):
    return click.option("--config", "-c", "config_path", default="terradoc.yaml",
                        help="Path to terradoc.yaml config file")(f)


def _bundle_option(f):
    return click.option("--bundle-dir", default=None, type=click.Path(file_okay=False),
                        help="Where the export bundle is written/read (default: data/)")(f)


def _out_options(f):
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
def render(config_path: str, bundle_dir: str | None, out: str | None, clean: bool):
    """Render the site from an existing export bundle."""
    from terradoc.build_site import render_site

    cfg = _load(config_path, out=out, bundle_dir=bundle_dir)
    with _friendly_errors():
        render_site(cfg, clean=clean)
    click.echo("\n=== Render Complete ===")


@main.command()
@_config_option
@_bundle_option
@_out_options
@click.option("--format", "fmt", default="text", type=click.Choice(FORMATS),
              help="Format of the check report printed first")
def build(config_path: str, bundle_dir: str | None, out: str | None, clean: bool, fmt: str):
    """Build the complete site: check, export, render."""
    from terradoc.build_site import render_site
    from terradoc.export import export_bundle

    cfg = _load(config_path, out=out, bundle_dir=bundle_dir)
    if not _report(cfg, fmt):
        click.echo("Build stopped: fix the errors above.", err=True)
        raise SystemExit(1)
    click.echo()
    with _friendly_errors():
        if clean:  # refuse before doing any work
            from terradoc.build_site import assert_safe_to_clean
            assert_safe_to_clean(cfg)
        export_bundle(cfg, run_checks=False)  # just checked above
        render_site(cfg, clean=clean)
    click.echo("\n=== Build Complete ===")


@main.command()
@click.argument("name", default="my-project")
@click.option("--theme", "theme_preset", default="terra",
              type=click.Choice(list(THEME_PRESETS.keys())),
              help="Theme preset to use (default: terra)")
@click.option("--eject-templates", is_flag=True,
              help="Copy the bundled templates into config/templates/ for local "
                   "customisation. A local copy shadows every terradoc template "
                   "update, so prefer config options and locale keys.")
def init(name: str, theme_preset: str, eject_templates: bool):
    """Scaffold a new terradoc project."""
    project_dir = Path(name)
    if project_dir.exists():
        click.echo(f"Directory '{name}' already exists", err=True)
        raise SystemExit(1)

    project_dir.mkdir()
    (project_dir / "config").mkdir()
    (project_dir / "data").mkdir()
    (project_dir / "data" / "encyclopedia").mkdir()
    (project_dir / "locales").mkdir()
    # static/ is copied verbatim into the site root by `terradoc build`
    (project_dir / "static" / "images").mkdir(parents=True)

    if eject_templates:
        (project_dir / "config" / "templates").mkdir(parents=True)
        templates_src = importlib.resources.files("terradoc.templates")
        for template_src in templates_src.iterdir():
            if template_src.name.endswith(".j2"):
                shutil.copy2(
                    str(template_src),
                    str(project_dir / "config" / "templates" / template_src.name),
                )

    # Create starter page configs
    for filename, content in STARTER_PAGE_CONFIGS.items():
        (project_dir / "config" / filename).write_text(content, encoding="utf-8")

    (project_dir / "static" / "images" / "logo.svg").write_text(
        DEFAULT_LOGO_SVG, encoding="utf-8"
    )
    (project_dir / "static" / "images" / "favicon.svg").write_text(
        DEFAULT_FAVICON_SVG, encoding="utf-8"
    )

    # Create default config
    preset = THEME_PRESETS[theme_preset]
    config_content = f"""project_name: "{name}"
project_subtitle: ""
site_title: "{name}"
site_tagline: ""
culture_name: ""
meta_prefix: "{name.lower().replace(' ', '_').replace('-', '_')}"
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
  preset: "{theme_preset}"
  logo: "images/logo.svg"
  favicon: "images/favicon.svg"
  colors:
    primary: "{preset['colors']['primary']}"
    accent: "{preset['colors']['accent']}"
  # module_intensity:
  #   dictionary: "minimal"
  #   encyclopedia: "balanced"
  #   fauna: "rich"
  # term_color: ""
  # term_weight: "600"
"""

    (project_dir / "terradoc.yaml").write_text(config_content, encoding="utf-8")

    # Create minimal locale files
    pt_locale = """html_lang: pt-BR
nav_brand: "{name}"
nav_dictionary: Dicionário
nav_encyclopedia: Enciclopédia
nav_about: Sobre
index_title: Início
index_hero_title: "{name}"
about_title: "Sobre"
about_subtitle: ""
about_mission_heading: "Missão"
about_mission: ""
about_partners_heading: "Equipe e Parceiros"
about_partners: ""
about_contact_heading: "Contato"
about_contact: ""
about_citation_heading: "Como Citar"
about_citation: ""
about_tools_heading: "Construído Com"
"""
    (project_dir / "locales" / "pt.yaml").write_text(
        pt_locale.format(name=name), encoding="utf-8"
    )

    en_locale = """html_lang: en
nav_brand: "{name}"
nav_dictionary: Dictionary
nav_encyclopedia: Encyclopedia
nav_about: About
index_title: Home
index_hero_title: "{name}"
about_title: "About"
about_subtitle: ""
about_mission_heading: "Mission"
about_mission: ""
about_partners_heading: "Team & Partners"
about_partners: ""
about_contact_heading: "Contact"
about_contact: ""
about_citation_heading: "How to Cite"
about_citation: ""
about_tools_heading: "Built With"
"""
    (project_dir / "locales" / "en.yaml").write_text(
        en_locale.format(name=name), encoding="utf-8"
    )

    click.echo(f"Created new terradoc project in '{name}/' (theme: {theme_preset})")
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


@main.command()
def themes():
    """List available theme presets."""
    click.echo("Available theme presets:\n")
    for name, preset in THEME_PRESETS.items():
        desc = preset.get("description", "")
        default = " (default)" if name == "terra" else ""
        click.echo(f"  {name}{default}")
        if desc:
            click.echo(f"    {desc}")
        click.echo(f"    Style: {preset.get('style', name)}")
        click.echo(f"    Primary: {preset['colors']['primary']}  Accent: {preset['colors']['accent']}")
        click.echo()
