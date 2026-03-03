"""CLI entry point for terradoc."""

import importlib.resources
import shutil
from pathlib import Path

import click

from terradoc.config import TerradocConfig, load_config


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
    "encyclopedia.yaml": """input: ../data/encyclopedia_index.json
template: templates/encyclopedia.html.j2
output: ../docs/encyclopedia.html
""",
    "bibliography.yaml": """input: ../data/bibliography.json
template: templates/bibliography.html.j2
output: ../docs/bibliography.html
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


@main.command()
@click.option("--config", "-c", "config_path", default="terradoc.yaml",
              help="Path to terradoc.yaml config file")
def build(config_path: str):
    """Build the complete site."""
    cfg_path = Path(config_path)
    if not cfg_path.exists():
        click.echo(f"Config file not found: {cfg_path}", err=True)
        raise SystemExit(1)

    cfg = load_config(cfg_path)

    # Step 1: Check encyclopedia entries (if enabled)
    if cfg.is_module_enabled("encyclopedia"):
        from terradoc.check_entries import check_entries
        result = check_entries(cfg.data_dir)
        if result != 0:
            raise SystemExit(result)
        click.echo()

    # Step 2: Run converters
    from terradoc.convert import run_all_converters
    counts = run_all_converters(cfg)

    # Step 3: Post-processing
    from terradoc.cross_linker import attach_recordings_to_dictionary, cross_link_datasets

    if cfg.is_module_enabled("recordings") and cfg.is_module_enabled("dictionary"):
        attach_recordings_to_dictionary(cfg)
        click.echo()

    cross_link_datasets(cfg)
    click.echo()

    # Step 4: Copy data files
    from terradoc.index_builder import copy_data_to_docs, generate_index
    copy_data_to_docs(cfg)
    click.echo()

    generate_index(counts, cfg)
    click.echo()

    # Step 5: Build site
    from terradoc.build_site import build_site
    build_site(cfg)

    click.echo("\n=== Build Complete ===")


@main.command()
@click.argument("name", default="my-project")
def init(name: str):
    """Scaffold a new terradoc project."""
    project_dir = Path(name)
    if project_dir.exists():
        click.echo(f"Directory '{name}' already exists", err=True)
        raise SystemExit(1)

    project_dir.mkdir()
    (project_dir / "config").mkdir()
    (project_dir / "config" / "templates").mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "data" / "encyclopedia").mkdir()
    (project_dir / "locales").mkdir()
    (project_dir / "docs").mkdir()
    (project_dir / "docs" / "images").mkdir(parents=True)
    (project_dir / "docs" / "js").mkdir(parents=True)

    # Copy bundled templates
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

    # Copy common.js
    js_src = importlib.resources.files("terradoc.static.js") / "common.js"
    shutil.copy2(str(js_src), str(project_dir / "docs" / "js" / "common.js"))
    (project_dir / "docs" / "images" / "logo.svg").write_text(
        DEFAULT_LOGO_SVG, encoding="utf-8"
    )
    (project_dir / "docs" / "images" / "favicon.svg").write_text(
        DEFAULT_FAVICON_SVG, encoding="utf-8"
    )

    # Create default config
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
  encyclopedia: {{ enabled: true }}
  bibliography: {{ enabled: false }}
  recordings: {{ enabled: false }}

module_labels:
  dictionary: "Dictionary"
  encyclopedia: "Encyclopedia"
  fauna: "Fauna"
  bibliography: "Bibliography"

theme:
  logo: "images/logo.svg"
  favicon: "images/favicon.svg"
  colors:
    primary: "#3D352F"
    accent: "#C75B39"
"""

    (project_dir / "terradoc.yaml").write_text(config_content, encoding="utf-8")

    # Create minimal locale files
    pt_locale = """html_lang: pt-BR
nav_brand: "{name}"
nav_dictionary: Dicionário
nav_encyclopedia: Enciclopédia
index_title: Início
index_hero_title: "{name}"
"""
    (project_dir / "locales" / "pt.yaml").write_text(
        pt_locale.format(name=name), encoding="utf-8"
    )

    en_locale = """html_lang: en
nav_brand: "{name}"
nav_dictionary: Dictionary
nav_encyclopedia: Encyclopedia
index_title: Home
index_hero_title: "{name}"
"""
    (project_dir / "locales" / "en.yaml").write_text(
        en_locale.format(name=name), encoding="utf-8"
    )

    click.echo(f"Created new terradoc project in '{name}/'")
    click.echo(f"  Edit {name}/terradoc.yaml to configure your project")
    click.echo(f"  Add data to {name}/data/")
    click.echo(f"  Run: cd {name} && terradoc build")


def resolve_schema(module_slug: str, config: TerradocConfig) -> Path:
    """Resolve schema path — local overrides package defaults."""
    local = config.data_dir / f"{module_slug}_schema.yaml"
    if local.exists():
        return local
    package_schema = importlib.resources.files("terradoc.schemas") / f"{module_slug}_schema.yaml"
    return Path(str(package_schema))
