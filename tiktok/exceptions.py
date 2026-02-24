"""Exception hierarchy for the TikTok Python SDK.

All exceptions raised by the SDK derive from ``TikTokSDKError`` so callers
can catch the entire family with a single ``except`` clause when needed.
"""

from __future__ import annotations


class TikTokSDKError(Exception):
    """Base class for every exception raised by this SDK."""


# ---------------------------------------------------------------------------
# API-level errors (the TikTok platform returned an error payload)
# ---------------------------------------------------------------------------


class TikTokAPIError(TikTokSDKError):
    """The TikTok API responded with a non-OK error code.

    Attributes:
        code:        TikTok error code string (e.g. ``"rate_limit_exceeded"``).
        message:     Human-readable description from the API.
        log_id:      Opaque request identifier useful for support tickets.
        http_status: HTTP status code of the underlying response.
    """

    def __init__(
        self,
        code: str,
        message: str,
        log_id: str,
        http_status: int = 200,
    ) -> None:
        self.code = code
        self.message = message
        self.log_id = log_id
        self.http_status = http_status
        super().__init__(f"[{code}] {message} (log_id={log_id})")


class TikTokAuthError(TikTokAPIError):
    """Raised when the access token is missing, invalid, or lacks the required scope."""


class TikTokRateLimitError(TikTokAPIError):
    """Raised when a TikTok rate limit has been exceeded."""


class TikTokNotFoundError(TikTokAPIError):
    """Raised when the requested resource does not exist."""


class TikTokServerError(TikTokAPIError):
    """Raised when TikTok returns an internal server error (5xx)."""


# ---------------------------------------------------------------------------
# Client / transport-level errors
# ---------------------------------------------------------------------------


class TikTokUploadError(TikTokSDKError):
    """Raised when a binary chunk upload to TikTok's upload endpoint fails.

    Attributes:
        http_status: HTTP status code returned by the upload server.
    """

    def __init__(self, message: str, http_status: int | None = None) -> None:
        self.http_status = http_status
        super().__init__(message)


class TikTokConfigError(TikTokSDKError):
    """Raised when the SDK client is misconfigured (e.g. missing credentials)."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Mapping of TikTok error codes to specific exception subclasses.
_ERROR_CODE_MAP: dict[str, type[TikTokAPIError]] = {
    "access_token_invalid": TikTokAuthError,
    "access_token_expired": TikTokAuthError,
    "scope_not_authorized": TikTokAuthError,
    "permission_denied": TikTokAuthError,
    "rate_limit_exceeded": TikTokRateLimitError,
    "spam_risk_too_many_posts": TikTokRateLimitError,
    "resource_not_found": TikTokNotFoundError,
    "internal_error": TikTokServerError,
    "server_error": TikTokServerError,
}


def build_api_error(
    code: str,
    message: str,
    log_id: str,
    http_status: int = 200,
) -> TikTokAPIError:
    """Return the most specific :class:`TikTokAPIError` subclass for *code*."""
    exc_class = _ERROR_CODE_MAP.get(code, TikTokAPIError)
    if http_status >= 500 and exc_class is TikTokAPIError:
        exc_class = TikTokServerError
    return exc_class(code=code, message=message, log_id=log_id, http_status=http_status)
