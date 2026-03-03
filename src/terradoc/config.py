"""Configuration for terradoc projects."""

import importlib.resources
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ModuleConfig:
    enabled: bool = True


@dataclass
class ThemeColors:
    primary: str = "#3D352F"
    accent: str = "#B7522C"
    accent_muted: str = "#9A4427"
    bg: str = "#F9F6F2"
    bg_light: str = "#F5EDE8"
    bg_infobox: str = "#FAF8F5"
    border: str = "#E8E4DF"
    border_dark: str = "#C8B8A8"
    text: str = "#333333"
    text_muted: str = "#6B6B6B"
    highlight: str = "#fff59d"
    warning_bg: str = "#fff8e1"
    surface: str = "#FFFFFF"
    border_light: str = "#EEEEEE"
    text_secondary: str = "#555555"
    accent_light: str = "#FDF0EB"
    success: str = "#5B8C5A"
    error: str = "#CC0000"
    accent_ring: str = "rgba(183, 82, 44, 0.2)"

    def to_dict(self) -> dict:
        return {
            "primary": self.primary,
            "accent": self.accent,
            "accent_muted": self.accent_muted,
            "bg": self.bg,
            "bg_light": self.bg_light,
            "bg_infobox": self.bg_infobox,
            "border": self.border,
            "border_dark": self.border_dark,
            "text": self.text,
            "text_muted": self.text_muted,
            "highlight": self.highlight,
            "warning_bg": self.warning_bg,
            "surface": self.surface,
            "border_light": self.border_light,
            "text_secondary": self.text_secondary,
            "accent_light": self.accent_light,
            "success": self.success,
            "error": self.error,
            "accent_ring": self.accent_ring,
        }


@dataclass
class ThemeConfig:
    colors: ThemeColors = field(default_factory=ThemeColors)
    colors_dark: ThemeColors | None = None
    logo: str = "images/logo.svg"
    favicon: str = "images/favicon.svg"
    font_family: str = (
        "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
        "Oxygen, Ubuntu, sans-serif"
    )
    font_family_headings: str = ""
    font_family_mono: str = "'Lucida Sans Unicode', 'DejaVu Sans', monospace"
    border_radius: str = "4px"
    hero_image: str = ""

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
    def template_dir(self) -> Path:
        """Return the template directory.

        Uses local config/templates/ if it exists, otherwise falls back to
        the package's bundled templates.
        """
        local = self.config_dir / "templates"
        if local.exists():
            return local
        import importlib.resources
        return Path(str(importlib.resources.files("terradoc.templates")))

    def is_module_enabled(self, name: str) -> bool:
        mod = self.modules.get(name)
        return mod.enabled if mod else False

    def enabled_modules(self) -> list[dict]:
        """Return list of enabled module info dicts for template rendering."""
        module_order = ("dictionary", "encyclopedia", "fauna", "bibliography")
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
            if "colors" in theme_raw:
                config.theme.colors = ThemeColors(**theme_raw["colors"])
            if "colors_dark" in theme_raw:
                config.theme.colors_dark = ThemeColors(**theme_raw["colors_dark"])
            for theme_key in (
                "logo", "favicon", "font_family", "font_family_headings",
                "font_family_mono", "border_radius", "hero_image",
            ):
                if theme_key in theme_raw:
                    setattr(config.theme, theme_key, theme_raw[theme_key])

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
