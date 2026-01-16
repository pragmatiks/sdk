"""Tests for SDK core models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from pragma_sdk import (
    BuildInfo,
    BuildStatus,
    Config,
    Dependency,
    DeploymentResult,
    DeploymentStatus,
    Field,
    FieldReference,
    LifecycleState,
    PushResult,
    ResourceReference,
    format_resource_id,
    is_dependency_marker,
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
        status=BuildStatus.PENDING,
        message="Build started",
    )
    assert result.version == "20250115.120000"
    assert result.status == BuildStatus.PENDING
    assert result.message == "Build started"


def test_build_info_success() -> None:
    """BuildInfo stores successful build info."""
    from datetime import UTC, datetime

    result = BuildInfo(
        provider_id="test-provider",
        version="20250115.120000",
        status=BuildStatus.SUCCESS,
        created_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
    )
    assert result.provider_id == "test-provider"
    assert result.version == "20250115.120000"
    assert result.status == BuildStatus.SUCCESS
    assert result.error_message is None


def test_build_info_failure() -> None:
    """BuildInfo stores failed build info."""
    from datetime import UTC, datetime

    result = BuildInfo(
        provider_id="test-provider",
        version="20250115.120000",
        status=BuildStatus.FAILED,
        error_message="Dockerfile syntax error",
        created_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
    )
    assert result.provider_id == "test-provider"
    assert result.version == "20250115.120000"
    assert result.status == BuildStatus.FAILED
    assert result.error_message == "Dockerfile syntax error"


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


# --- Dependency tests ---


def test_dependency_fields() -> None:
    """Dependency has provider, resource, name fields."""
    from conftest import StubResource

    dep = Dependency[StubResource](
        provider="postgres",
        resource="database",
        name="my-db",
    )
    assert dep.provider == "postgres"
    assert dep.resource == "database"
    assert dep.name == "my-db"


def test_dependency_id_property() -> None:
    """Dependency.id returns formatted resource ID."""
    from conftest import StubResource

    dep = Dependency[StubResource](
        provider="postgres",
        resource="database",
        name="my-db",
    )
    assert dep.id == "resource:postgres_database_my-db"


def test_dependency_serialization_includes_marker() -> None:
    """Dependency serialization includes __dependency__ marker."""
    from conftest import StubResource

    dep = Dependency[StubResource](
        provider="postgres",
        resource="database",
        name="my-db",
    )
    data = dep.model_dump(by_alias=True)
    assert data["__dependency__"] is True
    assert data["provider"] == "postgres"
    assert data["resource"] == "database"
    assert data["name"] == "my-db"


def test_dependency_type_extractable_at_runtime() -> None:
    """Type parameter T is extractable at runtime via __pydantic_generic_metadata__."""
    from conftest import StubResource

    # Create a parameterized type
    dep_type = Dependency[StubResource]

    # Extract the type argument via Pydantic's generic metadata
    # This is how the runtime will extract the type to instantiate the correct Resource subclass
    metadata = getattr(dep_type, "__pydantic_generic_metadata__", None)
    assert metadata is not None
    assert "args" in metadata
    assert len(metadata["args"]) == 1
    assert metadata["args"][0] is StubResource

    # Also verify it works on an instance's type
    dep = Dependency[StubResource](
        provider="test",
        resource="stub",
        name="my-db",
    )
    instance_metadata = getattr(type(dep), "__pydantic_generic_metadata__", None)
    assert instance_metadata is not None
    assert instance_metadata["args"][0] is StubResource


@pytest.mark.anyio
async def test_dependency_resolve_returns_cached_value() -> None:
    """resolve() returns cached value when _resolved is populated."""
    from conftest import StubConfig, StubOutputs, StubResource

    # Create a resolved resource
    config = StubConfig(name="my-db")
    resource = StubResource(
        name="my-db",
        config=config,
        outputs=StubOutputs(url="https://my-db.example.com"),
    )

    # Create dependency and populate _resolved
    dep = Dependency[StubResource](
        provider="test",
        resource="stub",
        name="my-db",
    )
    dep._resolved = resource

    # resolve() should return the cached value
    resolved = await dep.resolve()
    assert resolved is resource
    assert resolved.outputs is not None
    assert resolved.outputs.url == "https://my-db.example.com"


@pytest.mark.anyio
async def test_dependency_resolve_raises_when_not_resolved() -> None:
    """resolve() raises RuntimeError when _resolved is None."""
    from conftest import StubResource

    dep = Dependency[StubResource](
        provider="postgres",
        resource="database",
        name="my-db",
    )

    with pytest.raises(RuntimeError, match="Dependency.*not resolved"):
        await dep.resolve()


def test_dependency_in_config() -> None:
    """Dependency can be used as a field in Config."""
    from conftest import StubResource

    class AppConfig(Config):
        database: Dependency[StubResource]

    dep = Dependency[StubResource](
        provider="test",
        resource="stub",
        name="my-db",
    )
    config = AppConfig(database=dep)

    assert isinstance(config.database, Dependency)
    assert config.database.name == "my-db"
    assert config.database.id == "resource:test_stub_my-db"


# --- is_dependency_marker tests ---


def test_is_dependency_marker_valid() -> None:
    """is_dependency_marker returns True for valid dependency marker."""
    marker = {
        "__dependency__": True,
        "provider": "test",
        "resource": "database",
        "name": "my-db",
    }
    assert is_dependency_marker(marker) is True


def test_is_dependency_marker_with_extra_keys() -> None:
    """is_dependency_marker returns True even with extra keys like 'ref'."""
    marker = {
        "__dependency__": True,
        "provider": "test",
        "resource": "database",
        "name": "my-db",
        "ref": {"some": "data"},  # Added after resolution
    }
    assert is_dependency_marker(marker) is True


def test_is_dependency_marker_false_marker() -> None:
    """is_dependency_marker returns False when __dependency__ is False."""
    marker = {
        "__dependency__": False,
        "provider": "test",
        "resource": "database",
        "name": "my-db",
    }
    assert is_dependency_marker(marker) is False


def test_is_dependency_marker_missing_keys() -> None:
    """is_dependency_marker returns False when required keys are missing."""
    marker = {
        "__dependency__": True,
        "provider": "test",
    }
    assert is_dependency_marker(marker) is False


def test_is_dependency_marker_not_dict() -> None:
    """is_dependency_marker returns False for non-dict values."""
    assert is_dependency_marker("not a dict") is False
    assert is_dependency_marker(None) is False
    assert is_dependency_marker(123) is False
    assert is_dependency_marker([]) is False
