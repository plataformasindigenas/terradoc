"""Terradoc — Reusable engine for indigenous documentation platforms."""

__version__ = "0.1.0"

from terradoc.config import TerradocConfig, load_config

__all__ = ["TerradocConfig", "load_config", "__version__"]
