"""Exceptions for the Pragma SDK."""

from __future__ import annotations

from typing import Any


class ResourceFailedError(Exception):
    """Raised when a resource transitions to FAILED state during wait operations.

    Attributes:
        resource_id: The ID of the resource that failed.
        error: Error message from the failed resource.
        resource_data: Full resource data from the state notification.
    """

    def __init__(
        self,
        resource_id: str,
        error: str | None = None,
        resource_data: dict[str, Any] | None = None,
    ) -> None:
        """Initialize ResourceFailedError with resource details."""
        self.resource_id = resource_id
        self.error = error
        self.resource_data = resource_data
        message = f"Resource {resource_id} failed"

        if error:
            message += f": {error}"

        super().__init__(message)
