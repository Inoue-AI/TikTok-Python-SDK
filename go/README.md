# TikTok Go SDK

Typed, context-aware Go client for the TikTok Open API.

This SDK lives alongside the Python SDK in the same repository and mirrors the
Python SDK's core surface: the OAuth user-token lifecycle, the Display reads,
the full Content Posting flow (the operation the Inoue AI backend posts TikTok
content through), and account-analytics aggregates.

## Install

```bash
go get github.com/Inoue-AI/Inoue-AI-TikTok-SDK/go@latest
```

## Quickstart

```go
package main

import (
	"context"
	"log"
	"time"

	tiktok "github.com/Inoue-AI/Inoue-AI-TikTok-SDK/go"
)

func main() {
	client := tiktok.New(tiktok.ClientOptions{
		AccessToken: "USER_ACCESS_TOKEN",
		Timeout:     30 * time.Second,
	})
	defer client.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	user, err := client.GetUser(ctx, []string{"open_id", "display_name", "follower_count"})
	if err != nil {
		log.Fatalf("get user: %v", err)
	}
	log.Printf("user %s (%d followers)", user.DisplayName, user.FollowerCount)
}
```

## Methods

### OAuth (application credentials)

| Go function/method | TikTok endpoint | Notes |
|---|---|---|
| `BuildAuthorizationURL(params)` | `www.tiktok.com/v2/auth/authorize/` | No network call; PKCE-aware |
| `ExchangeCode(ctx, params)` | `POST /v2/oauth/token/` | `authorization_code` grant |
| `RefreshAccessToken(ctx, params)` | `POST /v2/oauth/token/` | `refresh_token` grant (rotates) |
| `RevokeAccessToken(ctx, key, secret, token)` | `POST /v2/oauth/revoke/` | Invalidate a grant |

### Display (user-token)

| Go method | TikTok endpoint | Scope |
|---|---|---|
| `GetUser(ctx, fields)` | `GET /v2/user/info/` | `user.info.basic` |
| `ListVideos(ctx, params)` | `POST /v2/video/list/` | `video.list` |
| `IterVideos(ctx, params)` | `POST /v2/video/list/` (auto-paginated) | `video.list` |
| `QueryVideos(ctx, ids, fields)` | `POST /v2/video/query/` | `video.list` |
| `GetVideo(ctx, id, fields)` | `POST /v2/video/query/` | `video.list` |
| `GetAccountAnalytics(ctx, params)` | `user/info` + `video/list` aggregate | `user.info.stats` + `video.list` |

`IterVideos` is the Go equivalent of the Python SDK's `iter_videos` async
generator. Go has no async generators, so it follows the SDK's established
cursor-walking convention and returns the accumulated slice; pass
`IterVideosParams.Limit` to bound the total and the upstream calls.

### Content Posting (user-token)

| Go method | TikTok endpoint | Scope |
|---|---|---|
| `QueryCreatorInfo(ctx)` | `POST /v2/post/publish/creator_info/query/` | `video.publish` |
| `InitVideoPost(ctx, info, source)` | `POST /v2/post/publish/video/init/` | `video.publish` |
| `InitInboxVideo(ctx, source)` | `POST /v2/post/publish/inbox/video/init/` | `video.upload` |
| `UploadVideoChunk(ctx, url, data, start, total, ct)` | `PUT {upload_url}` | — |
| `UploadVideoFile(ctx, url, path, ct, chunkSize)` | `PUT {upload_url}` (auto-chunked) | — |
| `PostVideoFromURL(ctx, url, info)` | `POST /v2/post/publish/video/init/` | `video.publish` |
| `PostVideoFromFile(ctx, path, info, ct, chunkSize)` | init + chunked upload | `video.publish` |
| `PostPhotos(ctx, params)` | `POST /v2/post/publish/content/init/` | `video.publish` |
| `GetPostStatus(ctx, publishID)` | `POST /v2/post/publish/status/fetch/` | `video.publish`/`video.upload` |
| `WaitForPostCompletion(ctx, id, interval, timeout)` | polls status to terminal | — |

`WaitForPostCompletion` polls with a `time.Ticker` and honours both the supplied
`timeout` and `ctx` cancellation — it never busy-waits and never leaks the ticker.

### Data Portability (user-token)

Available only to users in the European Economic Area (EEA) or the United
Kingdom (UK). Calls from other regions are rejected upstream regardless of token
validity, so live verification is region/credentials-gated; the request
construction and response parsing are unit-tested with `httptest`.

| Go method | TikTok endpoint | Notes |
|---|---|---|
| `AddDataRequest(ctx, params)` | `POST /v2/user/data/add/` | Always sends `fields=request_id` |
| `CheckDataRequestStatus(ctx, id, fields)` | `POST /v2/user/data/check/` | `nil` fields requests all status fields |
| `CancelDataRequest(ctx, id)` | `POST /v2/user/data/cancel/` | `request_id` carried as a query param |
| `DownloadData(ctx, id)` | `POST /v2/user/data/download/` | Returns the raw zip archive bytes |

## Operating principles

The Go client is built to the same memory-safety bar as the Inoue AI Go
backend:

- Every method takes `context.Context` first; cancellation propagates to the
  underlying HTTP call.
- Each `*Client` owns one `*http.Client` with an explicit `Timeout`,
  `MaxIdleConnsPerHost`, and `IdleConnTimeout`. `http.DefaultClient` is never
  used.
- `defer client.Close()` releases idle connections.
- All errors from the API surface as `*tiktok.Error` with `StatusCode`, `Code`,
  `Message`, and `LogID` for tracing.

## Errors

```go
out, err := client.GetUser(ctx, fields)
if err != nil {
	if apiErr, ok := tiktok.AsError(err); ok {
		switch {
		case apiErr.IsAuthError():
			// re-authenticate
		case apiErr.IsRateLimited():
			// back off
		case apiErr.IsServerError():
			// retry
		}
	}
	return err
}
```

## Repository layout

The Go SDK lives in the `go/` subdirectory of the repository. The Python SDK
remains under `tiktok/` and is unchanged. See the top-level [README](../README.md)
for the multi-language overview.
