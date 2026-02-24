"""Pydantic models for the TikTok Content Posting API responses.

Reference: https://developers.tiktok.com/doc/content-posting-api-get-started
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from tiktok.models.base import TikTokBaseModel

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PrivacyLevel(StrEnum):
    """Visibility options for a posted video or photo."""

    PUBLIC_TO_EVERYONE = "PUBLIC_TO_EVERYONE"
    MUTUAL_FOLLOW_FRIENDS = "MUTUAL_FOLLOW_FRIENDS"
    FOLLOWER_OF_CREATOR = "FOLLOWER_OF_CREATOR"
    SELF_ONLY = "SELF_ONLY"


class VideoSource(StrEnum):
    """Source type for video content uploads."""

    FILE_UPLOAD = "FILE_UPLOAD"
    PULL_FROM_URL = "PULL_FROM_URL"


class VideoContentType(StrEnum):
    """Accepted MIME types for video file uploads."""

    MP4 = "video/mp4"
    QUICKTIME = "video/quicktime"
    WEBM = "video/webm"


class PostStatus(StrEnum):
    """Status values returned by the Get Post Status endpoint."""

    PROCESSING_UPLOAD = "PROCESSING_UPLOAD"
    PROCESSING_DOWNLOAD = "PROCESSING_DOWNLOAD"
    SEND_TO_USER_INBOX = "SEND_TO_USER_INBOX"
    PUBLISH_COMPLETE = "PUBLISH_COMPLETE"
    FAILED = "FAILED"


class FailReason(StrEnum):
    """Failure reasons returned when ``PostStatus.FAILED`` is set."""

    FILE_FORMAT_CHECK_FAILED = "file_format_check_failed"
    DURATION_CHECK_FAILED = "duration_check_failed"
    FRAME_RATE_CHECK_FAILED = "frame_rate_check_failed"
    PICTURE_SIZE_CHECK_FAILED = "picture_size_check_failed"
    INTERNAL = "internal"
    VIDEO_PULL_FAILED = "video_pull_failed"
    PHOTO_PULL_FAILED = "photo_pull_failed"
    PUBLISH_CANCELLED = "publish_cancelled"
    AUTH_REMOVED = "auth_removed"
    SPAM_RISK_TOO_MANY_POSTS = "spam_risk_too_many_posts"
    SPAM_RISK_USER_BANNED_FROM_POSTING = "spam_risk_user_banned_from_posting"
    SPAM_RISK_TEXT = "spam_risk_text"
    SPAM_RISK = "spam_risk"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class CreatorInfo(TikTokBaseModel):
    """Creator information returned by ``/v2/post/publish/creator_info/query/``.

    Attributes:
        creator_avatar_url:        CDN URL of the creator's avatar image.
        creator_username:          Creator's TikTok username (``@handle``).
        creator_nickname:          Creator's display name.
        privacy_level_options:     Visibility levels available to this creator.
        comment_disabled:          Whether comments are disabled by default.
        duet_disabled:             Whether duets are disabled by default.
        stitch_disabled:           Whether stitches are disabled by default.
        max_video_post_duration_sec: Maximum allowed video length in seconds.
    """

    creator_avatar_url: str
    creator_username: str
    creator_nickname: str
    privacy_level_options: list[PrivacyLevel]
    comment_disabled: bool
    duet_disabled: bool
    stitch_disabled: bool
    max_video_post_duration_sec: int


class VideoInitData(TikTokBaseModel):
    """Response data from video initialisation endpoints.

    Returned by both
    ``/v2/post/publish/video/init/`` (direct post) and
    ``/v2/post/publish/inbox/video/init/`` (inbox / draft).

    Attributes:
        publish_id:  Opaque identifier used to track the post lifecycle.
        upload_url:  Pre-signed PUT URL for ``FILE_UPLOAD`` source type.
                     ``None`` when ``source`` is ``PULL_FROM_URL``.
    """

    publish_id: str
    upload_url: str | None = None


class PhotoInitData(TikTokBaseModel):
    """Response data from ``/v2/post/publish/content/init/`` (photo post).

    Attributes:
        publish_id: Opaque identifier used to track the post lifecycle.
    """

    publish_id: str


class PostStatusData(TikTokBaseModel):
    """Response data from ``/v2/post/publish/status/fetch/``.

    Attributes:
        status:
            Current processing state of the publish action.
        fail_reason:
            Populated only when ``status`` is ``PostStatus.FAILED``.
        publicaly_available_post_id:
            List of public post IDs (note: field name matches the API,
            which contains a typo of "publicly").  Only populated for
            public posts after moderation has completed.
        uploaded_bytes:
            Bytes uploaded so far (``FILE_UPLOAD`` only).
        downloaded_bytes:
            Bytes downloaded so far (``PULL_FROM_URL`` only).
    """

    status: PostStatus
    fail_reason: FailReason | None = None
    # Field name mirrors the TikTok API verbatim (typo in the official spec).
    publicaly_available_post_id: list[int] = Field(default_factory=list)
    uploaded_bytes: int | None = None
    downloaded_bytes: int | None = None
