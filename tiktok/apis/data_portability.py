"""Data Portability API namespace.

Wraps the following TikTok endpoints:

* ``POST /v2/user/data/add/``      — initiate a data export request
* ``POST /v2/user/data/check/``    — check the status of a request
* ``POST /v2/user/data/cancel/``   — cancel a pending request
* ``POST /v2/user/data/download/`` — download the exported zip archive

Reference: https://developers.tiktok.com/doc/data-portability-api-get-started

Availability note: This API is available only to users in the **European
Economic Area (EEA)** or the **United Kingdom (UK)**.
"""

from __future__ import annotations

from typing import Any

from tiktok.apis.base import BaseAPI
from tiktok.config import TIKTOK_API_BASE_URL
from tiktok.models.data_portability import (
    AddDataRequestData,
    DataCategory,
    DataFormat,
    DataRequestStatusData,
    StatusField,
)

_BASE = TIKTOK_API_BASE_URL

# Fields to request from the status endpoint by default.
_ALL_STATUS_FIELDS = list(StatusField)


class DataPortabilityAPI(BaseAPI):
    """Methods for exporting and downloading a user's TikTok data.

    All methods require an access token authorised with one or more
    ``portability.*`` scopes corresponding to the requested data categories.
    """

    # ------------------------------------------------------------------
    # Add data request
    # ------------------------------------------------------------------

    async def add_data_request(
        self,
        *,
        data_format: DataFormat,
        category_selection_list: list[DataCategory],
    ) -> AddDataRequestData:
        """Initiate a new data export request.

        Parameters
        ----------
        data_format:
            Output format for the archive (``"json"`` or ``"text"``).
        category_selection_list:
            One or more data categories to include in the export.  The
            authenticated user must have granted the corresponding
            ``portability.*`` scope(s).

        Scope required: varies by category (see :class:`DataCategory`).

        Returns:
            :class:`~tiktok.models.data_portability.AddDataRequestData`
            containing the ``request_id`` needed for subsequent calls.

        Raises:
            :class:`~tiktok.exceptions.TikTokAuthError`: Token lacks scope.
            :class:`~tiktok.exceptions.TikTokAPIError`: Any other API error.
        """
        payload = await self._session.post(
            f"{_BASE}/v2/user/data/add/",
            json={
                "data_format": data_format.value,
                "category_selection_list": [c.value for c in category_selection_list],
            },
            params={"fields": "request_id"},
        )
        return AddDataRequestData.model_validate(payload["data"])

    # ------------------------------------------------------------------
    # Check status
    # ------------------------------------------------------------------

    async def check_data_request_status(
        self,
        request_id: int,
        *,
        fields: list[StatusField] | None = None,
    ) -> DataRequestStatusData:
        """Check the processing status of an export request.

        Parameters
        ----------
        request_id:
            The ``request_id`` returned by :meth:`add_data_request`.
        fields:
            Status fields to include in the response.  Defaults to all
            available fields (see :class:`StatusField`).

        Scope required: same as used when creating the request.

        Returns:
            :class:`~tiktok.models.data_portability.DataRequestStatusData`.

        Raises:
            :class:`~tiktok.exceptions.TikTokAuthError`: Token lacks scope.
            :class:`~tiktok.exceptions.TikTokAPIError`: Any other API error.
        """
        requested_fields: list[StatusField] = fields if fields is not None else _ALL_STATUS_FIELDS
        params: dict[str, Any] = {
            "fields": ",".join(f.value for f in requested_fields),
        }
        payload = await self._session.post(
            f"{_BASE}/v2/user/data/check/",
            json={"request_id": request_id},
            params=params,
        )
        return DataRequestStatusData.model_validate(payload["data"])

    # ------------------------------------------------------------------
    # Cancel data request
    # ------------------------------------------------------------------

    async def cancel_data_request(self, request_id: int) -> None:
        """Cancel a pending data export request.

        Parameters
        ----------
        request_id:
            The ``request_id`` to cancel.

        Scope required: same as used when creating the request.

        Raises:
            :class:`~tiktok.exceptions.TikTokAuthError`: Token lacks scope.
            :class:`~tiktok.exceptions.TikTokAPIError`: Any other API error.
        """
        await self._session.post(
            f"{_BASE}/v2/user/data/cancel/",
            params={"request_id": str(request_id)},
        )

    # ------------------------------------------------------------------
    # Download data
    # ------------------------------------------------------------------

    async def download_data(self, request_id: int) -> bytes:
        """Download the exported data archive as raw bytes.

        The archive is a ``.zip`` file.  Call this only after the request
        status is ``DataRequestStatus.DOWNLOADING`` (or you have received
        the webhook notification from TikTok).

        Parameters
        ----------
        request_id:
            The ``request_id`` returned by :meth:`add_data_request`.

        Scope required: same as used when creating the request.

        Returns:
            Raw bytes of the zip archive.

        Raises:
            :class:`~tiktok.exceptions.TikTokAuthError`: Token lacks scope.
            :class:`~tiktok.exceptions.TikTokUploadError`: Download failure.
            :class:`~tiktok.exceptions.TikTokAPIError`: Any other API error.
        """
        return await self._session.post_stream(
            f"{_BASE}/v2/user/data/download/",
            json={"request_id": request_id},
        )
