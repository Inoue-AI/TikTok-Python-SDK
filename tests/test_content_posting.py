"""Tests for the Content Posting API namespace."""

from __future__ import annotations

import re

import pytest
from aioresponses import aioresponses

from tiktok.client import TikTokClient
from tiktok.exceptions import TikTokAPIError, TikTokAuthError
from tiktok.models.content_posting import (
    CreatorInfo,
    FailReason,
    PhotoInitData,
    PostStatus,
    PostStatusData,
    PrivacyLevel,
    VideoInitData,
    VideoSource,
)

BASE = "https://open.tiktokapis.com"

# Regex helpers — match URLs regardless of query-string order.
_URL_CREATOR_INFO = re.compile(rf"^{re.escape(BASE)}/v2/post/publish/creator_info/query/")
_URL_VIDEO_INIT = re.compile(rf"^{re.escape(BASE)}/v2/post/publish/video/init/")
_URL_INBOX_INIT = re.compile(rf"^{re.escape(BASE)}/v2/post/publish/inbox/video/init/")
_URL_CONTENT_INIT = re.compile(rf"^{re.escape(BASE)}/v2/post/publish/content/init/")
_URL_STATUS = re.compile(rf"^{re.escape(BASE)}/v2/post/publish/status/fetch/")
_URL_UPLOAD = re.compile(r"^https://open-upload\.tiktokapis\.com/upload/")


# ---------------------------------------------------------------------------
# query_creator_info
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_creator_info_success(client: TikTokClient) -> None:
    response_payload = {
        "data": {
            "creator_avatar_url": "https://example.com/avatar.jpg",
            "creator_username": "testuser",
            "creator_nickname": "Test User",
            "privacy_level_options": ["PUBLIC_TO_EVERYONE", "SELF_ONLY"],
            "comment_disabled": False,
            "duet_disabled": False,
            "stitch_disabled": True,
            "max_video_post_duration_sec": 60,
        },
        "error": {"code": "ok", "message": "", "log_id": "abc123"},
    }

    with aioresponses() as mock:
        mock.post(_URL_CREATOR_INFO, payload=response_payload)
        info = await client.content_posting.query_creator_info()

    assert isinstance(info, CreatorInfo)
    assert info.creator_username == "testuser"
    assert info.creator_nickname == "Test User"
    assert PrivacyLevel.PUBLIC_TO_EVERYONE in info.privacy_level_options
    assert info.stitch_disabled is True
    assert info.max_video_post_duration_sec == 60


@pytest.mark.asyncio
async def test_query_creator_info_auth_error(client: TikTokClient) -> None:
    response_payload = {
        "data": {},
        "error": {
            "code": "access_token_invalid",
            "message": "The access token is invalid.",
            "log_id": "err123",
        },
    }

    with aioresponses() as mock:
        mock.post(_URL_CREATOR_INFO, payload=response_payload)
        with pytest.raises(TikTokAuthError) as exc_info:
            await client.content_posting.query_creator_info()

    assert exc_info.value.code == "access_token_invalid"
    assert exc_info.value.log_id == "err123"


# ---------------------------------------------------------------------------
# init_video_post — PULL_FROM_URL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_init_video_post_pull_from_url(client: TikTokClient) -> None:
    response_payload = {
        "data": {"publish_id": "pub_123456"},
        "error": {"code": "ok", "message": "", "log_id": "abc"},
    }

    with aioresponses() as mock:
        mock.post(_URL_VIDEO_INIT, payload=response_payload)
        result = await client.content_posting.init_video_post(
            privacy_level=PrivacyLevel.PUBLIC_TO_EVERYONE,
            source=VideoSource.PULL_FROM_URL,
            video_url="https://example.com/video.mp4",
            title="My awesome video",
        )

    assert isinstance(result, VideoInitData)
    assert result.publish_id == "pub_123456"
    assert result.upload_url is None


@pytest.mark.asyncio
async def test_init_video_post_file_upload(client: TikTokClient) -> None:
    response_payload = {
        "data": {
            "publish_id": "pub_789",
            "upload_url": "https://open-upload.tiktokapis.com/upload/?upload_id=x&upload_token=y",
        },
        "error": {"code": "ok", "message": "", "log_id": "abc"},
    }

    with aioresponses() as mock:
        mock.post(_URL_VIDEO_INIT, payload=response_payload)
        result = await client.content_posting.init_video_post(
            privacy_level=PrivacyLevel.SELF_ONLY,
            source=VideoSource.FILE_UPLOAD,
            video_size=1024 * 1024 * 50,
            chunk_size=1024 * 1024 * 10,
            total_chunk_count=5,
        )

    assert result.publish_id == "pub_789"
    assert result.upload_url is not None
    assert "upload_token" in result.upload_url


@pytest.mark.asyncio
async def test_init_video_post_file_upload_missing_params(client: TikTokClient) -> None:
    with pytest.raises(TikTokAPIError) as exc_info:
        await client.content_posting.init_video_post(
            privacy_level=PrivacyLevel.SELF_ONLY,
            source=VideoSource.FILE_UPLOAD,
            # video_size, chunk_size, total_chunk_count intentionally omitted
        )
    assert exc_info.value.code == "invalid_params"


@pytest.mark.asyncio
async def test_post_video_from_url_missing_video_url(client: TikTokClient) -> None:
    with pytest.raises(TikTokAPIError) as exc_info:
        await client.content_posting.init_video_post(
            privacy_level=PrivacyLevel.PUBLIC_TO_EVERYONE,
            source=VideoSource.PULL_FROM_URL,
            # video_url intentionally omitted
        )
    assert exc_info.value.code == "invalid_params"


# ---------------------------------------------------------------------------
# init_inbox_video
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_init_inbox_video(client: TikTokClient) -> None:
    response_payload = {
        "data": {
            "publish_id": "inbox_pub_001",
            "upload_url": "https://open-upload.tiktokapis.com/upload/?upload_id=a&upload_token=b",
        },
        "error": {"code": "ok", "message": "", "log_id": "x"},
    }

    with aioresponses() as mock:
        mock.post(_URL_INBOX_INIT, payload=response_payload)
        result = await client.content_posting.init_inbox_video(
            source=VideoSource.FILE_UPLOAD,
            video_size=5_000_000,
            chunk_size=5_000_000,
            total_chunk_count=1,
        )

    assert result.publish_id == "inbox_pub_001"
    assert result.upload_url is not None


# ---------------------------------------------------------------------------
# post_photos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_photos_success(client: TikTokClient) -> None:
    response_payload = {
        "data": {"publish_id": "photo_pub_001"},
        "error": {"code": "ok", "message": "", "log_id": "x"},
    }

    with aioresponses() as mock:
        mock.post(_URL_CONTENT_INIT, payload=response_payload)
        result = await client.content_posting.post_photos(
            photo_image_urls=["https://example.com/1.jpg", "https://example.com/2.jpg"],
            privacy_level=PrivacyLevel.PUBLIC_TO_EVERYONE,
            title="My photo carousel",
            auto_add_music=True,
        )

    assert isinstance(result, PhotoInitData)
    assert result.publish_id == "photo_pub_001"


# ---------------------------------------------------------------------------
# get_post_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_post_status_complete(client: TikTokClient) -> None:
    response_payload = {
        "data": {
            "status": "PUBLISH_COMPLETE",
            "publicaly_available_post_id": [7123456789012345678],
        },
        "error": {"code": "ok", "message": "", "log_id": "x"},
    }

    with aioresponses() as mock:
        mock.post(_URL_STATUS, payload=response_payload)
        result = await client.content_posting.get_post_status("pub_123")

    assert isinstance(result, PostStatusData)
    assert result.status == PostStatus.PUBLISH_COMPLETE
    assert result.fail_reason is None
    assert 7123456789012345678 in result.publicaly_available_post_id


@pytest.mark.asyncio
async def test_get_post_status_failed(client: TikTokClient) -> None:
    response_payload = {
        "data": {
            "status": "FAILED",
            "fail_reason": "duration_check_failed",
        },
        "error": {"code": "ok", "message": "", "log_id": "x"},
    }

    with aioresponses() as mock:
        mock.post(_URL_STATUS, payload=response_payload)
        result = await client.content_posting.get_post_status("pub_456")

    assert result.status == PostStatus.FAILED
    assert result.fail_reason == FailReason.DURATION_CHECK_FAILED


@pytest.mark.asyncio
async def test_get_post_status_processing(client: TikTokClient) -> None:
    response_payload = {
        "data": {
            "status": "PROCESSING_DOWNLOAD",
            "downloaded_bytes": 1048576,
        },
        "error": {"code": "ok", "message": "", "log_id": "x"},
    }

    with aioresponses() as mock:
        mock.post(_URL_STATUS, payload=response_payload)
        result = await client.content_posting.get_post_status("pub_789")

    assert result.status == PostStatus.PROCESSING_DOWNLOAD
    assert result.downloaded_bytes == 1048576


# ---------------------------------------------------------------------------
# upload_video_chunk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_video_chunk(client: TikTokClient) -> None:
    upload_url = "https://open-upload.tiktokapis.com/upload/?upload_id=x&upload_token=y"
    chunk_data = b"A" * 1024

    with aioresponses() as mock:
        mock.put(_URL_UPLOAD, status=200)
        await client.content_posting.upload_video_chunk(
            upload_url,
            data=chunk_data,
            start_byte=0,
            total_bytes=1024,
        )
    # No exception means success.
