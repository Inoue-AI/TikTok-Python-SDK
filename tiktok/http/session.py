"""Async HTTP session that wraps ``aiohttp`` for all TikTok API communication.

Responsibilities
----------------
* Attach ``Authorization`` and ``Content-Type`` headers to every request.
* Deserialise JSON responses and surface TikTok error payloads as typed
  exceptions.
* Handle binary PUT uploads (chunked video transfer).
* Handle streaming binary downloads (Data Portability zip files).
"""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from tiktok.config import DEFAULT_TIMEOUT
from tiktok.exceptions import TikTokUploadError, build_api_error


class TikTokSession:
    """Thin async HTTP client bound to a single user access token.

    The underlying :class:`aiohttp.ClientSession` is created lazily on the
    first request so the object can be constructed outside a running event
    loop without triggering deprecation warnings.

    Parameters
    ----------
    access_token:
        A valid TikTok user access token obtained via OAuth 2.0.
    timeout:
        Total request timeout in seconds (default: ``DEFAULT_TIMEOUT``).
    """

    def __init__(self, access_token: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._access_token = access_token
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        async with self._lock:
            if self._session is None or self._session.closed:
                connector = aiohttp.TCPConnector(
                    limit=100,
                    ttl_dns_cache=300,
                    ssl=True,
                )
                self._session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=self._timeout,
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                    },
                )
        return self._session

    async def aclose(self) -> None:
        """Close the underlying HTTP session and release all connections."""
        async with self._lock:
            if self._session is not None and not self._session.closed:
                await self._session.close()
                self._session = None

    # ------------------------------------------------------------------
    # Public request methods
    # ------------------------------------------------------------------

    async def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Issue a GET request and return the parsed JSON body."""
        session = await self._get_session()
        async with session.get(url, params=params) as response:
            return await self._parse_json_response(response)

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Issue a POST request with an optional JSON body and return the parsed JSON body."""
        session = await self._get_session()
        async with session.post(
            url,
            json=json,
            params=params,
            headers={"Content-Type": "application/json; charset=UTF-8"},
        ) as response:
            return await self._parse_json_response(response)

    async def post_no_body(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Issue a POST request with an empty body (some TikTok endpoints require this)."""
        session = await self._get_session()
        async with session.post(
            url,
            params=params,
            headers={"Content-Type": "application/json; charset=UTF-8"},
            data=b"",
        ) as response:
            return await self._parse_json_response(response)

    async def put_chunk(
        self,
        upload_url: str,
        *,
        data: bytes,
        content_type: str,
        content_range: str,
    ) -> None:
        """Upload a single binary chunk via PUT to an upload URL.

        Parameters
        ----------
        upload_url:
            Full URL returned by a ``/init/`` endpoint (includes upload token).
        data:
            Raw bytes for this chunk.
        content_type:
            MIME type of the video (``video/mp4``, ``video/quicktime``, or
            ``video/webm``).
        content_range:
            ``Content-Range`` header value in the form
            ``bytes {start}-{end}/{total}``.
        """
        session = await self._get_session()
        chunk_headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(data)),
            "Content-Range": content_range,
        }
        async with session.put(upload_url, data=data, headers=chunk_headers) as response:
            if response.status not in (200, 201, 204, 206):
                raise TikTokUploadError(
                    f"Chunk upload failed — HTTP {response.status}",
                    http_status=response.status,
                )

    async def post_stream(
        self,
        url: str,
        *,
        json: dict[str, Any],
    ) -> bytes:
        """Issue a POST request and return the raw binary response body.

        Used exclusively by the Data Portability download endpoint, which
        streams a zip archive rather than a JSON payload.
        """
        session = await self._get_session()
        async with session.post(
            url,
            json=json,
            headers={"Content-Type": "application/json"},
        ) as response:
            if response.status != 200:
                # The error is returned as JSON even for the streaming endpoint.
                try:
                    payload = await response.json(content_type=None)
                    error = payload.get("error", {})
                    raise build_api_error(
                        code=error.get("code", "unknown_error"),
                        message=error.get("message", "Unknown error"),
                        log_id=error.get("log_id", ""),
                        http_status=response.status,
                    )
                except (ValueError, KeyError):
                    raise TikTokUploadError(
                        f"Download request failed — HTTP {response.status}",
                        http_status=response.status,
                    ) from None
            return await response.read()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _parse_json_response(response: aiohttp.ClientResponse) -> dict[str, Any]:
        """Parse a TikTok JSON response, raising on non-OK error codes.

        TikTok always embeds an ``error`` object in the response body.  When
        ``error.code`` is ``"ok"`` the call succeeded; any other value is
        treated as an error regardless of the HTTP status code.
        """
        raw_body = await response.read()
        if not raw_body or not raw_body.strip():
            raise build_api_error(
                code="empty_response",
                message=f"TikTok returned an empty response body (HTTP {response.status}, url={response.url})",
                log_id="",
                http_status=response.status,
            )

        payload: dict[str, Any] = await response.json(content_type=None)
        error: dict[str, Any] = payload.get("error", {})
        code: str = error.get("code", "ok")

        if code != "ok":
            raise build_api_error(
                code=code,
                message=error.get("message", ""),
                log_id=error.get("log_id", ""),
                http_status=response.status,
            )

        return payload
