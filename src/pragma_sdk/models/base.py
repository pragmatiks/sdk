"""Core base classes for resource configuration and lifecycle."""

from __future__ import annotations

import typing
from collections.abc import AsyncIterator
from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel
from pydantic import Field as PydanticField

from pragma_sdk.context import apply_resource, get_current_resource_owner, wait_for_resource_state
from pragma_sdk.models.references import OwnerReference, ResourceReference, format_resource_id
from pragma_sdk.types import HealthStatus, LifecycleState, LogEntry


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
    owner_references: list[OwnerReference] = PydanticField(default_factory=list)
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

    async def logs(
        self,
        since: datetime | None = None,
        tail: int = 100,
    ) -> AsyncIterator[LogEntry]:
        """Override to provide logs for this resource.

        Args:
            since: Only return logs after this timestamp.
            tail: Maximum number of log entries to return.

        Yields:
            Log entries for this resource.

        Raises:
            NotImplementedError: Subclass must implement this method.
        """
        raise NotImplementedError("Subclass must implement logs()")
        yield  # For type checker

    async def health(self) -> HealthStatus:
        """Override to provide health status for this resource.

        Returns:
            Health status. Default implementation returns healthy.
        """
        return HealthStatus(status="healthy")

    def set_owner(self, owner: Resource) -> Resource:
        """Set this resource's owner for lifecycle management.

        Establishes an ownership relationship where the owner resource controls
        this resource's lifecycle. When the owner is deleted, owned resources
        can be automatically cleaned up via cascading deletes.

        Args:
            owner: Parent resource that will own this resource.

        Returns:
            Self for method chaining.
        """
        ref = OwnerReference(
            provider=owner.provider,
            resource=owner.resource,
            name=owner.name,
        )
        if ref not in self.owner_references:
            self.owner_references.append(ref)
        return self

    async def apply(self) -> Resource[ConfigT, OutputsT]:
        """Apply this resource through the API.

        Sends the resource to the API for creation or update. The API will
        validate, persist, and emit lifecycle events for provider processing.
        The resource's lifecycle_state will be set to PENDING by the API.

        Call this from within provider lifecycle handlers to create subresources.
        The owner is automatically set from the current runtime context (the
        resource whose lifecycle handler is executing). After apply(), call
        wait_ready() to wait for the resource to be processed.

        Returns:
            Self for method chaining.

        Example:
            ```python
            async def on_create(self):
                db = DatabaseResource(name=f"{self.name}-db", config=DbConfig(...))
                await db.apply()  # Owner automatically set from context
                await db.wait_ready(timeout=120.0)
                return AppOutputs(db_url=db.outputs.connection_url)
            ```
        """
        current_owner = get_current_resource_owner()
        if current_owner is not None and current_owner not in self.owner_references:
            self.owner_references.append(current_owner)

        resource_data = {
            "provider": self.provider,
            "resource": self.resource,
            "name": self.name,
            "config": self.config.model_dump(),
            "owner_references": [ref.model_dump() for ref in self.owner_references],
        }
        if self.tags:
            resource_data["tags"] = self.tags

        await apply_resource(resource_data)
        self.lifecycle_state = LifecycleState.PENDING
        return self

    async def wait_ready(self, timeout: float = 60.0) -> Resource[ConfigT, OutputsT]:
        """Wait for this resource to reach READY state.

        Subscribes to NATS state notifications and waits for the resource
        to transition to READY. Updates self with the outputs from the
        state notification.

        Args:
            timeout: Maximum seconds to wait before raising TimeoutError.

        Returns:
            Self with updated outputs and lifecycle_state.

        Example:
            ```python
            async def on_create(self):
                db = DatabaseResource(name=f"{self.name}-db", config=DbConfig(...))
                await db.apply()  # Owner automatically set from context
                await db.wait_ready(timeout=120.0)
                return AppOutputs(db_url=db.outputs.connection_url)
            ```
        """
        data = await wait_for_resource_state(self.id, LifecycleState.READY, timeout)

        self.lifecycle_state = LifecycleState(data.get("lifecycle_state", "ready"))

        outputs_data = data.get("outputs")
        if outputs_data is not None:
            outputs_type = self._outputs_type()
            if outputs_type is not None:
                self.outputs = outputs_type.model_validate(outputs_data)  # type: ignore[assignment]
            else:
                self.outputs = outputs_data

        return self

    def _outputs_type(self) -> type[Outputs] | None:
        """Get the OutputsT type from the model fields annotation.

        Returns:
            The Outputs subclass type or None if not determinable.
        """
        outputs_field = self.__class__.model_fields.get("outputs")
        if outputs_field is None:
            return None

        annotation = outputs_field.annotation
        if annotation is None:
            return None

        origin = typing.get_origin(annotation)
        if origin is type(None):
            return None

        if origin is typing.Union:
            args = typing.get_args(annotation)
            for arg in args:
                if arg is not type(None) and isinstance(arg, type) and issubclass(arg, Outputs):
                    return arg
            return None

        if isinstance(annotation, type) and issubclass(annotation, Outputs):
            return annotation

        return None
