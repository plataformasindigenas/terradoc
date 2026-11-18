"""Configuration for terradoc projects."""

import importlib.resources
from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml


@dataclass
class ModuleConfig:
    enabled: bool = True
    graph: bool = False


@dataclass
class ThemeColors:
    primary: str = "#C81F2D"
    accent: str = "#D4A03A"
    accent_muted: str = "#A01924"
    bg: str = "#F4F1EA"
    bg_light: str = "#EDE9E0"
    bg_infobox: str = "#FAF8F4"
    border: str = "#DDD8CE"
    border_dark: str = "#B8AFA2"
    text: str = "#111827"
    text_muted: str = "#6B6F5A"
    highlight: str = "#FFF9DB"
    warning_bg: str = "#FFF8E1"
    surface: str = "#FFFFFF"
    border_light: str = "#ECEAE5"
    text_secondary: str = "#6B6F5A"
    accent_light: str = "#FDECEA"
    success: str = "#4A7C59"
    error: str = "#C44536"
    accent_ring: str = "rgba(200, 31, 45, 0.2)"
    dark: str = "#0B0F17"

    def to_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


THEME_PRESETS: dict[str, dict] = {
    "terra": {
        "style": "terra",
        "colors": {
            "primary": "#C81F2D",
            "accent": "#D4A03A",
            "accent_muted": "#A01924",
            "bg": "#F4F1EA",
            "bg_light": "#EDE9E0",
            "bg_infobox": "#FAF8F4",
            "border": "#DDD8CE",
            "border_dark": "#B8AFA2",
            "text": "#111827",
            "text_muted": "#6B6F5A",
            "highlight": "#FFF9DB",
            "warning_bg": "#FFF8E1",
            "surface": "#FFFFFF",
            "border_light": "#ECEAE5",
            "text_secondary": "#6B6F5A",
            "accent_light": "#FDECEA",
            "success": "#4A7C59",
            "error": "#C44536",
            "accent_ring": "rgba(200, 31, 45, 0.2)",
            "dark": "#0B0F17",
        },
        "font_family": (
            "'Inter', -apple-system, BlinkMacSystemFont, "
            "'Segoe UI', sans-serif"
        ),
        "font_family_headings": "'Sora', 'Inter', sans-serif",
        "font_family_mono": "'IBM Plex Mono', 'Consolas', monospace",
        "border_radius": "28px",
        "module_intensity": {},
        "term_color": "",
        "term_weight": "600",
        "description": "Warm, organic theme with nature-inspired palette",
    },
    "classic": {
        "style": "classic",
        "colors": {
            "primary": "#3D352F",
            "accent": "#B7522C",
            "accent_muted": "#9A4427",
            "bg": "#F9F6F2",
            "bg_light": "#F5EDE8",
            "bg_infobox": "#FAF8F5",
            "border": "#E8E4DF",
            "border_dark": "#C8B8A8",
            "text": "#333333",
            "text_muted": "#6B6B6B",
            "highlight": "#fff59d",
            "warning_bg": "#fff8e1",
            "surface": "#FFFFFF",
            "border_light": "#EEEEEE",
            "text_secondary": "#555555",
            "accent_light": "#FDF0EB",
            "success": "#5B8C5A",
            "error": "#CC0000",
            "accent_ring": "rgba(183, 82, 44, 0.2)",
        },
        "font_family": (
            "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
            "Oxygen, Ubuntu, sans-serif"
        ),
        "font_family_headings": "",
        "font_family_mono": "'Lucida Sans Unicode', 'DejaVu Sans', monospace",
        "border_radius": "4px",
        "module_intensity": {},
        "term_color": "",
        "term_weight": "600",
        "description": "Classic utilitarian dashboard look",
    },
}


@dataclass
class ThemeConfig:
    colors: ThemeColors = field(default_factory=ThemeColors)
    colors_dark: ThemeColors | None = None
    logo: str = "images/logo.svg"
    favicon: str = "images/favicon.svg"
    font_family: str = (
        "'Inter', -apple-system, BlinkMacSystemFont, "
        "'Segoe UI', sans-serif"
    )
    font_family_headings: str = "'Sora', 'Inter', sans-serif"
    font_family_mono: str = "'IBM Plex Mono', 'Consolas', monospace"
    font_family_ipa: str = ""  # IPA fields; empty = the body font, which has IPA
    extra_css: list[str] = field(default_factory=list)  # site stylesheets from static/, e.g. css/site.css
    border_radius: str = "28px"
    hero_image: str = ""
    hero_images: list[str] = field(default_factory=list)
    hero_stats: list[str] = field(default_factory=list)
    style: str = "terra"
    module_intensity: dict[str, str] = field(default_factory=dict)
    term_color: str = ""
    term_weight: str = "600"
    hero_background: str = "weave"
    hero_motif: str = "weave"
    hero_divider: str = "weave"
    hero_height: str = ""
    page_badge: str = "weave"
    grain_pattern: str = "dots"
    templates: str = "v1"  # template set; see TEMPLATE_SETS
    # v2 only (ignored by v1); see terradoc.palette and meta REDESIGN-PLAN.md.
    palette: dict = field(default_factory=dict)  # role -> {color, material}; validated by check
    pack: str = "weave"  # motif pack: config/templates/v2/motifs/<pack>/ or bundled; "none"
    hero_credit: str = ""  # who took the hero photograph (shown under it)
    hero_alt: str = ""  # what the hero photograph shows, for screen readers
    hero_people: bool = True  # False: the hero shows a landscape or object (D25); recorded
    # now, used by later checks on withdrawn images
    # The v2 text face (vernacular, Portuguese and IPA alike): gentium (default), charis,
    # andika. Charis was D16's choice, but its tilde reads as a macron at text sizes.
    font_vernacular: str = "gentium"

    def to_dict(self) -> dict:
        result = {
            "colors": self.colors.to_dict(),
            "colors_dark": self.colors_dark.to_dict() if self.colors_dark else None,
            "logo": self.logo,
            "favicon": self.favicon,
            "font_family": self.font_family,
            "font_family_headings": self.font_family_headings,
            "font_family_mono": self.font_family_mono,
            "font_family_ipa": self.font_family_ipa,
            "extra_css": self.extra_css,
            "border_radius": self.border_radius,
            "hero_image": self.hero_image,
            "hero_images": self.hero_images,
            "hero_stats": self.hero_stats,
            "style": self.style,
            "module_intensity": self.module_intensity,
            "term_color": self.term_color,
            "term_weight": self.term_weight,
            "hero_background": self.hero_background,
            "hero_motif": self.hero_motif,
            "hero_divider": self.hero_divider,
            "hero_height": self.hero_height,
            "page_badge": self.page_badge,
            "grain_pattern": self.grain_pattern,
        }
        return result


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
    })
    default_locale: str = "pt"
    # ISO 639-3 / BCP 47 code of the people's language (bor, unk, mpu): `lang` on
    # vernacular text in v2, so browsers and screen readers do not read it as Portuguese.
    language_code: str = ""
    # The site's public address, e.g. "https://makurap.terradoc.org". The sitemap needs
    # absolute URLs; without base_url no sitemap is written.
    base_url: str = ""
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
        """terradoc's own templates for the active set (`theme.templates`)."""
        package = "terradoc.templates_v2" if self.theme.templates == "v2" else "terradoc.templates"
        return Path(str(importlib.resources.files(package)))

    @property
    def local_template_dir(self) -> Path:
        """The site's own templates for the active set: `config/templates/` for v1,
        `config/templates/v2/` for v2. May not exist."""
        if self.theme.templates == "v2":
            return self.config_dir / "templates" / "v2"
        return self.config_dir / "templates"

    @property
    def template_dirs(self) -> tuple[Path, ...]:
        """Where templates are looked up, site first: a site overrides one file
        (a page, a partial, a motif pack) and inherits the rest from terradoc."""
        local = self.local_template_dir
        if local.is_dir():
            return (local.resolve(), self.bundled_template_dir)
        return (self.bundled_template_dir,)

    def find_template(self, name: str) -> Path | None:
        """The first `name` along `template_dirs`, or None."""
        for d in self.template_dirs:
            if (d / name).is_file():
                return d / name
        return None

    @property
    def template_dir(self) -> Path:
        """Deprecated: the first template directory (kept for callers outside terradoc)."""
        return self.template_dirs[0]

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


# Template sets this version ships. v2 arrives with the redesign (meta REDESIGN-PLAN.md).
TEMPLATE_SETS = ("v1", "v2")

# Every key `theme:` may hold; anything else is reported by `terradoc check`.
THEME_KEYS = frozenset({
    "preset", "colors", "colors_dark", "module_intensity", "templates",
    "logo", "favicon", "font_family", "font_family_headings",
    "font_family_mono", "font_family_ipa", "border_radius", "hero_image", "style",
    "term_color", "term_weight",
    "hero_background", "hero_motif", "hero_divider",
    "hero_height", "page_badge", "grain_pattern",
    "hero_images", "hero_stats", "extra_css",
    # v2
    "palette", "pack", "hero_credit", "hero_alt", "hero_people", "font_vernacular",
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
                     "bib_file", "base_url", "language_code"):
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
            preset_name = theme_raw.get("preset", "terra")
            preset = THEME_PRESETS.get(preset_name, THEME_PRESETS["terra"])

            # Apply preset base values
            preset_colors = dict(preset["colors"])
            if "colors" in theme_raw:
                if not isinstance(theme_raw["colors"], dict):
                    raise ValueError(
                        "Invalid 'theme.colors' in terradoc.yaml: expected a YAML mapping/object"
                    )
                preset_colors.update(theme_raw["colors"])
            config.theme.colors = ThemeColors(**preset_colors)

            if "colors_dark" in theme_raw:
                if not isinstance(theme_raw["colors_dark"], dict):
                    raise ValueError(
                        "Invalid 'theme.colors_dark' in terradoc.yaml: expected a YAML mapping/object"
                    )
                config.theme.colors_dark = ThemeColors(**theme_raw["colors_dark"])

            config.theme.style = preset.get("style", "terra")
            for theme_key in (
                "font_family", "font_family_headings",
                "font_family_mono", "border_radius",
                "term_color", "term_weight",
            ):
                setattr(config.theme, theme_key, preset.get(theme_key, getattr(config.theme, theme_key)))

            # Module intensity: start from preset, merge YAML on top
            preset_intensity = dict(preset.get("module_intensity", {}))
            preset_intensity.update(theme_raw.get("module_intensity", {}))
            config.theme.module_intensity = preset_intensity

            # YAML overrides on top of preset
            for theme_key in (
                "logo", "favicon", "font_family", "font_family_headings",
                "font_family_mono", "font_family_ipa", "border_radius", "hero_image", "style",
                "term_color", "term_weight",
                "hero_background", "hero_motif", "hero_divider",
                "hero_height", "page_badge", "grain_pattern",
            ):
                if theme_key in theme_raw:
                    setattr(config.theme, theme_key, theme_raw[theme_key])

            # List overrides
            for list_key in ("hero_images", "hero_stats", "extra_css"):
                if list_key in theme_raw and isinstance(theme_raw[list_key], list):
                    setattr(config.theme, list_key, theme_raw[list_key])

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
