"""SDK-wide constants and configuration defaults."""

TIKTOK_API_BASE_URL = "https://open.tiktokapis.com"

# Default network timeout in seconds for API requests.
DEFAULT_TIMEOUT: float = 30.0

# Default size (in bytes) for each video chunk during FILE_UPLOAD.
# TikTok recommends chunks between 5 MB and 64 MB.
DEFAULT_VIDEO_CHUNK_SIZE: int = 10 * 1024 * 1024  # 10 MB

# Maximum number of video IDs accepted by the query-videos endpoint per call.
VIDEO_QUERY_MAX_IDS: int = 20

# Maximum number of videos returned per page by the list-videos endpoint.
VIDEO_LIST_MAX_COUNT: int = 20

# Maximum number of photo URLs accepted by the photo-post endpoint per call.
PHOTO_POST_MAX_IMAGES: int = 35

# Poll interval (seconds) used by wait_for_post_completion.
DEFAULT_POLL_INTERVAL: float = 3.0

# Maximum total wait time (seconds) used by wait_for_post_completion.
DEFAULT_POLL_TIMEOUT: float = 300.0
