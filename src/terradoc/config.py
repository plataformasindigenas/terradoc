"""Configuration for terradoc projects."""

import importlib.resources
from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml


@dataclass
class ModuleConfig:
    enabled: bool = True


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
    border_radius: str = "28px"
    hero_image: str = ""
    hero_images: list[str] = field(default_factory=list)
    hero_stats: list[str] = field(default_factory=list)
    style: str = "terra"
    module_intensity: dict[str, str] = field(default_factory=dict)
    term_color: str = ""
    term_weight: str = "600"

    def to_dict(self) -> dict:
        result = {
            "colors": self.colors.to_dict(),
            "colors_dark": self.colors_dark.to_dict() if self.colors_dark else None,
            "logo": self.logo,
            "favicon": self.favicon,
            "font_family": self.font_family,
            "font_family_headings": self.font_family_headings,
            "font_family_mono": self.font_family_mono,
            "border_radius": self.border_radius,
            "hero_image": self.hero_image,
            "hero_images": self.hero_images,
            "hero_stats": self.hero_stats,
            "style": self.style,
            "module_intensity": self.module_intensity,
            "term_color": self.term_color,
            "term_weight": self.term_weight,
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
    locale_labels: dict[str, str] = field(default_factory=lambda: {
        "pt": "Português",
        "en": "English",
    })
    default_locale: str = "pt"
    featured_article_id: str = ""
    bib_file: str = "references.bib"
    theme: ThemeConfig = field(default_factory=ThemeConfig)

    modules: dict[str, ModuleConfig] = field(default_factory=lambda: {
        "dictionary": ModuleConfig(),
        "fauna": ModuleConfig(),
        "encyclopedia": ModuleConfig(),
        "bibliography": ModuleConfig(),
        "recordings": ModuleConfig(),
    })
    module_labels: dict[str, str] = field(default_factory=lambda: {
        "dictionary": "Dictionary",
        "encyclopedia": "Encyclopedia",
        "fauna": "Fauna",
        "bibliography": "Bibliography",
    })

    # Paths (set after loading)
    base_dir: Path = field(default_factory=Path.cwd)

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def docs_dir(self) -> Path:
        return self.base_dir / "docs"

    @property
    def config_dir(self) -> Path:
        return self.base_dir / "config"

    @property
    def locales_dir(self) -> Path:
        return self.base_dir / "locales"

    @property
    def bundled_template_dir(self) -> Path:
        """Return the bundled template directory from the package."""
        return Path(str(importlib.resources.files("terradoc.templates")))

    @property
    def template_dir(self) -> Path:
        """Return the template directory.

        Uses local config/templates/ if it exists, otherwise falls back to
        the package's bundled templates.
        """
        local = self.config_dir / "templates"
        if local.exists():
            return local
        return self.bundled_template_dir

    def is_module_enabled(self, name: str) -> bool:
        mod = self.modules.get(name)
        return mod.enabled if mod else False

    def enabled_modules(self) -> list[dict]:
        """Return list of enabled module info dicts for template rendering."""
        module_order = ("dictionary", "encyclopedia", "fauna", "bibliography", "recordings")
        return [
            {"slug": name, "name": self.module_label(name)}
            for name in module_order
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
        }
        ctx.update({
            f"{slug}_label": self.module_label(slug) for slug in self.modules
        })
        return ctx


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
                     "bib_file"):
            if key in raw:
                setattr(config, key, raw[key])

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
                "font_family_mono", "border_radius", "hero_image", "style",
                "term_color", "term_weight",
            ):
                if theme_key in theme_raw:
                    setattr(config.theme, theme_key, theme_raw[theme_key])

            # List overrides
            for list_key in ("hero_images", "hero_stats"):
                if list_key in theme_raw and isinstance(theme_raw[list_key], list):
                    setattr(config.theme, list_key, theme_raw[list_key])

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
