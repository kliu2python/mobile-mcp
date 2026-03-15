from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "appium_profiles.yaml"
ENV_CONFIG_PATH = "APPIUM_MCP_CONFIG"

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


class AppiumConfigError(ValueError):
    """Raised when Appium MCP configuration is invalid."""


def _load_config_file(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise AppiumConfigError(
            f"Config file not found: {config_path}. "
            "Create one based on appium_profiles.example.yaml."
        )

    raw = config_path.read_text(encoding="utf-8")

    try:
        if config_path.suffix.lower() == ".json":
            data = json.loads(raw)
        else:
            data = yaml.safe_load(raw)
    except Exception as exc:  # parse errors from json/yaml
        raise AppiumConfigError(f"Failed to parse config file '{config_path}': {exc}") from exc

    if not isinstance(data, dict):
        raise AppiumConfigError("Config root must be a JSON/YAML object")

    return data


def _get_default_path() -> Path:
    configured_path = os.getenv(ENV_CONFIG_PATH)
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return DEFAULT_CONFIG_PATH


def _resolve_placeholders(value: Any) -> Any:
    if isinstance(value, str):
        return _ENV_VAR_PATTERN.sub(lambda m: os.getenv(m.group(1), m.group(0)), value)
    if isinstance(value, dict):
        return {k: _resolve_placeholders(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_placeholders(v) for v in value]
    return value


def _merge_profile(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    merged = dict(parent)
    merged.update({k: v for k, v in child.items() if k != "capabilities"})

    parent_caps = parent.get("capabilities") if isinstance(parent.get("capabilities"), dict) else {}
    child_caps = child.get("capabilities") if isinstance(child.get("capabilities"), dict) else {}
    merged["capabilities"] = {**parent_caps, **child_caps}
    return merged


def _normalize_profiles(raw_profiles: dict[str, Any]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}

    def resolve(name: str, stack: set[str]) -> dict[str, Any]:
        if name in normalized:
            return normalized[name]
        if name in stack:
            chain = " -> ".join([*stack, name])
            raise AppiumConfigError(f"Circular profile inheritance detected: {chain}")

        value = raw_profiles.get(name)
        if not isinstance(value, dict):
            raise AppiumConfigError(f"Profile '{name}' must be an object")

        stack.add(name)
        parent_name = value.get("extends")

        if parent_name is not None and not isinstance(parent_name, str):
            raise AppiumConfigError(f"Profile '{name}' field 'extends' must be a string")

        if parent_name:
            if parent_name not in raw_profiles:
                raise AppiumConfigError(
                    f"Profile '{name}' extends unknown profile '{parent_name}'"
                )
            parent = resolve(parent_name, stack)
            merged = _merge_profile(parent, value)
        else:
            merged = dict(value)

        stack.remove(name)

        platform = merged.get("platform")
        server_url = merged.get("server_url")
        capabilities = merged.get("capabilities")

        if not isinstance(platform, str) or not platform:
            raise AppiumConfigError(f"Profile '{name}' missing 'platform'")
        if not isinstance(server_url, str) or not server_url:
            raise AppiumConfigError(f"Profile '{name}' missing 'server_url'")
        if not isinstance(capabilities, dict):
            raise AppiumConfigError(f"Profile '{name}' missing dict 'capabilities'")

        normalized[name] = {
            "platform": platform,
            "server_url": server_url,
            "capabilities": _resolve_placeholders(capabilities),
        }
        return normalized[name]

    for profile_name in raw_profiles:
        resolve(profile_name, set())

    return normalized


def load_profiles(config_path: str | None = None) -> dict[str, dict[str, Any]]:
    path = Path(config_path).expanduser().resolve() if config_path else _get_default_path()
    data = _load_config_file(path)
    profiles = data.get("profiles")

    if not isinstance(profiles, dict) or not profiles:
        raise AppiumConfigError("Config must include non-empty 'profiles' mapping")

    return _normalize_profiles(profiles)


def get_profile(profile_name: str, config_path: str | None = None) -> dict[str, Any]:
    profiles = load_profiles(config_path=config_path)

    if profile_name not in profiles:
        available = ", ".join(sorted(profiles.keys()))
        raise AppiumConfigError(
            f"Unknown profile '{profile_name}'. Available profiles: {available}"
        )

    return profiles[profile_name]
