# Pragma SDK Context

## Overview
`pragma-sdk` is the Python library for interacting with the Pragmatiks platform and building custom providers. It strictly enforces type safety using **Pydantic v2**.

## Architecture

*   **Core Clients**: `PragmaClient` (sync) and `AsyncPragmaClient` (async) in `client.py`.
*   **Provider Authoring**:
    *   `Provider` class for registration.
    *   `Resource` base class with lifecycle hooks (`on_create`, `on_update`, `on_delete`).
    *   `Config` and `Outputs` (Pydantic models).
*   **Models**: All API data models are defined in `models.py`.

## Development

### Key Commands
Run these from the `pragma-sdk` directory or via `task sdk:<command>` from the root.

*   `task test`: Run tests (including async tests).
*   `task format`: Format code with `ruff`.
*   `task check`: Run type checking (`ty`) and linting (`ruff`).

### Dependencies
*   **Runtime**: `httpx` (HTTP client), `pydantic` (validation).
*   **Dev**: `respx` (HTTP mocking), `pytest-asyncio`.

## Conventions
*   **Type Safety**: All public APIs must be fully typed. Use `py.typed` marker.
*   **Async First**: The core logic is async; sync wrappers are provided for convenience.
*   **Serialization**: Use Pydantic's `model_dump()` and `model_validate()` for JSON handling.
*   **Testing**: Use `respx` to mock API responses in tests.
