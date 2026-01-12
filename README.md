# Pragmatiks SDK

Python SDK for building providers and interacting with the Pragmatiks platform.

## Installation

```bash
uv add pragmatiks-sdk
```

## Quick Start

### HTTP Clients

Interact with the Pragma API using sync or async clients:

```python
from pragma_sdk import PragmaClient, AsyncPragmaClient, Resource

# Synchronous client
with PragmaClient() as client:
    resources = client.list_resources(provider="postgres")
    db = client.get_resource("postgres", "database", "my-db")

    resource = client.apply_resource(
        Resource(
            provider="postgres",
            resource="database",
            name="my-db",
            config={"name": "analytics", "size_gb": 100}
        )
    )

    client.delete_resource("postgres", "database", "my-db")

# Asynchronous client
async with AsyncPragmaClient() as client:
    resources = await client.list_resources(provider="postgres")
    db = await client.get_resource("postgres", "database", "my-db")
    await client.delete_resource("postgres", "database", "my-db")
```

## Provider Authoring

Build providers that manage infrastructure resources with type-safe configuration and outputs.

### Basic Provider

```python
from pragma_sdk import Provider, Resource, Config, Outputs, Field

# Create a provider namespace
postgres = Provider(name="postgres")

# Define configuration schema
class DatabaseConfig(Config):
    db_name: Field[str]
    size_gb: Field[int] = 10
    owner: Field[str] = "postgres"

# Define output schema
class DatabaseOutputs(Outputs):
    connection_url: str
    created_at: str

# Implement resource lifecycle
@postgres.resource("database")
class Database(Resource[DatabaseConfig, DatabaseOutputs]):
    async def on_create(self) -> DatabaseOutputs:
        # Create the database
        return DatabaseOutputs(
            connection_url=f"postgres://localhost/{self.config.db_name}",
            created_at="2025-01-01T00:00:00Z"
        )

    async def on_update(self, previous_config: DatabaseConfig) -> DatabaseOutputs:
        # Update the database if config changed
        if previous_config.size_gb != self.config.size_gb:
            # Resize database
            pass
        return self.outputs  # type: ignore

    async def on_delete(self) -> None:
        # Delete the database
        pass
```

### Resource Lifecycle

Resources follow a 5-state lifecycle:

```
DRAFT → PENDING (commit)
PENDING → PROCESSING (provider picks up)
PROCESSING → READY (success) | FAILED (error)
READY/FAILED → PENDING (update/retry)
READY/FAILED → DRAFT (uncommit)
```

### Field References

Reference outputs from other resources:

```python
from pragma_sdk import FieldReference

app_config = AppConfig(
    name="my-app",
    # Reference database URL instead of hardcoding
    database_url=FieldReference(
        provider="postgres",
        resource="database",
        name="my-db",
        field="outputs.connection_url"
    )
)
```

## Testing Providers

Use `ProviderHarness` to test lifecycle methods locally without platform infrastructure:

```python
from pragma_sdk.provider import ProviderHarness

async def test_database_creation():
    harness = ProviderHarness()

    # Test on_create
    result = await harness.invoke_create(
        Database,
        name="test-db",
        config=DatabaseConfig(db_name="test-db", size_gb=10)
    )

    assert result.success
    assert result.outputs.connection_url == "postgres://localhost/test-db"

    # Test on_update
    result = await harness.invoke_update(
        Database,
        name="test-db",
        config=DatabaseConfig(db_name="test-db", size_gb=20),
        previous_config=DatabaseConfig(db_name="test-db", size_gb=10),
        current_outputs=result.outputs
    )

    assert result.success

    # Test on_delete
    result = await harness.invoke_delete(
        Database,
        name="test-db",
        config=DatabaseConfig(db_name="test-db")
    )

    assert result.success
```

## Authentication

Credentials are discovered automatically in this order:

1. Explicit `auth_token` parameter
2. Context-specific environment variable: `PRAGMA_AUTH_TOKEN_<CONTEXT>`
3. Generic environment variable: `PRAGMA_AUTH_TOKEN`
4. Credentials file: `~/.config/pragma/credentials`

```python
# Auto-discover from environment or credentials file
client = PragmaClient()

# Explicit token
client = PragmaClient(auth_token="eyJhbGc...")

# Specific context
client = PragmaClient(context="production")

# Require authentication (fail if no token found)
client = PragmaClient(context="production", require_auth=True)
```

### Environment Variables

```bash
# Generic token (all contexts)
export PRAGMA_AUTH_TOKEN=sk_test_...

# Context-specific token
export PRAGMA_AUTH_TOKEN_PRODUCTION=sk_prod_...
export PRAGMA_CONTEXT=production
```

## API Reference

### HTTP Clients

Both `PragmaClient` and `AsyncPragmaClient` provide:

- `is_healthy()` - Check API health
- `list_resources(provider, resource, tags)` - List resources
- `get_resource(provider, resource, name)` - Get a resource
- `apply_resource(resource)` - Create or update a resource
- `delete_resource(provider, resource, name)` - Delete a resource
- `register_resource(provider, resource, schema, description, tags)` - Register a resource type
- `unregister_resource(provider, resource)` - Unregister a resource type

### Provider Classes

- `Provider(name)` - Provider namespace
  - `@provider.resource(name)` - Decorator to register resources

- `Resource[ConfigT, OutputsT]` - Base class for resources
  - `on_create()` - Handle resource creation
  - `on_update(previous_config)` - Handle resource updates
  - `on_delete()` - Handle resource deletion

- `Config` - Base class for resource configuration
- `Outputs` - Base class for resource outputs
- `Field[T]` - Type alias for `T | FieldReference`

### Testing

- `ProviderHarness` - Local test harness
  - `invoke_create(resource_class, name, config, tags)` - Test on_create
  - `invoke_update(resource_class, name, config, previous_config, current_outputs, tags)` - Test on_update
  - `invoke_delete(resource_class, name, config, current_outputs, tags)` - Test on_delete
  - `events` - List of lifecycle events
  - `results` - List of lifecycle results
  - `clear()` - Clear event and result history

## Development

```bash
# Run tests
pytest

# Format code
ruff format

# Lint
ruff check
```

