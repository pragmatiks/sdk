"""Pragma SDK data models matching API resource model."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel
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
        build_id: Unique identifier for the build.
        job_name: Name of the Kubernetes build job.
        status: Initial build status (typically pending).
        message: Status message from the API.
    """

    build_id: str
    job_name: str
    status: BuildStatus
    message: str


class BuildResult(BaseModel):
    """Result of a build status query.

    Attributes:
        job_name: Name of the Kubernetes Job.
        status: Current build status.
        image: Full image reference (set on success).
        error_message: Error message (set on failure).
    """

    job_name: str
    status: BuildStatus
    image: str | None = None
    error_message: str | None = None


class DeploymentResult(BaseModel):
    """Result of a deployment status query.

    Attributes:
        deployment_name: Name of the Kubernetes Deployment.
        status: Current deployment status.
        available_replicas: Number of available replicas.
        ready_replicas: Number of ready replicas.
        message: Status message or error details.
    """

    deployment_name: str
    status: DeploymentStatus
    available_replicas: int = 0
    ready_replicas: int = 0
    message: str | None = None


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
