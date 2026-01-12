"""Python client and provider authoring framework for the Pragmatiks API.

Key exports:
    PragmaClient: Synchronous HTTP client for Pragmatiks API.
    AsyncPragmaClient: Asynchronous HTTP client for Pragmatiks API.
    Provider: Decorator for provider authoring.
    Resource: Base class for provider resources.
    Config: Base class for resource configuration.
    Outputs: Base class for resource outputs.
    Field: Field descriptor for configuration and output schemas.

Platform resource types:
    SecretConfig, SecretOutputs: Secret resource types.
    create_secret_config: Builder function for Secret resources.
"""

from pragma_sdk.auth import BearerAuth
from pragma_sdk.client import AsyncPragmaClient, PragmaClient
from pragma_sdk.models import (
    BuildResult,
    BuildStatus,
    Config,
    DeploymentResult,
    DeploymentStatus,
    EventType,
    Field,
    FieldReference,
    LifecycleState,
    Outputs,
    ProviderResponse,
    PushResult,
    Resource,
    ResourceReference,
    ResponseStatus,
    format_resource_id,
)
from pragma_sdk.platform import (
    SecretConfig,
    SecretOutputs,
    create_secret_config,
)
from pragma_sdk.provider import Provider


__all__ = [
    "AsyncPragmaClient",
    "BearerAuth",
    "BuildResult",
    "BuildStatus",
    "Config",
    "create_secret_config",
    "DeploymentResult",
    "DeploymentStatus",
    "EventType",
    "Field",
    "FieldReference",
    "format_resource_id",
    "LifecycleState",
    "Outputs",
    "PragmaClient",
    "Provider",
    "ProviderResponse",
    "PushResult",
    "Resource",
    "ResourceReference",
    "ResponseStatus",
    "SecretConfig",
    "SecretOutputs",
]
