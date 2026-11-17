# Terradoc

Terradoc is a Python toolkit for building multilingual documentation websites for Indigenous languages, ecological knowledge, and community-led cultural archives.

It was developed as the reusable publishing engine behind the [Plataforma de Linguas Indigenas](https://portal.plataformasindigenas.org), an initiative focused on language revitalization, documentation, educational access, and long-term community stewardship of linguistic and cultural knowledge in Brazil.

Rather than treating language data as a generic CMS problem, Terradoc is designed for projects that need:

- structured lexical and encyclopedic data
- multilingual presentation
- static deployment on low-complexity infrastructure
- community-specific branding and terminology
- traceable, file-based content workflows that can be reviewed and archived

## What Terradoc Does

Terradoc converts structured project data into a complete static website.

A typical project combines:

- dictionary or lexicon records
- encyclopedia articles
- fauna or ethnobiological entries
- bibliography data
- optional recordings metadata
- locale files for multilingual interface text

From those inputs, Terradoc validates data integrity, converts source formats, and generates HTML pages and JSON assets that can be published on standard static hosting without requiring a database or application server.

## Context And Use Case

Terradoc exists to support documentation and revitalization work where language materials are not just technical assets, but part of a broader social, educational, and ethical process.

In the context of the Plataforma de Linguas Indigenas, this includes:

- producing accessible digital materials for Indigenous communities, educators, and researchers
- organizing lexical, cultural, and reference content in a consistent format
- enabling multilingual public-facing portals
- keeping infrastructure simple enough to maintain and replicate across multiple community-specific platforms

The work is also shaped by governance principles that are essential in Indigenous language documentation, including free, prior, and informed consent, community data stewardship, and responsible handling of culturally sensitive materials. Terradoc does not replace those governance processes, but it is intended to support workflows where they are taken seriously.

This makes Terradoc particularly useful for:

- Indigenous language documentation initiatives
- community archives
- educational language portals
- collaborative research projects that need transparent, file-based publishing

## For Partners And Funders

Terradoc supports a model of digital language infrastructure that is practical, replicable, and aligned with long-term stewardship.

For institutions, partner organizations, and funders, the value is not only in the websites it produces, but in the operational model it enables:

- low-complexity deployment without expensive hosting infrastructure
- reproducible publication workflows that reduce dependence on custom web development
- reusable architecture that can support multiple community-specific platforms
- clearer separation between content stewardship and software maintenance
- durable outputs that can be archived, transferred, and maintained over time

In the broader context of Indigenous language revitalization, this matters because digital tools often fail when they are too expensive, too opaque, or too dependent on a single developer or institution. Terradoc is designed to reduce those risks by emphasizing structured data, static publishing, and maintainable project conventions.

It is also designed to fit projects where community control over publication decisions matters. In practice, that means the software works well in environments that require reviewable source files, explicit content pipelines, and governance checkpoints before publication.

## For Developers

Terradoc is intended for developers who need to build and maintain documentation portals without reinventing the full publishing stack for each project.

From an engineering perspective, the package provides:

- a Python-based CLI for project scaffolding and site builds
- a `src`-layout package with bundled templates and schema files
- configuration-driven customization through YAML
- static output suitable for simple deployment targets
- a codebase that is easier to audit and adapt than a bespoke CMS integration

If you are integrating Terradoc into a larger documentation workflow, the main extension points are configuration, local template overrides, upstream data preparation, and deployment automation around the generated `docs/` directory.

## Core Capabilities

- Modular site generation for dictionary, encyclopedia, fauna, ethnobotany, bibliography, recordings, and videos content
- Multilingual rendering with locale-based navigation and page generation
- Static-site output that can be hosted on GitHub Pages, institutional servers, or any basic web host
- Bundled templates that can be overridden per project
- Theme presets (`terra`, `classic`) with full color palettes, font stacks, and decorative macro system
- Per-module decoration intensity (`minimal`, `balanced`, `rich`) and indigenous-language term emphasis
- Data validation: ID format enforcement, filename consistency, `see_also` referential integrity, bibliography key resolution, and optional category vocabulary
- Data completeness reporting after conversion
- Cross-linking between datasets to improve navigation across related entries
- Built-in project scaffolding for new sites

## Typical Outputs

Depending on the modules enabled and the source material available, a Terradoc project can be used to publish:

- a multilingual dictionary portal for community and school use
- a cultural encyclopedia with articles, linked references, and internal cross-navigation
- a fauna or ethnobiological knowledge section connected to lexical entries
- a bibliography or research reference index for teachers, researchers, and collaborators
- a recordings catalog that connects audio metadata to lexical or educational content
- a lightweight digital documentation portal that can be maintained and republished without a custom web backend

## How It Works

Terradoc uses a project directory with a predictable structure:

```text
my-project/
  terradoc.yaml
  config/
    index.yaml
    dictionary.yaml
    fauna.yaml
    ethnobotany.yaml
    encyclopedia.yaml
    bibliography.yaml
    recordings.yaml
    videos.yaml
  data/
    encyclopedia/        # Markdown articles with YAML front matter
    categories.yaml      # Optional: controlled category vocabulary
    dictionary.tsv
    fauna.yaml
    ethnobotany.yaml
    references.bib
    recordings.yaml
    videos.yaml
  locales/
  static/               # copied verbatim into the site root (images/, audio/, ...)
  docs/                 # generated site (default output; git-ignore it)
```

Templates are bundled with terradoc. A project may shadow them with its own
`config/templates/` (`terradoc init --eject-templates`), but a local copy stops
receiving terradoc's template fixes, so prefer configuration and locale keys.

The standard workflow is:

1. Scaffold a new project.
2. Add or adapt your configuration.
3. Place source data in the project directories.
4. Run `terradoc check` (fast, writes nothing) and then `terradoc build`.
5. Publish the generated `docs/` output (or `--out DIR`).

## Installation

```bash
pip install terradoc
```

For development, install from source:

```bash
git clone https://github.com/plataformasindigenas/terradoc.git
cd terradoc
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Quick Start

Create a new project (optionally choose a theme preset):

```bash
terradoc init my-project
terradoc init my-project --theme classic
```

Move into the project and edit the main configuration:

```bash
cd my-project
```

Build the site:

```bash
terradoc build
```

The generated site will be written to `docs/`.

## Command-Line Interface

- `terradoc init <name> [--theme PRESET] [--eject-templates]`: scaffold a new project with starter configuration, locales, and asset placeholders in `static/`
- `terradoc check [-c CONFIG] [--format text|github|json]`: validate everything (see *Data Validation*) without writing anything; exit 1 on errors. `--format github` prints GitHub Actions annotations
- `terradoc export [-c CONFIG] [--bundle-dir DIR]`: write the normalised, cross-linked JSON bundle (format still experimental, see `docs/bundle.md`)
- `terradoc render [-c CONFIG] [--bundle-dir DIR] [--out DIR] [--clean]`: render the site from an existing bundle
- `terradoc build [-c CONFIG] [--bundle-dir DIR] [--out DIR] [--clean]`: `check`, then `export`, then `render`. Defaults keep the historic layout (bundle in `data/`, site in `docs/`); CI should pass `--bundle-dir` and `--out` so the checkout is never modified. `--clean` empties the output directory first and is refused without `--out`
- `terradoc guard --current DIR [--previous DIR] [--baseline DIR] [--confirm-shrink]`: compare a built site with the release it replaces; blocks unexpected loss of records or files
- `check` and `guard` also take `--format markdown [--codeowners FILE] [--run-url URL]` for issue bodies
- Publishing from GitHub (every branch, previews, failure issues): see `docs/publishing.md`
- `terradoc categories [-o FILE]`: dump all unique category paths from encyclopedia entries (use `-o data/categories.yaml` to bootstrap a controlled vocabulary)
- `terradoc themes`: list available theme presets with their color palettes

## Configuration

Projects are configured through `terradoc.yaml`. A minimal example:

```yaml
project_name: "My Project"
project_subtitle: "Community documentation portal"
site_title: "My Project"
site_tagline: "Language, knowledge, and memory"
culture_name: "Community Name"
meta_prefix: "my_project"
locales: ["pt", "en"]
default_locale: "pt"
base_url: "https://example.terradoc.org"   # for the sitemap (absolute URLs); none without it

modules:
  dictionary: { enabled: true }
  fauna: { enabled: true }
  encyclopedia: { enabled: true }
  ethnobotany: { enabled: true }
  bibliography: { enabled: true }
  recordings: { enabled: false }
  videos: { enabled: false }

# Optional: control navigation and index card order
module_order:
  - dictionary
  - encyclopedia
  - fauna
  - ethnobotany
  - bibliography
  - recordings
  - videos

theme:
  preset: "terra"               # or "classic"
  logo: "images/logo.svg"
  favicon: "images/favicon.svg"
  colors:                       # override individual preset colors
    primary: "#3D352F"
    accent: "#C75B39"
  module_intensity:             # decoration density per page
    dictionary: "minimal"
    encyclopedia: "balanced"
    fauna: "rich"
  # term_color: "#A85D33"       # color for .td-term spans
  # term_weight: "600"          # font-weight for .td-term spans
```

Local templates in `config/templates/` take precedence over the bundled defaults, which makes it straightforward to adapt Terradoc to different communities, institutions, and visual identities without forking the package.

### Data Validation

`terradoc check` (also the first step of `terradoc build`) reports every problem
with its file and line. **Errors block the build; warnings do not.**

- **Schemas**: every row of every enabled tabular module is validated against its schema (all errors, not just the first)
- **Consent**: every `videos` and `recordings` row must state `consent: approved` (community consent to publish it) or `consent: external` (someone else's public media that the site only embeds). Anything else, including a missing field, blocks the build
- **Media**: every `images/...` / `audio/...` path referenced by the data, the encyclopedia front matter or the theme must exist in `static/` (or, for older projects, `docs/`)
- **Dry export**: the real export runs into a throwaway directory, so anything the build would trip on is caught here

Encyclopedia entries are also checked:

- **ID format**: must match `[a-z0-9][a-z0-9-]*` (no uppercase, spaces, underscores, or accents)
- **Filename consistency**: each file's stem must match its `id` front-matter field
- **`see_also` integrity**: every cross-reference target must exist as an entry
- **Bibliography keys**: all referenced BibTeX keys must resolve against the `.bib` file
- **Category vocabulary**: if `data/categories.yaml` exists, entry categories are validated against it

To bootstrap a controlled category vocabulary from existing data:

```bash
terradoc categories -o data/categories.yaml
```

## Project Philosophy

Terradoc is intentionally simple in its deployment model:

- content lives in files
- output is static
- infrastructure requirements are minimal
- project customization happens through configuration and templates

This design makes the system easier to audit, preserve, replicate, and maintain over time, especially in collaborations where longevity and handover matter as much as feature velocity.

That same design also supports stronger governance practices:

- source materials can be reviewed before publication
- content decisions remain visible in files and configuration
- project teams can maintain clearer boundaries around what is and is not published
- community review processes are easier to integrate than in opaque hosted systems

Terradoc is a publishing engine, not a policy framework, but it is built to work within projects that prioritize consent, community data sovereignty, and responsible stewardship.

## Development

Run the test suite with:

```bash
pytest -q
```

Build distributable artifacts with:

```bash
python -m build
python -m twine check dist/*
```

## Contributing

Contributions are welcome, especially improvements related to:

- documentation workflows
- multilingual and accessibility support
- template flexibility
- data validation and conversion pipelines
- community-oriented publishing use cases

If you plan to make substantial changes, align them with the project's core priorities: reproducible builds, transparent data flows, and maintainable static output.

## License

Terradoc is licensed under the GNU GPL v3.0 or later. See [LICENSE](LICENSE).
