"""Pydantic models for the TikTok Data Portability API responses.

Reference: https://developers.tiktok.com/doc/data-portability-api-get-started
"""

from __future__ import annotations

from enum import StrEnum

from tiktok.models.base import TikTokBaseModel

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DataCategory(StrEnum):
    """Data categories that can be requested via the Data Portability API.

    Each category corresponds to a set of OAuth scopes:

    * ``ALL_DATA``       -> ``portability.all.single`` / ``portability.all.ongoing``
    * ``ACTIVITY``       -> ``portability.activity.single`` / ``.ongoing``
    * ``VIDEO``          -> ``portability.postsandprofile.single`` / ``.ongoing``
    * ``PROFILE``        -> ``portability.postsandprofile.single`` / ``.ongoing``
    * ``DIRECT_MESSAGE`` -> ``portability.directmessages.single`` / ``.ongoing``
    """

    ALL_DATA = "all_data"
    ACTIVITY = "activity"
    VIDEO = "video"
    PROFILE = "profile"
    DIRECT_MESSAGE = "direct_message"


class DataFormat(StrEnum):
    """Output format for a data export."""

    TEXT = "text"
    JSON = "json"


class DataRequestStatus(StrEnum):
    """Processing status of a data export request."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class StatusField(StrEnum):
    """Fields that can be requested from ``/v2/user/data/check/``.

    Pass any combination of these values as the ``fields`` parameter.
    """

    REQUEST_ID = "request_id"
    APPLY_TIME = "apply_time"
    COLLECT_TIME = "collect_time"
    STATUS = "status"
    DATA_FORMAT = "data_format"
    CATEGORY_SELECTION_LIST = "category_selection_list"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class AddDataRequestData(TikTokBaseModel):
    """Response data from ``/v2/user/data/add/``.

    Attributes:
        request_id: Unique identifier for this export request.  Store this
                    value - it is required by the status-check and download
                    endpoints.
    """

    request_id: int


class DataRequestStatusData(TikTokBaseModel):
    """Response data from ``/v2/user/data/check/``.

    Only fields included in the ``fields`` query parameter will be
    populated; all others default to ``None``.

    Attributes:
        request_id:              The export request identifier.
        apply_time:              UTC Unix timestamp (seconds) when the request
                                 was submitted.
        collect_time:            UTC Unix timestamp (seconds) when data
                                 collection started.
        status:                  Current processing state.
        data_format:             Output format of the export archive.
        category_selection_list: Data categories included in this export.
    """

    request_id: int | None = None
    apply_time: int | None = None
    collect_time: int | None = None
    status: DataRequestStatus | None = None
    data_format: DataFormat | None = None
    category_selection_list: list[DataCategory] | None = None
