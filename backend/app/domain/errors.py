class PostedError(Exception):
    """Base class for typed application errors."""


class IncompleteSnapshotError(PostedError):
    """Raised when a brokerage response cannot prove snapshot completeness."""


class IdempotencyConflictError(PostedError):
    """Raised when an idempotency key is reused for different work."""


class SyncAlreadyRunningError(PostedError):
    """Raised when a connection-scoped synchronization lock is already held."""


class ProviderNotConfiguredError(PostedError):
    """Raised when a requested provider has no usable credentials."""
