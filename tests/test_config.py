"""Tests for credential discovery and configuration management."""

from __future__ import annotations

from pathlib import Path

import pytest

from pragma_sdk.config import (
    get_credentials_file_path,
    get_current_context_from_config,
    get_token_for_context,
    load_credentials,
)


def test_get_credentials_file_path_uses_xdg_config_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """XDG_CONFIG_HOME environment variable determines credentials path."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = get_credentials_file_path()
    assert path == tmp_path / "pragma" / "credentials"


def test_get_credentials_file_path_falls_back_to_home(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without XDG_CONFIG_HOME, falls back to ~/.config/pragma/credentials."""
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    path = get_credentials_file_path()
    assert str(path).endswith(".config/pragma/credentials")


def test_load_credentials_returns_none_when_file_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns None when credentials file doesn't exist."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    token = load_credentials("default")
    assert token is None


def test_load_credentials_parses_key_value_format(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Loads token from credentials file for specified context."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    creds_file = tmp_path / "pragma" / "credentials"
    creds_file.parent.mkdir(parents=True)
    creds_file.write_text("default=token1\nproduction=token2\n")

    assert load_credentials("default") == "token1"
    assert load_credentials("production") == "token2"
    assert load_credentials("nonexistent") is None


def test_get_current_context_from_config_reads_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reads current_context from CLI config.yaml."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    config_file = tmp_path / "pragma" / "config.yaml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("current_context: production\n")

    context = get_current_context_from_config()
    assert context == "production"


def test_get_current_context_from_config_returns_none_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Returns None when config file doesn't exist."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    context = get_current_context_from_config()
    assert context is None


def test_get_token_for_context_env_var_has_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    """Context-specific environment variable has highest priority."""
    monkeypatch.setenv("PRAGMA_AUTH_TOKEN_PRODUCTION", "context-token")
    monkeypatch.setenv("PRAGMA_AUTH_TOKEN", "generic-token")

    token = get_token_for_context("production")
    assert token == "context-token"


def test_get_token_for_context_generic_env_var_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Generic environment variable is used when context-specific not set."""
    monkeypatch.delenv("PRAGMA_AUTH_TOKEN_PRODUCTION", raising=False)
    monkeypatch.setenv("PRAGMA_AUTH_TOKEN", "generic-token")

    token = get_token_for_context("production")
    assert token == "generic-token"


def test_get_token_for_context_file_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Credentials file is used when env vars not set."""
    monkeypatch.delenv("PRAGMA_AUTH_TOKEN_PRODUCTION", raising=False)
    monkeypatch.delenv("PRAGMA_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    creds_file = tmp_path / "pragma" / "credentials"
    creds_file.parent.mkdir(parents=True)
    creds_file.write_text("production=file-token\n")

    token = get_token_for_context("production")
    assert token == "file-token"


def test_get_token_for_context_determines_context_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Determines context from PRAGMA_CONTEXT environment variable."""
    monkeypatch.setenv("PRAGMA_CONTEXT", "staging")
    monkeypatch.setenv("PRAGMA_AUTH_TOKEN_STAGING", "staging-token")

    token = get_token_for_context()
    assert token == "staging-token"


def test_get_token_for_context_returns_none_when_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Returns None when no token found anywhere."""
    monkeypatch.delenv("PRAGMA_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("PRAGMA_CONTEXT", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", "/nonexistent")

    token = get_token_for_context("unknown")
    assert token is None
