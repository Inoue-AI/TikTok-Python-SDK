"""Pydantic models for the TikTok Display API responses.

Reference: https://developers.tiktok.com/doc/display-api-overview
"""

from __future__ import annotations

from enum import StrEnum

from tiktok.models.base import TikTokBaseModel

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class UserField(StrEnum):
    """Queryable fields for ``/v2/user/info/``.

    Each field maps to a specific OAuth scope:

    * ``OPEN_ID``, ``UNION_ID``, ``AVATAR_URL``, ``AVATAR_URL_100``,
      ``AVATAR_LARGE_URL``, ``DISPLAY_NAME`` -> ``user.info.basic``
    * ``BIO_DESCRIPTION``, ``PROFILE_DEEP_LINK``, ``IS_VERIFIED``,
      ``USERNAME`` -> ``user.info.profile``
    * ``FOLLOWER_COUNT``, ``FOLLOWING_COUNT``, ``LIKES_COUNT``,
      ``VIDEO_COUNT`` -> ``user.info.stats``
    """

    OPEN_ID = "open_id"
    UNION_ID = "union_id"
    AVATAR_URL = "avatar_url"
    AVATAR_URL_100 = "avatar_url_100"
    AVATAR_LARGE_URL = "avatar_large_url"
    DISPLAY_NAME = "display_name"
    BIO_DESCRIPTION = "bio_description"
    PROFILE_DEEP_LINK = "profile_deep_link"
    IS_VERIFIED = "is_verified"
    USERNAME = "username"
    FOLLOWER_COUNT = "follower_count"
    FOLLOWING_COUNT = "following_count"
    LIKES_COUNT = "likes_count"
    VIDEO_COUNT = "video_count"


class VideoField(StrEnum):
    """Queryable fields for ``/v2/video/list/`` and ``/v2/video/query/``.

    Requires the ``video.list`` OAuth scope.
    """

    ID = "id"
    CREATE_TIME = "create_time"
    COVER_IMAGE_URL = "cover_image_url"
    SHARE_URL = "share_url"
    VIDEO_DESCRIPTION = "video_description"
    DURATION = "duration"
    HEIGHT = "height"
    WIDTH = "width"
    TITLE = "title"
    EMBED_HTML = "embed_html"
    EMBED_LINK = "embed_link"
    LIKE_COUNT = "like_count"
    COMMENT_COUNT = "comment_count"
    SHARE_COUNT = "share_count"
    VIEW_COUNT = "view_count"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class User(TikTokBaseModel):
    """TikTok user profile object returned by ``/v2/user/info/``.

    Only fields included in the ``fields`` query parameter will be
    populated; all others default to ``None``.

    Attributes:
        open_id:          Unique identifier for the user within your app.
        union_id:         Identifier shared across apps within the same
                          developer account.
        avatar_url:       CDN URL of the user's profile picture.
        avatar_url_100:   100 x 100 px variant of the avatar.
        avatar_large_url: Large variant of the avatar.
        display_name:     User's display name.
        bio_description:  Profile bio text.
        profile_deep_link: Deep link to the user's TikTok profile.
        is_verified:      Whether the account holds a verified badge.
        username:         ``@handle`` (without the ``@`` prefix).
        follower_count:   Number of followers.
        following_count:  Number of accounts the user follows.
        likes_count:      Total likes received across all videos.
        video_count:      Total number of public videos.
    """

    open_id: str | None = None
    union_id: str | None = None
    avatar_url: str | None = None
    avatar_url_100: str | None = None
    avatar_large_url: str | None = None
    display_name: str | None = None
    bio_description: str | None = None
    profile_deep_link: str | None = None
    is_verified: bool | None = None
    username: str | None = None
    follower_count: int | None = None
    following_count: int | None = None
    likes_count: int | None = None
    video_count: int | None = None


class Video(TikTokBaseModel):
    """TikTok video object returned by list and query endpoints.

    Only fields included in the ``fields`` query parameter will be
    populated; all others default to ``None``.

    Attributes:
        id:                Unique video identifier (also called ``item_id``).
        create_time:       UTC Unix timestamp (seconds) when the video was posted.
        cover_image_url:   CDN link for the static cover image (6-hour TTL).
        share_url:         Shareable link to the video.
        video_description: Creator-set description (max 150 characters).
        duration:          Video length in seconds.
        height:            Vertical dimension in pixels.
        width:             Horizontal dimension in pixels.
        title:             Video title (max 150 characters).
        embed_html:        HTML snippet for embedding the video.
        embed_link:        Embed URL on tiktok.com.
        like_count:        Number of likes.
        comment_count:     Number of comments.
        share_count:       Number of shares.
        view_count:        Number of views.
    """

    id: str | None = None
    create_time: int | None = None
    cover_image_url: str | None = None
    share_url: str | None = None
    video_description: str | None = None
    duration: int | None = None
    height: int | None = None
    width: int | None = None
    title: str | None = None
    embed_html: str | None = None
    embed_link: str | None = None
    like_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    view_count: int | None = None


class VideoListData(TikTokBaseModel):
    """Paginated response from ``/v2/video/list/``.

    Attributes:
        videos:   List of video objects for the current page.
        cursor:   UTC Unix timestamp (milliseconds) to pass as ``cursor``
                  in the next request to fetch older videos.
        has_more: ``True`` when additional pages are available.
    """

    videos: list[Video]
    cursor: int
    has_more: bool


class VideoQueryData(TikTokBaseModel):
    """Response from ``/v2/video/query/``.

    Attributes:
        videos: Video objects matching the requested IDs.
    """

    videos: list[Video]
