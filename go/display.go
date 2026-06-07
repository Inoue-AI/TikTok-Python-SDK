package tiktok

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strings"
)

// User mirrors the subset of TikTok user fields exposed via /v2/user/info/.
// Fields are populated only if they were requested via the `fields` argument.
type User struct {
	OpenID          string `json:"open_id,omitempty"`
	UnionID         string `json:"union_id,omitempty"`
	AvatarURL       string `json:"avatar_url,omitempty"`
	AvatarURL100    string `json:"avatar_url_100,omitempty"`
	AvatarLargeURL  string `json:"avatar_large_url,omitempty"`
	DisplayName     string `json:"display_name,omitempty"`
	BioDescription  string `json:"bio_description,omitempty"`
	ProfileDeepLink string `json:"profile_deep_link,omitempty"`
	IsVerified      bool   `json:"is_verified,omitempty"`
	Username        string `json:"username,omitempty"`
	FollowerCount   int64  `json:"follower_count,omitempty"`
	FollowingCount  int64  `json:"following_count,omitempty"`
	LikesCount      int64  `json:"likes_count,omitempty"`
	VideoCount      int64  `json:"video_count,omitempty"`
}

// Video mirrors the TikTok video resource fields exposed via /v2/video/list/
// and /v2/video/query/.
type Video struct {
	ID                string   `json:"id,omitempty"`
	CreateTime        int64    `json:"create_time,omitempty"`
	CoverImageURL     string   `json:"cover_image_url,omitempty"`
	ShareURL          string   `json:"share_url,omitempty"`
	VideoDescription  string   `json:"video_description,omitempty"`
	Duration          int64    `json:"duration,omitempty"`
	Height            int64    `json:"height,omitempty"`
	Width             int64    `json:"width,omitempty"`
	Title             string   `json:"title,omitempty"`
	EmbedHTML         string   `json:"embed_html,omitempty"`
	EmbedLink         string   `json:"embed_link,omitempty"`
	LikeCount         int64    `json:"like_count,omitempty"`
	CommentCount      int64    `json:"comment_count,omitempty"`
	ShareCount        int64    `json:"share_count,omitempty"`
	ViewCount         int64    `json:"view_count,omitempty"`
	HashtagNames      []string `json:"hashtag_names,omitempty"`
	VideoLabel        any      `json:"video_label,omitempty"`
	IsPaidPartnership bool     `json:"is_paid_partnership,omitempty"`
}

// VideoListResult is the page wrapper returned by /v2/video/list/.
type VideoListResult struct {
	Videos  []Video `json:"videos"`
	Cursor  int64   `json:"cursor"`
	HasMore bool    `json:"has_more"`
}

// VideoQueryResult is the wrapper returned by /v2/video/query/.
type VideoQueryResult struct {
	Videos []Video `json:"videos"`
}

// GetUser fetches the authenticated user's profile. `fields` must contain at
// least one TikTok user field name (e.g. "open_id", "display_name",
// "follower_count").
//
// Scope: user.info.basic (and user.info.profile / user.info.stats for the
// corresponding fields).
func (c *Client) GetUser(ctx context.Context, fields []string) (*User, error) {
	if len(fields) == 0 {
		return nil, errors.New("tiktok: GetUser requires at least one field")
	}
	q := url.Values{}
	q.Set("fields", strings.Join(fields, ","))

	data, err := c.doJSON(ctx, http.MethodGet, c.baseURL+"/v2/user/info/", nil, q)
	if err != nil {
		return nil, err
	}
	var wrapper struct {
		User User `json:"user"`
	}
	if err := json.Unmarshal(data, &wrapper); err != nil {
		return nil, fmt.Errorf("tiktok: decode user: %w", err)
	}
	return &wrapper.User, nil
}

// ListVideosParams configures a single page request to /v2/video/list/.
type ListVideosParams struct {
	Fields   []string // Required. Video fields to request.
	Cursor   *int64   // Pagination cursor (UTC Unix ms). Nil = first page.
	MaxCount int      // Page size (1-20). Defaults to 20.
}

// ListVideos returns one page of the authenticated user's videos.
//
// Scope: video.list.
func (c *Client) ListVideos(ctx context.Context, p ListVideosParams) (*VideoListResult, error) {
	if len(p.Fields) == 0 {
		return nil, errors.New("tiktok: ListVideos requires at least one field")
	}
	maxCount := p.MaxCount
	if maxCount <= 0 {
		maxCount = 20
	}
	body := map[string]any{"max_count": maxCount}
	if p.Cursor != nil {
		body["cursor"] = *p.Cursor
	}

	q := url.Values{}
	q.Set("fields", strings.Join(p.Fields, ","))

	data, err := c.doJSON(ctx, http.MethodPost, c.baseURL+"/v2/video/list/", body, q)
	if err != nil {
		return nil, err
	}
	out := &VideoListResult{}
	if err := json.Unmarshal(data, out); err != nil {
		return nil, fmt.Errorf("tiktok: decode video list: %w", err)
	}
	return out, nil
}

// IterVideosParams configures IterVideos.
type IterVideosParams struct {
	// Fields is required: the video fields to request on each page.
	Fields []string
	// MaxCount is the per-page size (1-20). Defaults to 20 when non-positive.
	MaxCount int
	// Limit caps the total number of videos returned across all pages. When
	// non-positive, every available video is returned. It bounds memory and
	// upstream calls so the iteration can never run unbounded.
	Limit int
}

// IterVideos returns every video for the authenticated user, automatically
// following pagination cursors until all videos have been collected (or the
// optional Limit is reached). It is the Go equivalent of the Python SDK's
// iter_videos async generator; because Go has no async generators, the SDK
// follows the established cursor-walking convention (see GetAccountAnalytics)
// and returns the accumulated slice.
//
// Each page request honours ctx; cancellation stops the walk and surfaces the
// context error.
//
// Scope: video.list.
func (c *Client) IterVideos(ctx context.Context, p IterVideosParams) ([]Video, error) {
	if len(p.Fields) == 0 {
		return nil, errors.New("tiktok: IterVideos requires at least one field")
	}
	maxCount := p.MaxCount
	if maxCount <= 0 {
		maxCount = 20
	}

	var (
		all    []Video
		cursor *int64
	)
	for {
		if err := ctx.Err(); err != nil {
			return nil, err
		}
		page, err := c.ListVideos(ctx, ListVideosParams{
			Fields:   p.Fields,
			Cursor:   cursor,
			MaxCount: maxCount,
		})
		if err != nil {
			return nil, err
		}
		for i := range page.Videos {
			all = append(all, page.Videos[i])
			if p.Limit > 0 && len(all) >= p.Limit {
				return all, nil
			}
		}
		if !page.HasMore {
			return all, nil
		}
		next := page.Cursor
		cursor = &next
	}
}

// GetVideo fetches metadata for a single video by ID. Convenience wrapper
// around /v2/video/query/ for the common single-video case.
//
// Scope: video.list.
func (c *Client) GetVideo(ctx context.Context, videoID string, fields []string) (*Video, error) {
	if videoID == "" {
		return nil, errors.New("tiktok: GetVideo requires a non-empty video ID")
	}
	out, err := c.QueryVideos(ctx, []string{videoID}, fields)
	if err != nil {
		return nil, err
	}
	if len(out.Videos) == 0 {
		return nil, &Error{Code: "resource_not_found", Message: "video not found", StatusCode: http.StatusNotFound}
	}
	return &out.Videos[0], nil
}

// QueryVideos fetches metadata for a batch of videos by ID (1-20).
//
// Scope: video.list.
func (c *Client) QueryVideos(ctx context.Context, videoIDs []string, fields []string) (*VideoQueryResult, error) {
	if len(videoIDs) == 0 {
		return nil, errors.New("tiktok: QueryVideos requires at least one video ID")
	}
	if len(videoIDs) > 20 {
		return nil, fmt.Errorf("tiktok: QueryVideos accepts at most 20 IDs (%d provided)", len(videoIDs))
	}
	if len(fields) == 0 {
		return nil, errors.New("tiktok: QueryVideos requires at least one field")
	}

	q := url.Values{}
	q.Set("fields", strings.Join(fields, ","))

	body := map[string]any{
		"filters": map[string]any{"video_ids": videoIDs},
	}
	data, err := c.doJSON(ctx, http.MethodPost, c.baseURL+"/v2/video/query/", body, q)
	if err != nil {
		return nil, err
	}
	out := &VideoQueryResult{}
	if err := json.Unmarshal(data, out); err != nil {
		return nil, fmt.Errorf("tiktok: decode video query: %w", err)
	}
	return out, nil
}
