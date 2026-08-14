from __future__ import annotations


class RateLimitedError(Exception):
    """Raised by a tool when the upstream service is rate-limiting the request."""
