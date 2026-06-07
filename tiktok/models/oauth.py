"""Pydantic models for the TikTok OAuth 2.0 endpoints.

Reference: https://developers.tiktok.com/doc/oauth-user-access-token-management

The OAuth endpoints differ from the rest of the API in two ways:

* They are authenticated with the *application* ``client_key`` / ``client_secret``
  pair rather than a user access token.
* The token endpoint accepts ``application/x-www-form-urlencoded`` bodies and
  returns a flat JSON object (no ``data`` / ``error`` envelope); errors are
  surfaced in OAuth2 shape (``error`` / ``error_description``).
"""

from __future__ import annotations

from tiktok.models.base import TikTokBaseModel


class TokenResponse(TikTokBaseModel):
    """Decoded response from ``/v2/oauth/token/``.

    Returned for both the ``authorization_code`` grant (initial exchange) and
    the ``refresh_token`` grant (refresh).

    Attributes:
        access_token:        New user access token.
        expires_in:          Lifetime of ``access_token`` in seconds.
        refresh_token:       New refresh token (TikTok rotates it on refresh).
        refresh_expires_in:  Lifetime of ``refresh_token`` in seconds.
        open_id:             Unique identifier of the authorising user.
        scope:               Space- or comma-delimited list of granted scopes.
        token_type:          Always ``"Bearer"``.
    """

    access_token: str
    expires_in: int
    refresh_token: str
    refresh_expires_in: int
    open_id: str
    scope: str
    token_type: str
