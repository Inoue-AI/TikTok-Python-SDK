"""Tests for the Display API namespace."""

from __future__ import annotations

import re

import pytest
from aioresponses import aioresponses

from tiktok.client import TikTokClient
from tiktok.exceptions import TikTokAPIError
from tiktok.models.display import (
    User,
    UserField,
    Video,
    VideoField,
    VideoListData,
    VideoQueryData,
)

BASE = "https://open.tiktokapis.com"

# Regex helpers — match URLs regardless of query-string order.
_URL_USER_INFO = re.compile(rf"^{re.escape(BASE)}/v2/user/info/")
_URL_VIDEO_LIST = re.compile(rf"^{re.escape(BASE)}/v2/video/list/")
_URL_VIDEO_QUERY = re.compile(rf"^{re.escape(BASE)}/v2/video/query/")


# ---------------------------------------------------------------------------
# get_user_info
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_info_basic(client: TikTokClient) -> None:
    response_payload = {
        "data": {
            "user": {
                "open_id": "open_123",
                "union_id": "union_456",
                "avatar_url": "https://cdn.example.com/avatar.jpg",
                "display_name": "Jane Doe",
            }
        },
        "error": {"code": "ok", "message": "", "log_id": "xyz"},
    }

    with aioresponses() as mock:
        mock.get(_URL_USER_INFO, payload=response_payload)
        user = await client.display.get_user_info(
            fields=[
                UserField.OPEN_ID,
                UserField.UNION_ID,
                UserField.AVATAR_URL,
                UserField.DISPLAY_NAME,
            ]
        )

    assert isinstance(user, User)
    assert user.open_id == "open_123"
    assert user.display_name == "Jane Doe"
    # Fields not requested should remain None.
    assert user.follower_count is None
    assert user.bio_description is None


@pytest.mark.asyncio
async def test_get_user_info_with_stats(client: TikTokClient) -> None:
    response_payload = {
        "data": {
            "user": {
                "open_id": "open_001",
                "display_name": "Creator",
                "follower_count": 100_000,
                "following_count": 250,
                "likes_count": 5_000_000,
                "video_count": 42,
            }
        },
        "error": {"code": "ok", "message": "", "log_id": "abc"},
    }

    with aioresponses() as mock:
        mock.get(_URL_USER_INFO, payload=response_payload)
        user = await client.display.get_user_info(
            fields=[
                UserField.OPEN_ID,
                UserField.DISPLAY_NAME,
                UserField.FOLLOWER_COUNT,
                UserField.FOLLOWING_COUNT,
                UserField.LIKES_COUNT,
                UserField.VIDEO_COUNT,
            ]
        )

    assert user.follower_count == 100_000
    assert user.video_count == 42


@pytest.mark.asyncio
async def test_get_user_info_profile_fields(client: TikTokClient) -> None:
    response_payload = {
        "data": {
            "user": {
                "open_id": "open_999",
                "username": "coolguy",
                "bio_description": "Making great content",
                "is_verified": True,
                "profile_deep_link": "https://vm.tiktok.com/coolguy",
            }
        },
        "error": {"code": "ok", "message": "", "log_id": "abc"},
    }

    with aioresponses() as mock:
        mock.get(_URL_USER_INFO, payload=response_payload)
        user = await client.display.get_user_info(
            fields=[
                UserField.OPEN_ID,
                UserField.USERNAME,
                UserField.BIO_DESCRIPTION,
                UserField.IS_VERIFIED,
                UserField.PROFILE_DEEP_LINK,
            ]
        )

    assert user.username == "coolguy"
    assert user.is_verified is True
    assert user.bio_description == "Making great content"


# ---------------------------------------------------------------------------
# list_videos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_videos_first_page(client: TikTokClient) -> None:
    response_payload = {
        "data": {
            "videos": [
                {"id": "v001", "title": "First video", "duration": 30},
                {"id": "v002", "title": "Second video", "duration": 60},
            ],
            "cursor": 1700000000000,
            "has_more": True,
        },
        "error": {"code": "ok", "message": "", "log_id": "x"},
    }

    with aioresponses() as mock:
        mock.get(_URL_VIDEO_LIST, payload=response_payload)
        result = await client.display.list_videos(
            fields=[VideoField.ID, VideoField.TITLE, VideoField.DURATION]
        )

    assert isinstance(result, VideoListData)
    assert len(result.videos) == 2
    assert result.videos[0].id == "v001"
    assert result.videos[1].title == "Second video"
    assert result.has_more is True
    assert result.cursor == 1700000000000


@pytest.mark.asyncio
async def test_list_videos_last_page(client: TikTokClient) -> None:
    response_payload = {
        "data": {
            "videos": [{"id": "v010", "title": "Oldest video", "duration": 15}],
            "cursor": 1699000000000,
            "has_more": False,
        },
        "error": {"code": "ok", "message": "", "log_id": "x"},
    }

    with aioresponses() as mock:
        mock.get(_URL_VIDEO_LIST, payload=response_payload)
        result = await client.display.list_videos(
            fields=[VideoField.ID, VideoField.TITLE, VideoField.DURATION],
            cursor=1700000000000,
        )

    assert result.has_more is False
    assert result.videos[0].id == "v010"


@pytest.mark.asyncio
async def test_list_videos_all_fields(client: TikTokClient) -> None:
    response_payload = {
        "data": {
            "videos": [
                {
                    "id": "v888",
                    "create_time": 1700000000,
                    "cover_image_url": "https://cdn.example.com/cover.jpg",
                    "share_url": "https://vm.tiktok.com/v888",
                    "video_description": "Great video",
                    "duration": 45,
                    "height": 1920,
                    "width": 1080,
                    "title": "Full fields test",
                    "embed_html": "<blockquote>...</blockquote>",
                    "embed_link": "https://www.tiktok.com/embed/v2/v888",
                    "like_count": 9999,
                    "comment_count": 250,
                    "share_count": 120,
                    "view_count": 500000,
                }
            ],
            "cursor": 1700000000000,
            "has_more": False,
        },
        "error": {"code": "ok", "message": "", "log_id": "x"},
    }

    with aioresponses() as mock:
        mock.get(_URL_VIDEO_LIST, payload=response_payload)
        result = await client.display.list_videos(fields=list(VideoField))

    video = result.videos[0]
    assert video.id == "v888"
    assert video.like_count == 9999
    assert video.view_count == 500000
    assert video.height == 1920
    assert video.width == 1080


@pytest.mark.asyncio
async def test_iter_videos_pagination(client: TikTokClient) -> None:
    first_page = {
        "data": {
            "videos": [{"id": "v001"}, {"id": "v002"}],
            "cursor": 1700000000000,
            "has_more": True,
        },
        "error": {"code": "ok", "message": "", "log_id": "a"},
    }
    second_page = {
        "data": {
            "videos": [{"id": "v003"}],
            "cursor": 1699000000000,
            "has_more": False,
        },
        "error": {"code": "ok", "message": "", "log_id": "b"},
    }

    with aioresponses() as mock:
        mock.get(_URL_VIDEO_LIST, payload=first_page)
        mock.get(_URL_VIDEO_LIST, payload=second_page)

        collected: list[Video] = []
        async for video in client.display.iter_videos(fields=[VideoField.ID]):
            collected.append(video)

    assert [v.id for v in collected] == ["v001", "v002", "v003"]


# ---------------------------------------------------------------------------
# query_videos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_videos_success(client: TikTokClient) -> None:
    response_payload = {
        "data": {
            "videos": [
                {
                    "id": "v001",
                    "cover_image_url": "https://cdn.example.com/cover1.jpg",
                    "embed_link": "https://www.tiktok.com/embed/v2/v001",
                    "like_count": 1500,
                    "view_count": 50000,
                }
            ]
        },
        "error": {"code": "ok", "message": "", "log_id": "x"},
    }

    with aioresponses() as mock:
        mock.post(_URL_VIDEO_QUERY, payload=response_payload)
        result = await client.display.query_videos(
            video_ids=["v001"],
            fields=[
                VideoField.ID,
                VideoField.COVER_IMAGE_URL,
                VideoField.EMBED_LINK,
                VideoField.LIKE_COUNT,
                VideoField.VIEW_COUNT,
            ],
        )

    assert isinstance(result, VideoQueryData)
    assert len(result.videos) == 1
    assert result.videos[0].like_count == 1500
    assert result.videos[0].view_count == 50000


@pytest.mark.asyncio
async def test_query_videos_multiple_ids(client: TikTokClient) -> None:
    response_payload = {
        "data": {
            "videos": [
                {"id": "v001", "title": "Video One"},
                {"id": "v002", "title": "Video Two"},
            ]
        },
        "error": {"code": "ok", "message": "", "log_id": "x"},
    }

    with aioresponses() as mock:
        mock.post(_URL_VIDEO_QUERY, payload=response_payload)
        result = await client.display.query_videos(
            video_ids=["v001", "v002"],
            fields=[VideoField.ID, VideoField.TITLE],
        )

    assert len(result.videos) == 2
    assert result.videos[0].id == "v001"
    assert result.videos[1].title == "Video Two"


@pytest.mark.asyncio
async def test_query_videos_empty_ids_raises(client: TikTokClient) -> None:
    with pytest.raises(TikTokAPIError) as exc_info:
        await client.display.query_videos(video_ids=[], fields=[VideoField.ID])
    assert exc_info.value.code == "invalid_params"


@pytest.mark.asyncio
async def test_query_videos_too_many_ids_raises(client: TikTokClient) -> None:
    too_many = [str(i) for i in range(21)]
    with pytest.raises(TikTokAPIError) as exc_info:
        await client.display.query_videos(video_ids=too_many, fields=[VideoField.ID])
    assert exc_info.value.code == "invalid_params"
    assert "20" in exc_info.value.message
