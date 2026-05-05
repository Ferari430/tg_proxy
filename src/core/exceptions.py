class TgProxyError(Exception):
    """Base exception for all application errors."""


class ConfigError(TgProxyError):
    """Invalid or missing configuration."""


class MappingNotFoundError(TgProxyError):
    """Chat is not in the configured group mappings."""


class DatabaseError(TgProxyError):
    """Database operation failed."""
