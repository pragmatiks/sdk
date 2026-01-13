# Pragmatiks SDK

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/pragmatiks/sdk)
[![PyPI version](https://img.shields.io/pypi/v/pragmatiks-sdk.svg)](https://pypi.org/project/pragmatiks-sdk/)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

**[Documentation](https://docs.pragmatiks.io/sdk/overview)** | **[CLI](https://github.com/pragmatiks/cli)** | **[Providers](https://github.com/pragmatiks/providers)**

Build providers and interact with the Pragmatiks platform programmatically.

<!-- TODO: Add logo and demo GIF -->

## Quick Start

```python
from pragma_sdk import PragmaClient, Resource

with PragmaClient() as client:
    # Apply a resource
    client.apply_resource(
        Resource(
            provider="gcp",
            resource="storage",
            name="my-bucket",
            config={"location": "US", "storage_class": "STANDARD"}
        )
    )

    # Get resource status
    bucket = client.get_resource("gcp", "storage", "my-bucket")
    print(bucket.outputs)
```

## Installation

```bash
pip install pragmatiks-sdk
```

Or with uv:

```bash
uv add pragmatiks-sdk
```

## Features

- **HTTP Clients** - Sync and async clients for the Pragma API
- **Provider Authoring** - Build custom providers with type-safe Config and Outputs
- **Field References** - Reference outputs from other resources dynamically
- **Testing Harness** - Test provider lifecycle methods locally without deployment
- **Auto-discovery** - Automatic credential resolution from environment or config files

## Building Providers

Define resources with typed configuration and lifecycle methods:

```python
from pragma_sdk import Provider, Resource, Config, Outputs, Field

gcp = Provider(name="gcp")

class BucketConfig(Config):
    location: Field[str]
    storage_class: Field[str] = "STANDARD"

class BucketOutputs(Outputs):
    url: str
    created_at: str

@gcp.resource("storage")
class Bucket(Resource[BucketConfig, BucketOutputs]):
    async def on_create(self) -> BucketOutputs:
        # Provision the bucket
        return BucketOutputs(url=f"gs://{self.name}", created_at="...")

    async def on_update(self, previous_config: BucketConfig) -> BucketOutputs:
        # Handle config changes
        return self.outputs

    async def on_delete(self) -> None:
        # Clean up
        pass
```

## Field References

Reference outputs from other resources:

```python
from pragma_sdk import FieldReference

config = AppConfig(
    database_url=FieldReference(
        provider="postgres",
        resource="database",
        name="my-db",
        field="outputs.connection_url"
    )
)
```

## Testing Providers

Test lifecycle methods locally with `ProviderHarness`:

```python
from pragma_sdk.provider import ProviderHarness

async def test_bucket_creation():
    harness = ProviderHarness()

    result = await harness.invoke_create(
        Bucket,
        name="test-bucket",
        config=BucketConfig(location="US")
    )

    assert result.success
    assert "gs://test-bucket" in result.outputs.url
```

## Authentication

Credentials are discovered automatically:

1. Explicit `auth_token` parameter
2. Environment variable: `PRAGMA_AUTH_TOKEN`
3. Credentials file: `~/.config/pragma/credentials`

```python
# Auto-discover credentials
client = PragmaClient()

# Explicit token
client = PragmaClient(auth_token="sk_...")

# Require authentication (fail if no token)
client = PragmaClient(require_auth=True)
```

## API Reference

### HTTP Client Methods

| Method | Description |
|--------|-------------|
| `list_resources(provider, resource, tags)` | List resources with optional filters |
| `get_resource(provider, resource, name)` | Get a specific resource |
| `apply_resource(resource)` | Create or update a resource |
| `delete_resource(provider, resource, name)` | Delete a resource |
| `is_healthy()` | Check API health |

### Provider Classes

| Class | Description |
|-------|-------------|
| `Provider(name)` | Provider namespace with `@provider.resource()` decorator |
| `Resource[ConfigT, OutputsT]` | Base class with `on_create`, `on_update`, `on_delete` |
| `Config` | Base class for resource configuration (Pydantic model) |
| `Outputs` | Base class for resource outputs (Pydantic model) |
| `Field[T]` | Type alias for `T | FieldReference` |
| `ProviderHarness` | Local testing harness |

## Development

```bash
# Run tests
task sdk:test

# Format code
task sdk:format

# Type check and lint
task sdk:check
```

## License

MIT
