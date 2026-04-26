# TikTok Go SDK

Typed, context-aware Go client for the TikTok Open API.

This SDK lives alongside the Python SDK in the same repository and exposes a
focused subset of the platform: the methods the Inoue AI backend consumes
(account info, video listing/query, account analytics aggregates, and OAuth
token refresh).

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

| Go method | TikTok endpoint | Scope |
|---|---|---|
| `GetUser(ctx, fields)` | `GET /v2/user/info/` | `user.info.basic` |
| `ListVideos(ctx, params)` | `POST /v2/video/list/` | `video.list` |
| `QueryVideos(ctx, ids, fields)` | `POST /v2/video/query/` | `video.list` |
| `GetVideo(ctx, id, fields)` | `POST /v2/video/query/` | `video.list` |
| `GetAccountAnalytics(ctx, params)` | `user/info` + `video/list` aggregate | `user.info.stats` + `video.list` |
| `RefreshAccessToken(ctx, params)` | `POST /v2/oauth/token/` | n/a (app credentials) |

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
