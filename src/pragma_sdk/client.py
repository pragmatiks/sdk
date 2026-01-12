"""HTTP clients for the Pragma API."""

from __future__ import annotations

import os
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from typing import Any

import httpx

from pragma_sdk.auth import BearerAuth
from pragma_sdk.config import get_token_for_context
from pragma_sdk.models import (
    BuildResult,
    DeploymentResult,
    PushResult,
    Resource,
    ResourceDefinition,
    format_resource_id,
)


class BaseClient:
    """Base class for Pragma API clients with shared initialization logic."""

    base_url: str
    timeout: float

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 10.0,
        auth_token: str | None | object = ...,
        context: str | None = None,
        require_auth: bool = False,
    ):
        """Initialize client with automatic token discovery.

        Args:
            base_url: API URL. Defaults to PRAGMA_API_URL env var or localhost:8000.
            timeout: Request timeout in seconds.
            auth_token: Bearer token. Omit for auto-discovery, pass None to disable auth.
            context: Named context for token lookup (e.g., 'production').
            require_auth: Raise if no token can be discovered.

        Raises:
            ValueError: If require_auth is True and no token is found.
        """
        self.base_url = base_url or os.getenv("PRAGMA_API_URL", "http://localhost:8000")
        self.timeout = timeout

        if auth_token is ...:
            resolved_token = get_token_for_context(context)

            if require_auth and resolved_token is None:
                context_display = context or "default"
                raise ValueError(
                    f"Authentication required but no token found for context '{context_display}'. "
                    f"Set PRAGMA_AUTH_TOKEN environment variable, "
                    f"set PRAGMA_AUTH_TOKEN_{context_display.upper()} for context-specific auth, "
                    f"or run 'pragma login'."
                )
        else:
            resolved_token = auth_token if isinstance(auth_token, str) else None

        self._auth = BearerAuth(resolved_token) if resolved_token else None


class PragmaClient(BaseClient):
    """Synchronous client for the Pragma API.

    Example:
        >>> with PragmaClient() as client:
        ...     resources = client.list_resources(provider="example")
        ...     resource = client.get_resource("example", "database", "my-db")
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 10.0,
        auth_token: str | None | object = ...,
        context: str | None = None,
        require_auth: bool = False,
    ):
        """Initialize the synchronous Pragma client.

        See BaseClient for parameter documentation.
        """
        super().__init__(base_url, timeout, auth_token, context, require_auth)
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout, auth=self._auth)

    def __enter__(self):
        """Enter context manager.

        Returns:
            Self for use in with statement.
        """
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """Exit context manager and close client."""
        self.close()

    def close(self):
        """Close the underlying HTTP client."""
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: Any | None = None,
        **kwargs: Any,
    ) -> Any:
        """Make an HTTP request to the Pragma API.

        Returns:
            Parsed JSON response, raw text, or None for 204 responses.

        Raises:
            httpx.HTTPStatusError: If the API returns an error response.
        """  # noqa: DOC502
        response = self._client.request(
            method=method,
            url=path,
            params=params,
            json=json_data,
            **kwargs,
        )

        response.raise_for_status()
        if response.status_code == 204:
            return None
        if response.headers.get("content-type") == "application/json":
            return response.json()
        return response.text

    def is_healthy(self) -> bool:
        """Check if the Pragma API is healthy.

        Returns:
            True if API returns healthy status, False otherwise.
        """
        try:
            response = self._request("GET", "/health")
            return response.get("status") == "ok"
        except httpx.HTTPError:
            return False

    def register_resource(
        self,
        provider: str,
        resource: str,
        schema: dict[str, Any] | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> ResourceDefinition:
        """Register a new resource type.

        Args:
            provider: Provider that will manage this resource type.
            resource: Resource type name (e.g., 'database', 'connection').
            schema: JSON schema for validating resource configurations.
            description: Human-readable description.
            tags: Tags for categorization and filtering.

        Returns:
            The registered resource definition.

        Raises:
            httpx.HTTPStatusError: If registration fails.
        """  # noqa: DOC502
        payload: dict[str, Any] = {"provider": provider, "resource": resource}
        if schema is not None:
            payload["schema"] = schema
        if description is not None:
            payload["description"] = description
        if tags is not None:
            payload["tags"] = tags

        response = self._request("POST", "/resources/register", json_data=payload)
        return ResourceDefinition.model_validate(response)

    def unregister_resource(self, provider: str, resource: str) -> None:
        """Unregister a resource type.

        Raises:
            httpx.HTTPStatusError: If unregistration fails or resource type not found.
        """  # noqa: DOC502
        self._request("DELETE", f"/resources/unregister/{provider}/{resource}")

    def list_resources[ResourceT: Resource](
        self,
        provider: str | None = None,
        resource: str | None = None,
        tags: list[str] | None = None,
        *,
        model: type[ResourceT] | None = None,
    ) -> list[ResourceT] | list[dict[str, Any]]:
        """List resources with optional filters.

        Args:
            provider: Filter by provider name.
            resource: Filter by resource type.
            tags: Filter by tags (must match all).
            model: Resource subclass for typed response; returns raw dicts if None.

        Returns:
            List of resources as typed instances or raw dicts.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """  # noqa: DOC502
        params = {}
        if provider:
            params["provider"] = provider
        if resource:
            params["resource"] = resource
        if tags:
            params["tags"] = tags

        response = self._request("GET", "/resources/", params=params)
        if model is not None:
            return [model.model_validate(item) for item in response]
        return response

    def get_resource[ResourceT: Resource](
        self,
        provider: str,
        resource: str,
        name: str,
        *,
        model: type[ResourceT] | None = None,
    ) -> ResourceT | dict[str, Any]:
        """Get a resource by its full identifier.

        Args:
            provider: Provider that manages the resource.
            resource: Resource type name.
            name: Resource instance name.
            model: Resource subclass for typed response; returns raw dict if None.

        Returns:
            Resource as typed instance or raw dict.

        Raises:
            httpx.HTTPStatusError: If resource not found or request fails.
        """  # noqa: DOC502
        resource_id = format_resource_id(provider, resource, name)
        response = self._request("GET", f"/resources/{resource_id}")
        if model is not None:
            return model.model_validate(response)
        return response

    def apply_resource[ResourceT: Resource](
        self,
        resource: ResourceT | dict[str, Any],
        *,
        model: type[ResourceT] | None = None,
    ) -> ResourceT | dict[str, Any]:
        """Apply a resource (create or update).

        Args:
            resource: Resource to apply as typed instance or raw dict.
            model: Resource subclass for typed response; returns raw dict if None.

        Returns:
            Applied resource as typed instance or raw dict.

        Raises:
            httpx.HTTPStatusError: If the apply operation fails.
        """  # noqa: DOC502
        json_data = resource.model_dump() if isinstance(resource, Resource) else resource
        response = self._request("POST", "/resources/apply", json_data=json_data)
        if model is not None:
            return model.model_validate(response)
        return response

    def delete_resource(self, provider: str, resource: str, name: str) -> None:
        """Delete a resource.

        Raises:
            httpx.HTTPStatusError: If resource not found or deletion fails.
        """  # noqa: DOC502
        resource_id = format_resource_id(provider, resource, name)
        self._request("DELETE", f"/resources/{resource_id}")

    def list_dead_letter_events(self, provider: str | None = None) -> list[dict[str, Any]]:
        """List dead letter events with optional provider filter.

        Args:
            provider: Filter by provider name.

        Returns:
            List of dead letter events as raw dicts.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """  # noqa: DOC502
        params = {}
        if provider:
            params["provider"] = provider
        return self._request("GET", "/ops/dead-letter", params=params)

    def get_dead_letter_event(self, event_id: str) -> dict[str, Any]:
        """Get a dead letter event by ID.

        Args:
            event_id: The dead letter event ID.

        Returns:
            Dead letter event as raw dict.

        Raises:
            httpx.HTTPStatusError: If event not found or request fails.
        """  # noqa: DOC502
        return self._request("GET", f"/ops/dead-letter/{event_id}")

    def retry_dead_letter_event(self, event_id: str) -> None:
        """Retry a dead letter event.

        Args:
            event_id: The dead letter event ID to retry.

        Raises:
            httpx.HTTPStatusError: If event not found or retry fails.
        """  # noqa: DOC502
        self._request("POST", f"/ops/dead-letter/{event_id}/retry")

    def retry_all_dead_letter_events(self) -> int:
        """Retry all dead letter events.

        Returns:
            Number of events retried.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """  # noqa: DOC502
        response = self._request("POST", "/ops/dead-letter/retry-all")
        return response["retried_count"]

    def delete_dead_letter_event(self, event_id: str) -> None:
        """Delete a dead letter event.

        Args:
            event_id: The dead letter event ID to delete.

        Raises:
            httpx.HTTPStatusError: If event not found or deletion fails.
        """  # noqa: DOC502
        self._request("DELETE", f"/ops/dead-letter/{event_id}")

    def delete_dead_letter_events(self, provider: str | None = None, *, all: bool = False) -> int:
        """Delete multiple dead letter events.

        Args:
            provider: Delete events for this provider only.
            all: Delete all dead letter events (ignores provider filter).

        Returns:
            Number of events deleted.

        Raises:
            ValueError: If neither provider nor all is specified.
            httpx.HTTPStatusError: If the request fails.
        """  # noqa: DOC502
        if not provider and not all:
            raise ValueError("Must specify either provider or all=True")

        params: dict[str, Any] = {}
        if all:
            params["all"] = "true"
        elif provider:
            params["provider"] = provider

        response = self._request("DELETE", "/ops/dead-letter", params=params)
        return response["deleted_count"]

    def push_provider(self, provider_id: str, tarball: bytes) -> PushResult:
        """Push provider code and trigger a build.

        Uploads a tarball containing provider source code and starts a
        BuildKit job to build a container image.

        Args:
            provider_id: Unique identifier for the provider.
            tarball: Gzipped tarball (tar.gz) containing provider source code.

        Returns:
            PushResult with build ID and job name for tracking.

        Raises:
            httpx.HTTPStatusError: If the push fails.
        """  # noqa: DOC502
        response = self._request(
            "POST",
            f"/providers/{provider_id}/push",
            files={"code": ("code.tar.gz", tarball, "application/gzip")},
        )
        return PushResult.model_validate(response)

    def get_build_status(self, provider_id: str, job_name: str) -> BuildResult:
        """Get the status of a build job.

        Args:
            provider_id: Provider identifier.
            job_name: Name of the BuildKit job.

        Returns:
            BuildResult with current build state.

        Raises:
            httpx.HTTPStatusError: If build job not found or request fails.
        """  # noqa: DOC502
        response = self._request("GET", f"/providers/{provider_id}/builds/{job_name}")
        return BuildResult.model_validate(response)

    def stream_build_logs(self, provider_id: str, job_name: str) -> AbstractContextManager[httpx.Response]:
        """Stream logs from a build job.

        Returns a streaming response for real-time monitoring of build progress.
        The caller is responsible for iterating over the response and closing it.

        Args:
            provider_id: Provider identifier.
            job_name: Name of the BuildKit job.

        Returns:
            Context manager yielding httpx.Response with build logs (text/plain).

        Raises:
            httpx.HTTPStatusError: If build job not found or request fails.

        Example:
            >>> with client.stream_build_logs("my-provider", "build-job-123") as response:
            ...     for line in response.iter_lines():
            ...         print(line)
        """  # noqa: DOC502
        return self._client.stream("GET", f"/providers/{provider_id}/builds/{job_name}/logs")

    def deploy_provider(self, provider_id: str, image: str) -> DeploymentResult:
        """Deploy a provider from a built container image.

        Creates or updates the Kubernetes Deployment for the provider.

        Args:
            provider_id: Unique identifier for the provider.
            image: Full container image reference (e.g., registry/image:tag).

        Returns:
            DeploymentResult with initial deployment state.

        Raises:
            httpx.HTTPStatusError: If deployment fails.
        """  # noqa: DOC502
        response = self._request(
            "POST",
            f"/providers/{provider_id}/deploy",
            json_data={"image": image},
        )
        return DeploymentResult.model_validate(response)

    def get_deployment_status(self, provider_id: str) -> DeploymentResult:
        """Get the deployment status for a provider.

        Args:
            provider_id: Unique identifier for the provider.

        Returns:
            DeploymentResult with current deployment state.

        Raises:
            httpx.HTTPStatusError: If deployment not found or request fails.
        """  # noqa: DOC502
        response = self._request("GET", f"/providers/{provider_id}/deployment")
        return DeploymentResult.model_validate(response)


class AsyncPragmaClient(BaseClient):
    """Asynchronous client for the Pragma API.

    Example:
        >>> async with AsyncPragmaClient() as client:
        ...     resources = await client.list_resources(provider="example")
        ...     resource = await client.get_resource("example", "database", "my-db")
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 10.0,
        auth_token: str | None | object = ...,
        context: str | None = None,
        require_auth: bool = False,
    ):
        """Initialize the asynchronous Pragma client.

        See BaseClient for parameter documentation.
        """
        super().__init__(base_url, timeout, auth_token, context, require_auth)
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout, auth=self._auth)

    async def __aenter__(self):
        """Enter async context manager.

        Returns:
            Self for use in async with statement.
        """
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager and close client."""
        await self._client.__aexit__(exc_type, exc_val, exc_tb)

    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: Any | None = None,
        **kwargs: Any,
    ) -> Any:
        """Make an HTTP request to the Pragma API.

        Returns:
            Parsed JSON response, raw text, or None for 204 responses.

        Raises:
            httpx.HTTPStatusError: If the API returns an error response.
        """  # noqa: DOC502
        response = await self._client.request(
            method=method,
            url=path,
            params=params,
            json=json_data,
            **kwargs,
        )

        response.raise_for_status()
        if response.status_code == 204:
            return None
        if response.headers.get("content-type") == "application/json":
            return response.json()
        return response.text

    async def is_healthy(self) -> bool:
        """Check if the Pragma API is healthy.

        Returns:
            True if API returns healthy status, False otherwise.
        """
        try:
            response = await self._request("GET", "/health")
            return response.get("status") == "ok"
        except httpx.HTTPError:
            return False

    async def register_resource(
        self,
        provider: str,
        resource: str,
        schema: dict[str, Any] | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> ResourceDefinition:
        """Register a new resource type.

        Args:
            provider: Provider that will manage this resource type.
            resource: Resource type name (e.g., 'database', 'connection').
            schema: JSON schema for validating resource configurations.
            description: Human-readable description.
            tags: Tags for categorization and filtering.

        Returns:
            The registered resource definition.

        Raises:
            httpx.HTTPStatusError: If registration fails.
        """  # noqa: DOC502
        payload: dict[str, Any] = {"provider": provider, "resource": resource}
        if schema is not None:
            payload["schema"] = schema
        if description is not None:
            payload["description"] = description
        if tags is not None:
            payload["tags"] = tags

        response = await self._request("POST", "/resources/register", json_data=payload)
        return ResourceDefinition.model_validate(response)

    async def unregister_resource(self, provider: str, resource: str) -> None:
        """Unregister a resource type.

        Raises:
            httpx.HTTPStatusError: If unregistration fails or resource type not found.
        """  # noqa: DOC502
        await self._request("DELETE", f"/resources/unregister/{provider}/{resource}")

    async def list_resources[ResourceT: Resource](
        self,
        provider: str | None = None,
        resource: str | None = None,
        tags: list[str] | None = None,
        *,
        model: type[ResourceT] | None = None,
    ) -> list[ResourceT] | list[dict[str, Any]]:
        """List resources with optional filters.

        Args:
            provider: Filter by provider name.
            resource: Filter by resource type.
            tags: Filter by tags (must match all).
            model: Resource subclass for typed response; returns raw dicts if None.

        Returns:
            List of resources as typed instances or raw dicts.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """  # noqa: DOC502
        params = {}
        if provider:
            params["provider"] = provider
        if resource:
            params["resource"] = resource
        if tags:
            params["tags"] = tags

        response = await self._request("GET", "/resources/", params=params)
        if model is not None:
            return [model.model_validate(item) for item in response]
        return response

    async def get_resource[ResourceT: Resource](
        self,
        provider: str,
        resource: str,
        name: str,
        *,
        model: type[ResourceT] | None = None,
    ) -> ResourceT | dict[str, Any]:
        """Get a resource by its full identifier.

        Args:
            provider: Provider that manages the resource.
            resource: Resource type name.
            name: Resource instance name.
            model: Resource subclass for typed response; returns raw dict if None.

        Returns:
            Resource as typed instance or raw dict.

        Raises:
            httpx.HTTPStatusError: If resource not found or request fails.
        """  # noqa: DOC502
        resource_id = format_resource_id(provider, resource, name)
        response = await self._request("GET", f"/resources/{resource_id}")
        if model is not None:
            return model.model_validate(response)
        return response

    async def apply_resource[ResourceT: Resource](
        self,
        resource: ResourceT | dict[str, Any],
        *,
        model: type[ResourceT] | None = None,
    ) -> ResourceT | dict[str, Any]:
        """Apply a resource (create or update).

        Args:
            resource: Resource to apply as typed instance or raw dict.
            model: Resource subclass for typed response; returns raw dict if None.

        Returns:
            Applied resource as typed instance or raw dict.

        Raises:
            httpx.HTTPStatusError: If the apply operation fails.
        """  # noqa: DOC502
        json_data = resource.model_dump() if isinstance(resource, Resource) else resource
        response = await self._request("POST", "/resources/apply", json_data=json_data)
        if model is not None:
            return model.model_validate(response)
        return response

    async def delete_resource(self, provider: str, resource: str, name: str) -> None:
        """Delete a resource.

        Raises:
            httpx.HTTPStatusError: If resource not found or deletion fails.
        """  # noqa: DOC502
        resource_id = format_resource_id(provider, resource, name)
        await self._request("DELETE", f"/resources/{resource_id}")

    async def list_dead_letter_events(self, provider: str | None = None) -> list[dict[str, Any]]:
        """List dead letter events with optional provider filter.

        Args:
            provider: Filter by provider name.

        Returns:
            List of dead letter events as raw dicts.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """  # noqa: DOC502
        params = {}
        if provider:
            params["provider"] = provider
        return await self._request("GET", "/ops/dead-letter", params=params)

    async def get_dead_letter_event(self, event_id: str) -> dict[str, Any]:
        """Get a dead letter event by ID.

        Args:
            event_id: The dead letter event ID.

        Returns:
            Dead letter event as raw dict.

        Raises:
            httpx.HTTPStatusError: If event not found or request fails.
        """  # noqa: DOC502
        return await self._request("GET", f"/ops/dead-letter/{event_id}")

    async def retry_dead_letter_event(self, event_id: str) -> None:
        """Retry a dead letter event.

        Args:
            event_id: The dead letter event ID to retry.

        Raises:
            httpx.HTTPStatusError: If event not found or retry fails.
        """  # noqa: DOC502
        await self._request("POST", f"/ops/dead-letter/{event_id}/retry")

    async def retry_all_dead_letter_events(self) -> int:
        """Retry all dead letter events.

        Returns:
            Number of events retried.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """  # noqa: DOC502
        response = await self._request("POST", "/ops/dead-letter/retry-all")
        return response["retried_count"]

    async def delete_dead_letter_event(self, event_id: str) -> None:
        """Delete a dead letter event.

        Args:
            event_id: The dead letter event ID to delete.

        Raises:
            httpx.HTTPStatusError: If event not found or deletion fails.
        """  # noqa: DOC502
        await self._request("DELETE", f"/ops/dead-letter/{event_id}")

    async def delete_dead_letter_events(self, provider: str | None = None, *, all: bool = False) -> int:
        """Delete multiple dead letter events.

        Args:
            provider: Delete events for this provider only.
            all: Delete all dead letter events (ignores provider filter).

        Returns:
            Number of events deleted.

        Raises:
            ValueError: If neither provider nor all is specified.
            httpx.HTTPStatusError: If the request fails.
        """  # noqa: DOC502
        if not provider and not all:
            raise ValueError("Must specify either provider or all=True")

        params: dict[str, Any] = {}
        if all:
            params["all"] = "true"
        elif provider:
            params["provider"] = provider

        response = await self._request("DELETE", "/ops/dead-letter", params=params)
        return response["deleted_count"]

    async def push_provider(self, provider_id: str, tarball: bytes) -> PushResult:
        """Push provider code and trigger a build.

        Uploads a tarball containing provider source code and starts a
        BuildKit job to build a container image.

        Args:
            provider_id: Unique identifier for the provider.
            tarball: Gzipped tarball (tar.gz) containing provider source code.

        Returns:
            PushResult with build ID and job name for tracking.

        Raises:
            httpx.HTTPStatusError: If the push fails.
        """  # noqa: DOC502
        response = await self._request(
            "POST",
            f"/providers/{provider_id}/push",
            files={"code": ("code.tar.gz", tarball, "application/gzip")},
        )
        return PushResult.model_validate(response)

    async def get_build_status(self, provider_id: str, job_name: str) -> BuildResult:
        """Get the status of a build job.

        Args:
            provider_id: Provider identifier.
            job_name: Name of the BuildKit job.

        Returns:
            BuildResult with current build state.

        Raises:
            httpx.HTTPStatusError: If build job not found or request fails.
        """  # noqa: DOC502
        response = await self._request("GET", f"/providers/{provider_id}/builds/{job_name}")
        return BuildResult.model_validate(response)

    def stream_build_logs(self, provider_id: str, job_name: str) -> AbstractAsyncContextManager[httpx.Response]:
        """Stream logs from a build job.

        Returns a streaming response for real-time monitoring of build progress.
        The caller is responsible for iterating over the response and closing it.

        Args:
            provider_id: Provider identifier.
            job_name: Name of the BuildKit job.

        Returns:
            Async context manager yielding httpx.Response with build logs (text/plain).

        Raises:
            httpx.HTTPStatusError: If build job not found or request fails.

        Example:
            >>> async with client.stream_build_logs("my-provider", "build-job-123") as response:
            ...     async for line in response.aiter_lines():
            ...         print(line)
        """  # noqa: DOC502
        return self._client.stream("GET", f"/providers/{provider_id}/builds/{job_name}/logs")

    async def deploy_provider(self, provider_id: str, image: str) -> DeploymentResult:
        """Deploy a provider from a built container image.

        Creates or updates the Kubernetes Deployment for the provider.

        Args:
            provider_id: Unique identifier for the provider.
            image: Full container image reference (e.g., registry/image:tag).

        Returns:
            DeploymentResult with initial deployment state.

        Raises:
            httpx.HTTPStatusError: If deployment fails.
        """  # noqa: DOC502
        response = await self._request(
            "POST",
            f"/providers/{provider_id}/deploy",
            json_data={"image": image},
        )
        return DeploymentResult.model_validate(response)

    async def get_deployment_status(self, provider_id: str) -> DeploymentResult:
        """Get the deployment status for a provider.

        Args:
            provider_id: Unique identifier for the provider.

        Returns:
            DeploymentResult with current deployment state.

        Raises:
            httpx.HTTPStatusError: If deployment not found or request fails.
        """  # noqa: DOC502
        response = await self._request("GET", f"/providers/{provider_id}/deployment")
        return DeploymentResult.model_validate(response)
