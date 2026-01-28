"""Enumeration types for the Pragma SDK."""

from __future__ import annotations

from enum import StrEnum


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


class EventType(StrEnum):
    """Resource lifecycle event type: CREATE, UPDATE, or DELETE."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class ResponseStatus(StrEnum):
    """Provider response status: SUCCESS or FAILURE."""

    SUCCESS = "success"
    FAILURE = "failure"
