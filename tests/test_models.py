"""Tests for SDK core models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from pragma_sdk import (
    BuildResult,
    BuildStatus,
    Config,
    DeploymentResult,
    DeploymentStatus,
    Field,
    FieldReference,
    LifecycleState,
    PushResult,
    ResourceReference,
    format_resource_id,
)


if TYPE_CHECKING:
    from conftest import StubResource

from conftest import StubConfig


def test_lifecycle_state_values() -> None:
    """LifecycleState enum has all 5 states."""
    assert LifecycleState.DRAFT == "draft"
    assert LifecycleState.PENDING == "pending"
    assert LifecycleState.PROCESSING == "processing"
    assert LifecycleState.READY == "ready"
    assert LifecycleState.FAILED == "failed"


def test_format_resource_id() -> None:
    """format_resource_id creates format ID."""
    result = format_resource_id("postgres", "database", "my-db")
    assert result == "resource:postgres_database_my-db"


def test_resource_reference_id_property() -> None:
    """ResourceReference.id returns formatted resource ID."""
    ref = ResourceReference(provider="postgres", resource="database", name="my-db")
    assert ref.id == "resource:postgres_database_my-db"


def test_field_reference_extends_resource_reference() -> None:
    """FieldReference has field attribute on top of ResourceReference."""
    ref = FieldReference(
        provider="postgres",
        resource="database",
        name="my-db",
        field="outputs.connection_url",
    )
    assert ref.provider == "postgres"
    assert ref.resource == "database"
    assert ref.name == "my-db"
    assert ref.field == "outputs.connection_url"
    assert ref.id == "resource:postgres_database_my-db"


def test_config_forbids_extra_fields() -> None:
    """Config subclasses reject extra fields."""
    with pytest.raises(ValidationError):
        StubConfig(name="test", size=10, unknown_field="bad")


def test_resource_id_property(stub_resource: StubResource) -> None:
    """Resource.id returns formatted resource ID."""
    assert stub_resource.id == "resource:test_stub_my-resource"


def test_resource_default_lifecycle_state(stub_resource: StubResource) -> None:
    """Resource defaults to DRAFT lifecycle state."""
    assert stub_resource.lifecycle_state == LifecycleState.DRAFT


def test_resource_with_field_reference_in_config() -> None:
    """Config field can be a FieldReference instead of direct value."""
    ref = FieldReference(
        provider="postgres",
        resource="database",
        name="my-db",
        field="outputs.connection_url",
    )

    class AppConfig(Config):
        name: Field[str]
        database_url: Field[str]

    config1 = AppConfig(name="app", database_url="postgres://localhost")
    assert config1.database_url == "postgres://localhost"

    config2 = AppConfig(name="app", database_url=ref)
    assert isinstance(config2.database_url, FieldReference)
    assert config2.database_url.field == "outputs.connection_url"


def test_build_status_values() -> None:
    """BuildStatus enum has all 4 states."""
    assert BuildStatus.PENDING == "pending"
    assert BuildStatus.BUILDING == "building"
    assert BuildStatus.SUCCESS == "success"
    assert BuildStatus.FAILED == "failed"


def test_deployment_status_values() -> None:
    """DeploymentStatus enum has all 4 states."""
    assert DeploymentStatus.PENDING == "pending"
    assert DeploymentStatus.PROGRESSING == "progressing"
    assert DeploymentStatus.AVAILABLE == "available"
    assert DeploymentStatus.FAILED == "failed"


def test_push_result_model() -> None:
    """PushResult stores build initiation info."""
    result = PushResult(
        version="20250115.120000",
        job_name="build-my-provider-abc12345",
        status=BuildStatus.PENDING,
        message="Build started",
    )
    assert result.version == "20250115.120000"
    assert result.job_name == "build-my-provider-abc12345"
    assert result.status == BuildStatus.PENDING
    assert result.message == "Build started"


def test_build_result_success() -> None:
    """BuildResult stores successful build info."""
    result = BuildResult(
        job_name="build-job-123",
        status=BuildStatus.SUCCESS,
        image="registry.local/my-provider:abc123",
    )
    assert result.status == BuildStatus.SUCCESS
    assert result.image == "registry.local/my-provider:abc123"
    assert result.error_message is None


def test_build_result_failure() -> None:
    """BuildResult stores failed build info."""
    result = BuildResult(
        job_name="build-job-456",
        status=BuildStatus.FAILED,
        error_message="Dockerfile syntax error",
    )
    assert result.status == BuildStatus.FAILED
    assert result.error_message == "Dockerfile syntax error"
    assert result.image is None


def test_deployment_result_available() -> None:
    """DeploymentResult stores available deployment info."""
    result = DeploymentResult(
        deployment_name="provider-my-provider",
        status=DeploymentStatus.AVAILABLE,
        available_replicas=1,
        ready_replicas=1,
    )
    assert result.status == DeploymentStatus.AVAILABLE
    assert result.available_replicas == 1
    assert result.ready_replicas == 1
    assert result.message is None


def test_deployment_result_progressing() -> None:
    """DeploymentResult stores progressing deployment info."""
    result = DeploymentResult(
        deployment_name="provider-my-provider",
        status=DeploymentStatus.PROGRESSING,
        available_replicas=0,
        ready_replicas=0,
        message="Deployment in progress",
    )
    assert result.status == DeploymentStatus.PROGRESSING
    assert result.message == "Deployment in progress"
