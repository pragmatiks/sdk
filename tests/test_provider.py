"""Tests for provider authoring, Provider class, and ProviderHarness."""

from __future__ import annotations

import pytest
from conftest import FailingResource, StubConfig, StubOutputs, StubResource

from pragma_sdk import LifecycleState, Provider, Resource
from pragma_sdk.provider import ProviderHarness


def test_provider_resource_decorator_sets_classvars() -> None:
    """@provider.resource() sets provider and resource ClassVars."""
    test_provider = Provider(name="test_provider")

    @test_provider.resource("test_resource")
    class TestResource(Resource[StubConfig, StubOutputs]):
        async def on_create(self) -> StubOutputs:
            return StubOutputs(url="test")

        async def on_update(self, previous_config: StubConfig) -> StubOutputs:
            return StubOutputs(url="test")

        async def on_delete(self) -> None:
            pass

    assert TestResource.provider == "test_provider"
    assert TestResource.resource == "test_resource"


def test_provider_collects_resources() -> None:
    """Provider.resources contains all registered resources."""
    test_provider = Provider(name="collector")

    @test_provider.resource("first")
    class FirstResource(Resource[StubConfig, StubOutputs]):
        async def on_create(self) -> StubOutputs:
            return StubOutputs(url="first")

        async def on_update(self, previous_config: StubConfig) -> StubOutputs:
            return StubOutputs(url="first")

        async def on_delete(self) -> None:
            pass

    @test_provider.resource("second")
    class SecondResource(Resource[StubConfig, StubOutputs]):
        async def on_create(self) -> StubOutputs:
            return StubOutputs(url="second")

        async def on_update(self, previous_config: StubConfig) -> StubOutputs:
            return StubOutputs(url="second")

        async def on_delete(self) -> None:
            pass

    assert len(test_provider.resources) == 2
    assert "first" in test_provider.resources
    assert "second" in test_provider.resources
    assert test_provider.resources["first"] is FirstResource
    assert test_provider.resources["second"] is SecondResource


def test_provider_prevents_duplicate_resource_names() -> None:
    """Provider raises ValueError when resource name is already registered."""
    test_provider = Provider(name="duplicates")

    @test_provider.resource("unique")
    class FirstResource(Resource[StubConfig, StubOutputs]):
        async def on_create(self) -> StubOutputs:
            return StubOutputs(url="first")

        async def on_update(self, previous_config: StubConfig) -> StubOutputs:
            return StubOutputs(url="first")

        async def on_delete(self) -> None:
            pass

    with pytest.raises(ValueError, match="already registered"):

        @test_provider.resource("unique")
        class SecondResource(Resource[StubConfig, StubOutputs]):
            async def on_create(self) -> StubOutputs:
                return StubOutputs(url="second")

            async def on_update(self, previous_config: StubConfig) -> StubOutputs:
                return StubOutputs(url="second")

            async def on_delete(self) -> None:
                pass


def test_provider_repr() -> None:
    """Provider __repr__ shows name and resources."""
    test_provider = Provider(name="repr_test")

    @test_provider.resource("resource_a")
    class ResourceA(Resource[StubConfig, StubOutputs]):
        async def on_create(self) -> StubOutputs:
            return StubOutputs(url="a")

        async def on_update(self, previous_config: StubConfig) -> StubOutputs:
            return StubOutputs(url="a")

        async def on_delete(self) -> None:
            pass

    assert "repr_test" in repr(test_provider)
    assert "resource_a" in repr(test_provider)


def test_provider_resource_rejects_non_resource_class() -> None:
    """@provider.resource() raises TypeError for non-Resource classes."""
    test_provider = Provider(name="test")

    with pytest.raises(TypeError, match="can only decorate Resource subclasses"):

        @test_provider.resource("invalid")
        class NotAResource:
            pass


async def test_invoke_create_returns_outputs(harness: ProviderHarness) -> None:
    """invoke_create executes on_create and returns outputs."""
    config = StubConfig(name="my-resource", size=20)
    result = await harness.invoke_create(StubResource, name="my-resource", config=config)

    assert result.success
    assert result.outputs.url == "https://my-resource.example.com"
    assert result.resource.lifecycle_state == LifecycleState.PROCESSING


async def test_invoke_create_captures_errors(harness: ProviderHarness) -> None:
    """invoke_create captures exceptions as failed results."""
    config = StubConfig(name="will-fail")
    result = await harness.invoke_create(FailingResource, name="will-fail", config=config)

    assert result.failed
    assert result.error is not None
    assert "Creation failed" in str(result.error)


async def test_invoke_update_passes_previous_config(harness: ProviderHarness) -> None:
    """invoke_update provides previous config to on_update method."""
    result = await harness.invoke_update(
        StubResource,
        name="my-resource",
        config=StubConfig(name="my-resource", size=50),
        previous_config=StubConfig(name="my-resource", size=10),
        current_outputs=StubOutputs(url="https://old.example.com"),
    )

    assert result.success
    assert "updated" in result.outputs.url


async def test_invoke_delete_succeeds(harness: ProviderHarness) -> None:
    """invoke_delete executes on_delete method."""
    config = StubConfig(name="my-resource")
    result = await harness.invoke_delete(StubResource, name="my-resource", config=config)

    assert result.success
    assert result.outputs is None


async def test_harness_tracks_events_and_results(harness: ProviderHarness) -> None:
    """ProviderHarness tracks all events and results."""
    await harness.invoke_create(StubResource, name="r1", config=StubConfig(name="r1"))
    await harness.invoke_create(StubResource, name="r2", config=StubConfig(name="r2"))

    assert len(harness.events) == 2
    assert len(harness.results) == 2
    assert harness.events[0].name == "r1"
    assert harness.events[1].name == "r2"


async def test_harness_clear_resets_history(harness: ProviderHarness) -> None:
    """clear() resets event and result history."""
    await harness.invoke_create(StubResource, name="r1", config=StubConfig(name="r1"))
    harness.clear()

    assert len(harness.events) == 0
    assert len(harness.results) == 0
