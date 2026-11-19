"""Configuration for terradoc projects."""

import importlib.resources
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ModuleConfig:
    enabled: bool = True
    graph: bool = False


@dataclass
class ThemeConfig:
    """`theme:` in terradoc.yaml (the v2 people layer; see meta REDESIGN-PLAN.md)."""
    templates: str = "v2"  # template set; see TEMPLATE_SETS
    palette: dict = field(default_factory=dict)  # role -> {color, material}; terradoc.palette
    pack: str = "weave"  # motif pack: config/templates/v2/motifs/<pack>/ or bundled; "none"
    hero_image: str = ""  # the home photograph, in static/
    hero_credit: str = ""  # who took the hero photograph (shown under it)
    hero_alt: str = ""  # what the hero photograph shows, for screen readers
    hero_people: bool = True  # False: the hero shows a landscape or object (D25)
    favicon: str = "images/favicon.svg"  # in static/; without it, the pack's emblem
    # The text face (vernacular, Portuguese and IPA alike): gentium (default), charis,
    # andika. Charis was D16's choice, but its tilde reads as a macron at text sizes.
    font_vernacular: str = "gentium"

    def media(self) -> dict[str, str]:
        """Files in static/ that the theme names, by key (checked by `terradoc check`)."""
        return {k: v for k, v in (("hero_image", self.hero_image), ("favicon", self.favicon)) if v}


@dataclass
class TerradocConfig:
    project_name: str = "Terradoc Project"
    project_subtitle: str = ""
    site_title: str = ""
    site_tagline: str = ""
    culture_name: str = ""
    meta_prefix: str = "terradoc"
    locales: list[str] = field(default_factory=lambda: ["pt", "en"])
    # The language's own alphabet, in order; letters may be digraphs ("mb", "ng").
    # Empty = first character and Portuguese collation, as before.
    alphabet: list[str] = field(default_factory=list)
    # v2 dictionary search: letters that count as the same letter when searching, as
    # {letter: stands for}, e.g. {r: l, b: w, u: o} (Enawenê-Nawê). Accents are always ignored.
    search_folds: dict[str, str] = field(default_factory=dict)
    # Extra keys for the on-screen keyboard (it shows the alphabet's non-ASCII letters plus
    # these), e.g. [á, é, í, ó, ú].
    keyboard: list[str] = field(default_factory=list)
    unknown_theme_keys: list[str] = field(default_factory=list)  # filled by load_config
    locale_labels: dict[str, str] = field(default_factory=lambda: {
        "pt": "Português",
        "en": "English",
        "es": "Español",
    })
    default_locale: str = "pt"
    # ISO 639-3 / BCP 47 code of the people's language (bor, unk, mpu): `lang` on
    # vernacular text in v2, so browsers and screen readers do not read it as Portuguese.
    language_code: str = ""
    # The site's public address, e.g. "https://makurap.terradoc.org". The sitemap needs
    # absolute URLs; without base_url no sitemap is written.
    base_url: str = ""
    # Where the footer's project link ("Plataformas Indígenas", string ui_project) goes.
    project_url: str = "https://terradoc.org/"
    featured_article_id: str = ""
    bib_file: str = "references.bib"
    ethnobotany_encyclopedia_categories: list[str] = field(
        default_factory=lambda: ["natureza/flora"]
    )
    theme: ThemeConfig = field(default_factory=ThemeConfig)

    modules: dict[str, ModuleConfig] = field(default_factory=lambda: {
        "dictionary": ModuleConfig(),
        "fauna": ModuleConfig(),
        "ethnobotany": ModuleConfig(),
        "encyclopedia": ModuleConfig(),
        "bibliography": ModuleConfig(),
        "recordings": ModuleConfig(),
        "corpus": ModuleConfig(),
        "videos": ModuleConfig(),
    })
    module_order: list[str] = field(default_factory=lambda: [
        "dictionary", "encyclopedia", "fauna", "ethnobotany",
        "bibliography", "recordings", "corpus", "videos",
    ])
    module_labels: dict[str, str] = field(default_factory=lambda: {
        "dictionary": "Dictionary",
        "encyclopedia": "Encyclopedia",
        "fauna": "Fauna",
        "ethnobotany": "Ethnobotany",
        "bibliography": "Bibliography",
        "recordings": "Recordings",
        "corpus": "Corpus",
        "videos": "Videos",
    })

    # Paths (set after loading)
    base_dir: Path = field(default_factory=Path.cwd)
    # Optional overrides (CLI --out / --bundle-dir). None keeps the historic
    # layout: site in docs/, generated JSON next to the sources in data/.
    output_dir: Path | None = None
    bundle_dir_override: Path | None = None

    @property
    def data_dir(self) -> Path:
        """Source data (TSV/YAML/Markdown/BibTeX). Read-only during a build."""
        return self.base_dir / "data"

    @property
    def docs_dir(self) -> Path:
        """Where the rendered site is written."""
        if self.output_dir is not None:
            return self.output_dir
        return self.base_dir / "docs"

    @property
    def bundle_dir(self) -> Path:
        """Where generated, normalised JSON (the export bundle) is written."""
        if self.bundle_dir_override is not None:
            return self.bundle_dir_override
        return self.data_dir

    @property
    def static_dir(self) -> Path:
        """Files copied verbatim into the site root (images, audio, ...)."""
        return self.base_dir / "static"

    @property
    def config_dir(self) -> Path:
        return self.base_dir / "config"

    @property
    def locales_dir(self) -> Path:
        return self.base_dir / "locales"

    @property
    def bundled_template_dir(self) -> Path:
        """terradoc's own templates."""
        return Path(str(importlib.resources.files("terradoc.templates_v2")))

    @property
    def local_template_dir(self) -> Path:
        """The site's own templates, `config/templates/v2/` (may not exist)."""
        return self.config_dir / "templates" / "v2"

    def is_module_enabled(self, name: str) -> bool:
        mod = self.modules.get(name)
        return mod.enabled if mod else False

    def is_graph_enabled(self, name: str) -> bool:
        mod = self.modules.get(name)
        return mod.graph if mod else False

    def enabled_modules(self) -> list[dict]:
        """Return list of enabled module info dicts for template rendering."""
        # Use configured order; append any enabled modules not listed in order
        ordered = list(self.module_order)
        for name in self.modules:
            if name not in ordered:
                ordered.append(name)
        return [
            {"slug": name, "name": self.module_label(name)}
            for name in ordered
            if self.is_module_enabled(name)
        ]

    def locale_label(self, code: str) -> str:
        """Return a human-readable label for a locale code."""
        return self.locale_labels.get(code, code.upper())

    def module_label(self, name: str) -> str:
        """Return the display label for a module slug."""
        return self.module_labels.get(name, name.replace("_", " ").title())

    def resolve_schema(self, module_slug: str) -> Path:
        """Resolve a schema path, preferring local overrides in data/."""
        local = self.data_dir / f"{module_slug}_schema.yaml"
        if local.exists():
            return local
        package_schema = importlib.resources.files("terradoc.schemas") / f"{module_slug}_schema.yaml"
        return Path(str(package_schema))

    def site_context(self) -> dict[str, str]:
        """Return common site identity values for templates."""
        title = self.site_title or self.project_name
        tagline = self.site_tagline or self.project_subtitle
        ctx = {
            "title": title,
            "tagline": tagline,
            "alphabet": self.alphabet,
        }
        ctx.update({
            f"{slug}_label": self.module_label(slug) for slug in self.modules
        })
        return ctx


# Template sets this version ships. v1 was removed in 0.23.0 (meta REDESIGN-PLAN.md P6).
TEMPLATE_SETS = ("v2",)

# Every key `theme:` may hold; anything else is reported by `terradoc check`.
THEME_KEYS = frozenset({
    "templates", "palette", "pack", "hero_image", "hero_credit", "hero_alt", "hero_people",
    "favicon", "font_vernacular",
})

# Keys of the v1 template set, removed in 0.23.0: `check` names the release in its error.
REMOVED_THEME_KEYS = frozenset({
    "preset", "colors", "colors_dark", "module_intensity", "logo", "font_family",
    "font_family_headings", "font_family_mono", "font_family_ipa", "border_radius", "style",
    "term_color", "term_weight", "hero_background", "hero_motif", "hero_divider",
    "hero_height", "page_badge", "grain_pattern", "hero_images", "hero_stats", "extra_css",
})


def load_config(config_path: Path | None = None) -> TerradocConfig:
    """Load configuration from a YAML file, or return defaults."""
    if config_path and config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        if not isinstance(raw, dict):
            raise ValueError(
                f"Invalid terradoc.yaml at {config_path}: expected a YAML mapping at top level"
            )

        config = TerradocConfig()
        for key in ("project_name", "project_subtitle", "site_title",
                     "site_tagline", "culture_name",
                     "meta_prefix", "default_locale", "featured_article_id",
                     "bib_file", "base_url", "language_code", "project_url"):
            if key in raw:
                setattr(config, key, raw[key])

        if "ethnobotany_encyclopedia_categories" in raw:
            val = raw["ethnobotany_encyclopedia_categories"]
            if isinstance(val, list):
                config.ethnobotany_encyclopedia_categories = [str(v) for v in val]

        if "alphabet" in raw:
            if not isinstance(raw["alphabet"], list) or not all(isinstance(x, str) and x.strip() for x in raw["alphabet"]):
                raise ValueError("terradoc.yaml: 'alphabet' must be a list of letters, e.g. [a, ã, e, mb]")
            config.alphabet = [str(x).strip() for x in raw["alphabet"]]
        if "search_folds" in raw:
            folds = raw["search_folds"]
            if not isinstance(folds, dict) or not all(
                    isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip()
                    for k, v in folds.items()):
                raise ValueError("terradoc.yaml: 'search_folds' must map letters to letters, e.g. {r: l, u: o}")
            config.search_folds = {k.strip(): v.strip() for k, v in folds.items()}
        if "keyboard" in raw:
            if not isinstance(raw["keyboard"], list) or not all(isinstance(x, str) and x.strip() for x in raw["keyboard"]):
                raise ValueError("terradoc.yaml: 'keyboard' must be a list of letters, e.g. [á, é]")
            config.keyboard = [x.strip() for x in raw["keyboard"]]
        if "locales" in raw:
            config.locales = raw["locales"]
        if "locale_labels" in raw and isinstance(raw["locale_labels"], dict):
            config.locale_labels.update({
                str(key): str(value) for key, value in raw["locale_labels"].items()
            })

        if "theme" in raw:
            theme_raw = raw["theme"]
            if not isinstance(theme_raw, dict):
                raise ValueError(
                    "Invalid 'theme' in terradoc.yaml: expected a YAML mapping/object"
                )
            for theme_key in ("hero_image", "favicon"):
                if theme_key in theme_raw:
                    setattr(config.theme, theme_key, str(theme_raw[theme_key] or ""))

            if "templates" in theme_raw:
                config.theme.templates = str(theme_raw["templates"])
            if "palette" in theme_raw:  # validated by `check` and by the v2 build
                config.theme.palette = theme_raw["palette"]
            for key in ("pack", "hero_credit", "hero_alt", "font_vernacular"):
                if key in theme_raw:
                    setattr(config.theme, key, str(theme_raw[key] or ""))
            if "hero_people" in theme_raw:
                value = theme_raw["hero_people"]
                config.theme.hero_people = (value if isinstance(value, bool)
                                            else str(value).strip().lower() not in ("false", "no", "0", ""))
            # A misspelt or newer key would otherwise be ignored without a word;
            # `terradoc check` turns these into errors.
            config.unknown_theme_keys = sorted(str(k) for k in theme_raw if k not in THEME_KEYS)

        if "module_order" in raw and isinstance(raw["module_order"], list):
            config.module_order = [str(m) for m in raw["module_order"]]

        if "modules" in raw:
            for mod_name, mod_cfg in raw["modules"].items():
                if isinstance(mod_cfg, dict):
                    config.modules[mod_name] = ModuleConfig(**mod_cfg)
        if "module_labels" in raw and isinstance(raw["module_labels"], dict):
            config.module_labels.update({
                str(key): str(value) for key, value in raw["module_labels"].items()
            })

        config.base_dir = config_path.parent
        return config

    return TerradocConfig()
