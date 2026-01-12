"""Platform resource types for Pragmatiks internal resources.

Types for Secret resources managed by the pragma provider.
These types are exported from pragma_sdk for use in type hints and config generation.
"""

from pragma_sdk.models import Config, Outputs


class SecretConfig(Config):
    """Configuration for a Secret resource.

    Secrets store sensitive key-value data in SurrealDB. Values can be
    referenced by other resources via FieldReference to config.data.<key>.

    Attributes:
        data: Key-value pairs to store in the secret.
    """

    data: dict[str, str]


class SecretOutputs(Outputs):
    """Outputs produced by Secret creation.

    Attributes:
        keys: List of keys stored in the secret.
    """

    keys: list[str]


def create_secret_config(data: dict[str, str]) -> dict:
    """Build a Secret resource config dict.

    Args:
        data: Key-value pairs to store in the secret.

    Returns:
        Complete resource config dict ready for API submission.

    Example:
        >>> config = create_secret_config({"api_key": "secret123"})
        >>> config
        {'provider': 'pragma', 'resource': 'secret', 'config': {'data': {'api_key': 'secret123'}}}
    """
    return {
        "provider": "pragma",
        "resource": "secret",
        "config": {"data": data},
    }
