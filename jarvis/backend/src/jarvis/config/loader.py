"""Load and validate Jarvis configuration from YAML files."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from jarvis.config.settings import Settings

CONFIG_ENV = "JARVIS_CONFIG"
OVERRIDE_ENV = "JARVIS_CONFIG_OVERRIDE"


class ConfigError(Exception):
    """The configuration is missing, unreadable or invalid. Jarvis must not start."""


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read config file {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"config file {path} is not valid YAML: {exc}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError(f"config file {path} must contain a mapping at the top level")
    return raw


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def load_settings(path: Path, override_path: Path | None = None) -> Settings:
    """Read ``path``, apply the optional override file on top, and validate."""
    data = _read_yaml(path)
    if override_path is not None:
        data = _deep_merge(data, _read_yaml(override_path))
    try:
        return Settings.model_validate(data)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or '<root>'}: {error['msg']}"
            for error in exc.errors()
        )
        raise ConfigError(f"invalid configuration: {details}") from exc


def load_settings_from_env(environ: Mapping[str, str] | None = None) -> Settings:
    """Load settings from the files named by JARVIS_CONFIG / JARVIS_CONFIG_OVERRIDE."""
    env = os.environ if environ is None else environ
    config_path = env.get(CONFIG_ENV)
    if not config_path:
        raise ConfigError(f"environment variable {CONFIG_ENV} is not set")
    override = env.get(OVERRIDE_ENV)
    return load_settings(Path(config_path), Path(override) if override else None)
