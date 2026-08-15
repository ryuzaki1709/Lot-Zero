"""Explicit domain-level exceptions; boundary adapters translate them deliberately."""


class LotZeroDomainError(Exception):
    """Base class for expected domain failures."""


class InvariantViolation(LotZeroDomainError):
    """Raised when a domain record or transition breaks an invariant."""


class VersionConflict(LotZeroDomainError):
    """Raised when a command is bound to an obsolete case or boundary version."""


class AuthorizationDenied(LotZeroDomainError):
    """Raised when a principal lacks authority for a consequential operation."""


class PolicyDenied(LotZeroDomainError):
    """Raised when an otherwise authorized operation fails policy evaluation."""


class UnknownCommandKind(LotZeroDomainError):
    """Raised by command dispatch when no closed command variant matches."""
