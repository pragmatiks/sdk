# CLAUDE.md

## Project

**pragma-sdk**: Python SDK for the Pragmatiks platform. Provides typed clients for API consumers and provider authors.

## Architecture

```
pragma-sdk/
├── src/pragma_sdk/
│   ├── client.py          # Main PragmaClient
│   ├── models/            # Pydantic models (shared with API)
│   └── resources/         # Resource-specific clients
└── tests/
```

## Dependencies

- `httpx` - Async HTTP client
- `pydantic` - Data validation and serialization
- `pyyaml` - YAML parsing for resource definitions

## Development

Always use `task` commands:

| Command | Purpose |
|---------|---------|
| `task test` | Run pytest |
| `task format` | Format with ruff |
| `task check` | Lint + type check |

## Patterns

- All API methods are async
- Pydantic models for request/response types
- httpx for HTTP calls with respx for testing
- Type hints on all public interfaces

## Testing

- Use respx to mock httpx calls
- Fixtures in `conftest.py`
- No real API calls in unit tests

## Publishing to PyPI

Package: `pragmatiks-sdk` on [PyPI](https://pypi.org/project/pragmatiks-sdk/)

**Versioning** (commitizen):
```bash
cz bump              # Bump version based on conventional commits
cz bump --patch      # Force patch bump
cz bump --minor      # Force minor bump
```

**Publishing**:
```bash
uv build             # Build wheel and sdist
uv publish           # Publish to PyPI (requires PYPI_TOKEN)
```

**Version files**: `pyproject.toml` (version field updated by commitizen)

**Tag format**: `v{version}` (e.g., `v0.15.1`)

## Related Repositories

- `../pragma-os/` - API server (defines the contracts)
- `../pragma-cli/` - CLI (consumes this SDK)
- `../pragma-providers/` - Providers (use SDK for API calls)
