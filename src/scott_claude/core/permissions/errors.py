from __future__ import annotations


class PermissionDeniedError(Exception):
    """Raised when a tool call is denied by the permission manager."""
