# Inoue-AI TikTok SDK

Multi-language SDK for the TikTok Open API. This repository ships both a
Python client (under `tiktok/`) and a Go client (under `go/`).

> **Note:** This repository was renamed from `Inoue-AI/TikTok-Python-SDK` to
> `Inoue-AI/Inoue-AI-TikTok-SDK`. GitHub auto-redirects the old URL, so
> existing `pip install ... @ git+https://github.com/Inoue-AI/TikTok-Python-SDK.git`
> commands continue to work. The local clone keeps the legacy directory name.

## Python

The Python source remains under [`tiktok/`](./tiktok). Install:

```bash
pip install "git+https://github.com/Inoue-AI/Inoue-AI-TikTok-SDK.git"
```

See the original Python documentation below.

## Go

The Go SDK lives under [`go/`](./go). It exposes a focused subset matching
the calls the Inoue AI Go backend makes (account info, video list/query,
account analytics aggregates, OAuth token refresh). Every method is
context-aware and the underlying `*http.Client` is bounded.

```bash
go get github.com/Inoue-AI/Inoue-AI-TikTok-SDK/go@latest
```

```go
client := tiktok.New(tiktok.ClientOptions{AccessToken: "..."})
defer client.Close()
user, err := client.GetUser(ctx, []string{"open_id", "display_name"})
```

See [`go/README.md`](./go/README.md) for the full Go API.

---

## Original Python SDK

An async Python SDK for TikTok's **Content Posting API**, **Display API**, and **Data Portability API**.

[![CI](https://github.com/inoue-ai/tiktok-python-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/inoue-ai/tiktok-python-sdk/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/tiktok-python-sdk)](https://pypi.org/project/tiktok-python-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/tiktok-python-sdk)](https://pypi.org/project/tiktok-python-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Features

- **Fully async** — built on `aiohttp` with an `asyncio`-native interface
- **Typed responses** — every API response is a frozen Pydantic v2 model
- **Three API namespaces** — `client.content_posting`, `client.display`, `client.data_portability`
- **Convenience helpers** — upload files from disk, poll for post completion, paginate videos automatically
- **Clean exception hierarchy** — catch broad or specific errors as needed
- **Docker support** — multi-stage Dockerfile for dev and prod environments

## Requirements

- Python ≥ 3.11
- A TikTok developer account with a registered app
- A valid user access token (OAuth 2.0 handled externally)

## Installation

```bash
pip install tiktok-python-sdk
```

## Quick start

```python
import asyncio
from tiktok import TikTokClient, UserField, VideoField, PrivacyLevel

async def main() -> None:
    async with TikTokClient(access_token="act.your_token_here") as client:

        # --- Display API ---
        user = await client.display.get_user_info(
            fields=[UserField.DISPLAY_NAME, UserField.FOLLOWER_COUNT, UserField.VIDEO_COUNT]
        )
        print(f"{user.display_name} has {user.follower_count:,} followers")

        # Paginate through all videos
        async for video in client.display.iter_videos(
            fields=[VideoField.ID, VideoField.TITLE, VideoField.VIEW_COUNT]
        ):
            print(video.id, video.title, video.view_count)

        # --- Content Posting API ---
        creator = await client.content_posting.query_creator_info()
        print(f"Max video duration: {creator.max_video_post_duration_sec}s")

        # Post a video by URL
        init = await client.content_posting.post_video_from_url(
            "https://example.com/my-video.mp4",
            privacy_level=PrivacyLevel.PUBLIC_TO_EVERYONE,
            title="Posted via TikTok Python SDK #python #dev",
        )

        # Poll until the post is live (or failed)
        status = await client.content_posting.wait_for_post_completion(init.publish_id)
        print(status.status, status.publicaly_available_post_id)

asyncio.run(main())
```

## API reference

### `TikTokClient`

```python
TikTokClient(access_token: str, *, timeout: float = 30.0)
```

The main client.  Use as an async context manager or call `await client.aclose()` manually.

---

### `client.content_posting` — Content Posting API

| Method | Description |
|--------|-------------|
| `query_creator_info()` | Creator capabilities and privacy options |
| `init_video_post(...)` | Initialise a direct video post (returns `publish_id` + optional `upload_url`) |
| `init_inbox_video(...)` | Initialise an inbox/draft video upload |
| `upload_video_chunk(upload_url, data, ...)` | Upload one binary chunk |
| `upload_video_file(upload_url, file_path, ...)` | Upload a full file from disk, auto-chunked |
| `post_video_from_url(video_url, ...)` | Convenience: direct-post a video by URL |
| `post_video_from_file(file_path, ...)` | Convenience: direct-post a video from disk |
| `post_photos(photo_image_urls, ...)` | Post a photo carousel |
| `get_post_status(publish_id)` | Fetch current publish status |
| `wait_for_post_completion(publish_id, ...)` | Poll until terminal state |

#### Privacy levels

```python
class PrivacyLevel(str, Enum):
    PUBLIC_TO_EVERYONE    = "PUBLIC_TO_EVERYONE"
    MUTUAL_FOLLOW_FRIENDS = "MUTUAL_FOLLOW_FRIENDS"
    FOLLOWER_OF_CREATOR   = "FOLLOWER_OF_CREATOR"
    SELF_ONLY             = "SELF_ONLY"
```

#### Post status values

```python
class PostStatus(str, Enum):
    PROCESSING_UPLOAD    = "PROCESSING_UPLOAD"
    PROCESSING_DOWNLOAD  = "PROCESSING_DOWNLOAD"
    SEND_TO_USER_INBOX   = "SEND_TO_USER_INBOX"
    PUBLISH_COMPLETE     = "PUBLISH_COMPLETE"
    FAILED               = "FAILED"
```

---

### `client.display` — Display API

| Method | Description |
|--------|-------------|
| `get_user_info(fields)` | Authenticated user's profile |
| `list_videos(fields, *, cursor, max_count)` | One page of the user's videos |
| `iter_videos(fields, ...)` | Async iterator over all videos (auto-paginates) |
| `query_videos(video_ids, fields)` | Fetch specific videos by ID (max 20) |

#### Available user fields (`UserField`)

`OPEN_ID`, `UNION_ID`, `AVATAR_URL`, `AVATAR_URL_100`, `AVATAR_LARGE_URL`,
`DISPLAY_NAME`, `BIO_DESCRIPTION`, `PROFILE_DEEP_LINK`, `IS_VERIFIED`,
`USERNAME`, `FOLLOWER_COUNT`, `FOLLOWING_COUNT`, `LIKES_COUNT`, `VIDEO_COUNT`

#### Available video fields (`VideoField`)

`ID`, `CREATE_TIME`, `COVER_IMAGE_URL`, `SHARE_URL`, `VIDEO_DESCRIPTION`,
`DURATION`, `HEIGHT`, `WIDTH`, `TITLE`, `EMBED_HTML`, `EMBED_LINK`,
`LIKE_COUNT`, `COMMENT_COUNT`, `SHARE_COUNT`, `VIEW_COUNT`

---

### `client.data_portability` — Data Portability API

> Available only to TikTok users in the **EEA** or **UK**.

| Method | Description |
|--------|-------------|
| `add_data_request(data_format, category_selection_list)` | Start a new export |
| `check_data_request_status(request_id, *, fields)` | Check export progress |
| `cancel_data_request(request_id)` | Cancel a pending export |
| `download_data(request_id)` | Download the zip archive as `bytes` |

#### Data categories (`DataCategory`)

`ALL_DATA`, `ACTIVITY`, `VIDEO`, `PROFILE`, `DIRECT_MESSAGE`

---

### Exception hierarchy

```
TikTokSDKError
├── TikTokAPIError          ← non-OK error code from the platform
│   ├── TikTokAuthError     ← invalid / expired token, missing scope
│   ├── TikTokRateLimitError
│   ├── TikTokNotFoundError
│   └── TikTokServerError   ← 5xx from TikTok
├── TikTokUploadError       ← chunk or download transport failure
└── TikTokConfigError       ← SDK misconfiguration (e.g. empty token)
```

```python
from tiktok import TikTokAuthError, TikTokRateLimitError, TikTokAPIError

try:
    user = await client.display.get_user_info(fields=[UserField.DISPLAY_NAME])
except TikTokAuthError as e:
    print(f"Auth failed: {e.code} — {e.message}")
except TikTokRateLimitError:
    print("Rate limited, back off and retry.")
except TikTokAPIError as e:
    print(f"API error {e.code}: {e.message} (log_id={e.log_id})")
```

## Development

```bash
# Clone and install with dev extras
git clone https://github.com/inoue-ai/tiktok-python-sdk.git
cd tiktok-python-sdk
pip install -e ".[dev]"

# Run tests
pytest

# Lint and format
ruff check .
ruff format .

# Type-check
mypy tiktok/
```

### Docker

```bash
# Build the dev image
docker build --target dev -t tiktok-sdk:dev .

# Run tests in Docker
docker compose run test

# Run lint in Docker
docker compose run lint

# Run mypy in Docker
docker compose run typecheck
```

## Authentication

This SDK does **not** implement the TikTok OAuth 2.0 flow.  Obtain an access
token externally (e.g. via your web server or the TikTok Developer Portal) and
pass it to `TikTokClient`.  Token refresh must also be handled externally.

Required OAuth scopes per feature:

| Feature | Scopes |
|---------|--------|
| Query creator info | `video.publish` |
| Direct post video | `video.publish` |
| Inbox/draft video | `video.upload` |
| Post photos | `video.publish` |
| Display — user info (basic) | `user.info.basic` |
| Display — user info (profile) | `user.info.profile` |
| Display — user stats | `user.info.stats` |
| Display — video list/query | `video.list` |
| Data Portability | `portability.<category>.single` or `.ongoing` |

## License

[MIT](LICENSE)
