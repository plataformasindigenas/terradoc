# Terradoc

Reusable engine for indigenous documentation platforms.

Terradoc converts structured data (TSV, YAML, markdown, BibTeX) into multilingual static websites for documenting indigenous languages and cultures.

## Features

- **Modular architecture**: Enable/disable dictionary, fauna, encyclopedia, bibliography, and recordings modules
- **Multilingual**: Built-in i18n support with locale-based rendering
- **Themeable**: CSS custom properties driven by YAML configuration
- **Cross-linking**: Automatic links between dictionary, fauna, and encyclopedia entries
- **Static output**: Generates pure HTML/CSS/JS — host anywhere

## Installation

```bash
pip install terradoc
```

## Quick Start

```bash
# Scaffold a new project
terradoc init my-project

# Edit configuration
cd my-project
vim terradoc.yaml

# Add your data to data/
# Build the site
terradoc build
```

## Configuration

Projects are configured via `terradoc.yaml`:

```yaml
project_name: "My Project"
culture_name: "GroupName"
meta_prefix: "group"
locales: ["pt", "en"]
default_locale: "pt"

modules:
  dictionary: { enabled: true }
  fauna: { enabled: true }
  encyclopedia: { enabled: true }
  bibliography: { enabled: true }
  recordings: { enabled: false }

theme:
  colors:
    primary: "#3D352F"
    accent: "#C75B39"
```

## License

GPL-3.0-or-later
