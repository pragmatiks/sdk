"""CLI for extracting resource schemas from provider packages.

This module is designed to run during the Docker build process to extract
JSON schemas for all resources in a provider package. The schemas are output
as JSON to stdout, which is captured and stored with the build artifacts.

Usage:
    python -m pragma_sdk.provider.extract_schemas
    python -m pragma_sdk.provider.extract_schemas my_provider_package

If no package name is provided, it will attempt to detect the package from
pyproject.toml in the current directory.
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path
from typing import Any

from pragma_sdk.models import Config, Resource
from pragma_sdk.provider.discovery import discover_resources


def get_config_class(resource_class: type[Resource]) -> type[Config]:
    """Extract Config subclass from Resource's config field annotation.

    Args:
        resource_class: A Resource subclass.

    Returns:
        Config subclass type from the Resource's config field.

    Raises:
        ValueError: If Resource has no config field or wrong type.
    """
    annotations = resource_class.model_fields
    config_field = annotations.get("config")

    if config_field is None:
        raise ValueError(f"Resource {resource_class.__name__} has no config field")

    config_type = config_field.annotation

    if not isinstance(config_type, type) or not issubclass(config_type, Config):
        raise ValueError(f"Resource {resource_class.__name__} config field is not a Config subclass")

    return config_type


def detect_provider_package() -> str | None:
    """Detect provider package name from current directory.

    Reads pyproject.toml and checks in order:
    1. [tool.pragma] package - explicit module name
    2. [project] name - converted to underscores if ends with '-provider'

    Returns:
        Package name if found, None otherwise.
    """
    pyproject = Path("pyproject.toml")
    if not pyproject.exists():
        return None

    with open(pyproject, "rb") as f:
        data = tomllib.load(f)

    # Prefer explicit package name from [tool.pragma]
    pragma_package = data.get("tool", {}).get("pragma", {}).get("package")
    if pragma_package:
        return pragma_package

    # Fall back to project name conversion
    name = data.get("project", {}).get("name", "")
    if name and name.endswith("-provider"):
        return name.replace("-", "_")

    return None


def extract_schemas(package_name: str) -> list[dict[str, Any]]:
    """Extract JSON schemas for all resources in a provider package.

    Discovers all Resource classes in the package and extracts their
    config schemas using Pydantic's model_json_schema().

    Args:
        package_name: Python package name to scan (e.g., "postgres_provider").

    Returns:
        List of schema dictionaries with provider, resource, and config_schema keys.
    """
    schemas: list[dict[str, Any]] = []

    try:
        resources = discover_resources(package_name)
        for (provider, resource), cls in resources.items():
            try:
                config_type = get_config_class(cls)
                config_schema = config_type.model_json_schema()
                schemas.append(
                    {
                        "provider": provider,
                        "resource": resource,
                        "config_schema": config_schema,
                    }
                )
            except ValueError as e:
                print(f"Warning: Skipping {provider}/{resource}: {e}", file=sys.stderr)
                continue

    except Exception as e:
        print(f"Warning: Schema extraction failed: {e}", file=sys.stderr)

    return schemas


def main() -> None:
    """CLI entry point for schema extraction.

    If a package name is provided as an argument, use it. Otherwise,
    attempt to detect the package from pyproject.toml.

    Outputs JSON array of schemas to stdout. On failure, outputs
    an empty array.
    """
    if len(sys.argv) > 1:
        package_name = sys.argv[1]
    else:
        detected = detect_provider_package()
        if detected is None:
            print("Error: Could not detect package name. Provide it as an argument.", file=sys.stderr)
            print("[]")
            return
        package_name = detected

    schemas = extract_schemas(package_name)
    print(json.dumps(schemas, indent=2))


if __name__ == "__main__":
    main()
