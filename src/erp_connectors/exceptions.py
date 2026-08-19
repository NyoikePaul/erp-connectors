"""Shared connector errors."""

class ERPConnectorError(Exception):
    """Base for all connector failures."""


class AuthenticationError(ERPConnectorError):
    pass


class NotFoundError(ERPConnectorError):
    pass


class TransientError(ERPConnectorError):
    """Network / 5xx / rate-limit — safe to retry."""


class ValidationError(ERPConnectorError):
    pass
