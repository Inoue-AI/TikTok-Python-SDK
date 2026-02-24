"""Tests for the Data Portability API namespace."""

from __future__ import annotations

import re

import pytest
from aioresponses import aioresponses

from tiktok.client import TikTokClient
from tiktok.exceptions import TikTokAPIError, TikTokAuthError
from tiktok.models.data_portability import (
    AddDataRequestData,
    DataCategory,
    DataFormat,
    DataRequestStatus,
    DataRequestStatusData,
    StatusField,
)

BASE = "https://open.tiktokapis.com"

# Regex helpers — match URLs regardless of query-string order.
_URL_ADD = re.compile(rf"^{re.escape(BASE)}/v2/user/data/add/")
_URL_CHECK = re.compile(rf"^{re.escape(BASE)}/v2/user/data/check/")
_URL_CANCEL = re.compile(rf"^{re.escape(BASE)}/v2/user/data/cancel/")
_URL_DOWNLOAD = re.compile(rf"^{re.escape(BASE)}/v2/user/data/download/")


# ---------------------------------------------------------------------------
# add_data_request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_data_request_success(client: TikTokClient) -> None:
    response_payload = {
        "data": {"request_id": 987654321},
        "error": {"code": "ok", "message": "", "log_id": "abc"},
    }

    with aioresponses() as mock:
        mock.post(_URL_ADD, payload=response_payload)
        result = await client.data_portability.add_data_request(
            data_format=DataFormat.JSON,
            category_selection_list=[DataCategory.PROFILE, DataCategory.VIDEO],
        )

    assert isinstance(result, AddDataRequestData)
    assert result.request_id == 987654321


@pytest.mark.asyncio
async def test_add_data_request_all_data(client: TikTokClient) -> None:
    response_payload = {
        "data": {"request_id": 111222333},
        "error": {"code": "ok", "message": "", "log_id": "xyz"},
    }

    with aioresponses() as mock:
        mock.post(_URL_ADD, payload=response_payload)
        result = await client.data_portability.add_data_request(
            data_format=DataFormat.TEXT,
            category_selection_list=[DataCategory.ALL_DATA],
        )

    assert result.request_id == 111222333


@pytest.mark.asyncio
async def test_add_data_request_activity_and_dm(client: TikTokClient) -> None:
    response_payload = {
        "data": {"request_id": 444555666},
        "error": {"code": "ok", "message": "", "log_id": "abc"},
    }

    with aioresponses() as mock:
        mock.post(_URL_ADD, payload=response_payload)
        result = await client.data_portability.add_data_request(
            data_format=DataFormat.JSON,
            category_selection_list=[DataCategory.ACTIVITY, DataCategory.DIRECT_MESSAGE],
        )

    assert result.request_id == 444555666


@pytest.mark.asyncio
async def test_add_data_request_scope_error(client: TikTokClient) -> None:
    response_payload = {
        "data": {},
        "error": {
            "code": "scope_not_authorized",
            "message": "Required portability scope not granted.",
            "log_id": "err001",
        },
    }

    with aioresponses() as mock:
        mock.post(_URL_ADD, payload=response_payload)
        with pytest.raises(TikTokAuthError) as exc_info:
            await client.data_portability.add_data_request(
                data_format=DataFormat.JSON,
                category_selection_list=[DataCategory.DIRECT_MESSAGE],
            )

    assert exc_info.value.code == "scope_not_authorized"


# ---------------------------------------------------------------------------
# check_data_request_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_data_request_status_pending(client: TikTokClient) -> None:
    response_payload = {
        "data": {
            "request_id": 987654321,
            "apply_time": 1700000000,
            "collect_time": 1700000005,
            "status": "pending",
            "data_format": "json",
            "category_selection_list": ["profile", "video"],
        },
        "error": {"code": "ok", "message": "", "log_id": "x"},
    }

    with aioresponses() as mock:
        mock.post(_URL_CHECK, payload=response_payload)
        result = await client.data_portability.check_data_request_status(987654321)

    assert isinstance(result, DataRequestStatusData)
    assert result.status == DataRequestStatus.PENDING
    assert result.data_format == DataFormat.JSON
    assert DataCategory.PROFILE in (result.category_selection_list or [])
    assert result.apply_time == 1700000000


@pytest.mark.asyncio
async def test_check_data_request_status_downloading(client: TikTokClient) -> None:
    response_payload = {
        "data": {
            "request_id": 999,
            "status": "downloading",
        },
        "error": {"code": "ok", "message": "", "log_id": "y"},
    }

    with aioresponses() as mock:
        mock.post(_URL_CHECK, payload=response_payload)
        result = await client.data_portability.check_data_request_status(
            999,
            fields=[StatusField.REQUEST_ID, StatusField.STATUS],
        )

    assert result.status == DataRequestStatus.DOWNLOADING
    assert result.request_id == 999


@pytest.mark.asyncio
async def test_check_data_request_status_expired(client: TikTokClient) -> None:
    response_payload = {
        "data": {"request_id": 777, "status": "expired"},
        "error": {"code": "ok", "message": "", "log_id": "z"},
    }

    with aioresponses() as mock:
        mock.post(_URL_CHECK, payload=response_payload)
        result = await client.data_portability.check_data_request_status(777)

    assert result.status == DataRequestStatus.EXPIRED


@pytest.mark.asyncio
async def test_check_data_request_status_cancelled(client: TikTokClient) -> None:
    response_payload = {
        "data": {"request_id": 555, "status": "cancelled"},
        "error": {"code": "ok", "message": "", "log_id": "z"},
    }

    with aioresponses() as mock:
        mock.post(_URL_CHECK, payload=response_payload)
        result = await client.data_portability.check_data_request_status(555)

    assert result.status == DataRequestStatus.CANCELLED


# ---------------------------------------------------------------------------
# cancel_data_request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_data_request_success(client: TikTokClient) -> None:
    response_payload = {"error": {"code": "ok", "message": "", "log_id": "cancel_log_123"}}

    with aioresponses() as mock:
        mock.post(_URL_CANCEL, payload=response_payload)
        # Should complete without raising.
        await client.data_portability.cancel_data_request(987654321)


@pytest.mark.asyncio
async def test_cancel_data_request_api_error(client: TikTokClient) -> None:
    response_payload = {
        "error": {
            "code": "resource_not_found",
            "message": "Request not found.",
            "log_id": "err002",
        }
    }

    with aioresponses() as mock:
        mock.post(_URL_CANCEL, payload=response_payload)
        with pytest.raises(TikTokAPIError) as exc_info:
            await client.data_portability.cancel_data_request(0)

    assert exc_info.value.code == "resource_not_found"


# ---------------------------------------------------------------------------
# download_data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_data_success(client: TikTokClient) -> None:
    fake_zip = b"PK\x03\x04"  # Minimal zip magic bytes

    with aioresponses() as mock:
        mock.post(
            _URL_DOWNLOAD,
            body=fake_zip,
            content_type="application/zip",
            status=200,
        )
        data = await client.data_portability.download_data(987654321)

    assert data == fake_zip
    assert data[:4] == b"PK\x03\x04"
