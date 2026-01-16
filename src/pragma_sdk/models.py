"""Pragma SDK data models matching API resource model."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, PrivateAttr
from pydantic import Field as PydanticField


class LifecycleState(StrEnum):
    """Resource lifecycle states: DRAFT, PENDING, PROCESSING, READY, FAILED."""

    DRAFT = "draft"
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class BuildStatus(StrEnum):
    """Status of a BuildKit build job."""

    PENDING = "pending"
    BUILDING = "building"
    SUCCESS = "success"
    FAILED = "failed"


class DeploymentStatus(StrEnum):
    """Status of a provider deployment."""

    PENDING = "pending"
    PROGRESSING = "progressing"
    AVAILABLE = "available"
    FAILED = "failed"


class PushResult(BaseModel):
    """Result from pushing provider code to start a build.

    Attributes:
        version: CalVer version for the build (YYYYMMDD.HHMMSS).
        status: Initial build status (typically pending).
        message: Status message from the API.
    """

    version: str
    status: BuildStatus
    message: str


class BuildInfo(BaseModel):
    """Build information for a provider version.

    Attributes:
        provider_id: Provider identifier.
        version: CalVer version string (YYYYMMDD.HHMMSS).
        status: Current build status.
        error_message: Error message (set on failure).
        created_at: When the build was created.
    """

    provider_id: str
    version: str
    status: BuildStatus
    error_message: str | None = None
    created_at: datetime


class DeploymentResult(BaseModel):
    """Result of a deployment operation (deploy/rollback).

    Contains internal K8s details needed for deployment commands.

    Attributes:
        deployment_name: Name of the Kubernetes Deployment.
        status: Current deployment status.
        available_replicas: Number of available replicas.
        ready_replicas: Number of ready replicas.
        version: Deployed version (CalVer format YYYYMMDD.HHMMSS).
        image: Container image reference (internal, may not be exposed).
        updated_at: Last update timestamp from deployment conditions.
        message: Status message or error details.
    """

    deployment_name: str
    status: DeploymentStatus
    available_replicas: int = 0
    ready_replicas: int = 0
    version: str | None = None
    image: str | None = None
    updated_at: datetime | None = None
    message: str | None = None


class ProviderStatus(BaseModel):
    """User-facing provider deployment status.

    Minimal representation without internal K8s details like replica
    counts, deployment names, or container images.

    Attributes:
        status: Current deployment status.
        version: CalVer version string of deployed build.
        updated_at: Last update timestamp.
        healthy: Whether the provider is healthy (available with ready replicas).
    """

    status: DeploymentStatus
    version: str | None = None
    updated_at: datetime | None = None
    healthy: bool = False


class ProviderInfo(BaseModel):
    """Provider information from API list endpoint.

    Attributes:
        provider_id: Unique identifier for the provider.
        current_version: CalVer of currently deployed build (None if never deployed).
        deployment_status: Current deployment status (None if not deployed).
        updated_at: Timestamp of last provider update (typically last deployment).
    """

    provider_id: str
    current_version: str | None = None
    deployment_status: DeploymentStatus | None = None
    updated_at: datetime | None = None


class ProviderDeleteResult(BaseModel):
    """User-facing result of a provider delete operation.

    Minimal representation without internal infrastructure details.

    Attributes:
        provider_id: Provider that was deleted.
        deployment_deleted: Whether the running deployment was removed.
        resources_deleted: Number of resources deleted (if cascade was used).
    """

    provider_id: str
    deployment_deleted: bool = False
    resources_deleted: int = 0


class UserInfo(BaseModel):
    """Current user information from authentication.

    Attributes:
        user_id: Unique identifier from Clerk authentication.
        email: User's primary email address (None if not set).
        organization_id: Clerk organization identifier.
        organization_name: Name of the user's organization (None if not available).
    """

    user_id: str
    email: str | None = None
    organization_id: str
    organization_name: str | None = None


class EventType(StrEnum):
    """Resource lifecycle event type: CREATE, UPDATE, or DELETE."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class ResponseStatus(StrEnum):
    """Provider response status: SUCCESS or FAILURE."""

    SUCCESS = "success"
    FAILURE = "failure"


def format_resource_id(provider: str, resource: str, name: str) -> str:
    """Format a unique resource ID.

    Returns:
        Resource ID as `resource:{provider}_{resource}_{name}`.
    """
    return f"resource:{provider}_{resource}_{name}"


class ResourceReference(BaseModel):
    """Reference to another resource for dependency tracking."""

    provider: str
    resource: str
    name: str

    @property
    def id(self) -> str:
        """Unique resource ID for the referenced resource."""
        return format_resource_id(self.provider, self.resource, self.name)


class FieldReference(ResourceReference):
    """Reference to a specific output field of another resource."""

    field: str


def is_dependency_marker(value: Any) -> bool:
    """Check if a value is a serialized Dependency marker.

    When Dependency[T] is serialized (e.g., sent via API), it becomes a dict
    with __dependency__=True and provider/resource/name keys. This function
    detects such markers regardless of whether they've been resolved.

    Args:
        value: Any value to check.

    Returns:
        True if value is a dict with the required dependency keys and __dependency__=True.
    """
    if not isinstance(value, dict):
        return False
    required = {"__dependency__", "provider", "resource", "name"}
    return required.issubset(value.keys()) and value.get("__dependency__") is True


class Dependency[ResourceT: "Resource"](BaseModel):
    """Typed dependency on another resource for whole-instance access.

    Use this when you need access to the full resource object (config, outputs,
    methods) rather than just a single field value. Call resolve() in lifecycle
    handlers to get the typed resource instance.

    Example:
        ```python
        class AppConfig(Config):
            database: Dependency[DatabaseResource]

        async def on_create(self):
            db = await self.config.database.resolve()
            print(db.outputs.connection_url)
        ```
    """

    model_config = {"populate_by_name": True}

    dependency_marker: bool = PydanticField(
        default=True, alias="__dependency__", serialization_alias="__dependency__"
    )
    provider: str
    resource: str
    name: str

    _resolved: ResourceT | None = PrivateAttr(default=None)

    @property
    def id(self) -> str:
        """Unique resource ID for the referenced resource."""
        return format_resource_id(self.provider, self.resource, self.name)

    async def resolve(self) -> ResourceT:
        """Get the resolved resource instance.

        The runtime injects resolved dependencies before calling lifecycle
        handlers. This method returns that pre-resolved instance.

        Returns:
            The typed resource with access to its config, outputs, and methods.

        Raises:
            RuntimeError: If the dependency was not resolved by the runtime.
                This happens when the dependent resource is not yet READY.
        """
        if self._resolved is not None:
            return self._resolved
        raise RuntimeError(
            f"Dependency '{self.id}' not resolved. "
            "The dependent resource may not be READY yet."
        )


type Field[T] = T | FieldReference
"""Config field that accepts a direct value or a FieldReference."""


class ProviderResponse(BaseModel):
    """Provider response reporting the outcome of a lifecycle event."""

    event_id: str
    event_type: EventType
    resource_id: str
    tenant_id: str
    status: ResponseStatus
    outputs: dict | None = None
    error: str | None = None
    timestamp: datetime


class ResourceDefinition(BaseModel):
    """Metadata about a registered resource type."""

    provider: str
    resource: str
    schema_: dict[str, Any] | None = PydanticField(default=None, alias="schema")
    description: str | None = None
    tags: list[str] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def id(self) -> str:
        """Unique resource definition ID: resource_definition:{provider}_{resource}."""
        return f"resource_definition:{self.provider}_{self.resource}"


class Config(BaseModel):
    """Base class for resource configuration schemas."""

    model_config = {"extra": "forbid"}


class Outputs(BaseModel):
    """Base class for resource outputs produced by lifecycle handlers."""

    model_config = {"extra": "forbid"}


class Resource[ConfigT: Config, OutputsT: Outputs](BaseModel):
    """Base class for provider-managed resources with lifecycle handlers.

    Lifecycle handlers (on_create, on_update, on_delete) must be idempotent.
    Events may be redelivered if the runtime crashes after processing but
    before acknowledging the message. Design handlers to produce the same
    result when called multiple times with the same input.
    """

    provider: ClassVar[str]
    resource: ClassVar[str]

    name: str

    config: ConfigT
    dependencies: list[ResourceReference] = PydanticField(default_factory=list)

    outputs: OutputsT | None = None
    error: str | None = None

    lifecycle_state: LifecycleState = LifecycleState.DRAFT

    tags: list[str] | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def id(self) -> str:
        """Unique resource ID: resource:{provider}_{resource}_{name}."""
        return format_resource_id(self.provider, self.resource, self.name)

    async def on_create(self) -> OutputsT:
        """Handle resource creation."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement on_create()")

    async def on_update(self, previous_config: ConfigT) -> OutputsT:
        """Handle resource update with access to the previous configuration."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement on_update()")

    async def on_delete(self) -> None:
        """Handle resource deletion."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement on_delete()")
