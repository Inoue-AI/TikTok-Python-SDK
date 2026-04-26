package tiktok

import (
	"context"
	"fmt"
	"time"
)

// AccountAnalytics is the aggregated analytics payload for an authenticated
// TikTok account, derived by summarising VideoListResult / video stats. The
// shape mirrors what the Inoue backend stores for cron-driven account stats.
type AccountAnalytics struct {
	OpenID         string    `json:"open_id"`
	WindowStart    time.Time `json:"window_start"`
	WindowEnd      time.Time `json:"window_end"`
	VideoCount     int64     `json:"video_count"`
	ViewCount      int64     `json:"view_count"`
	LikeCount      int64     `json:"like_count"`
	CommentCount   int64     `json:"comment_count"`
	ShareCount     int64     `json:"share_count"`
	FollowerCount  int64     `json:"follower_count"`
	FollowingCount int64     `json:"following_count"`
}

// AccountAnalyticsParams configures GetAccountAnalytics.
type AccountAnalyticsParams struct {
	// Window controls how far back to scan video posts when computing
	// engagement totals. Defaults to 30 days when zero.
	Window time.Duration
	// PageSize controls the per-page video pagination size (1-20). Defaults to 20.
	PageSize int
}

// GetAccountAnalytics returns aggregated stats for the authenticated TikTok
// user by combining /v2/user/info/ (profile counts) with a paginated walk of
// /v2/video/list/ (engagement aggregates).
//
// Scopes: user.info.stats and video.list.
func (c *Client) GetAccountAnalytics(ctx context.Context, p AccountAnalyticsParams) (*AccountAnalytics, error) {
	window := p.Window
	if window <= 0 {
		window = 30 * 24 * time.Hour
	}
	pageSize := p.PageSize
	if pageSize <= 0 {
		pageSize = 20
	}
	now := time.Now().UTC()
	windowStart := now.Add(-window)

	user, err := c.GetUser(ctx, []string{
		"open_id", "follower_count", "following_count", "likes_count", "video_count",
	})
	if err != nil {
		return nil, fmt.Errorf("tiktok: GetAccountAnalytics user: %w", err)
	}

	out := &AccountAnalytics{
		OpenID:         user.OpenID,
		WindowStart:    windowStart,
		WindowEnd:      now,
		FollowerCount:  user.FollowerCount,
		FollowingCount: user.FollowingCount,
	}

	cursor := (*int64)(nil)
	for {
		page, err := c.ListVideos(ctx, ListVideosParams{
			Fields: []string{
				"id", "create_time", "view_count", "like_count",
				"comment_count", "share_count",
			},
			Cursor:   cursor,
			MaxCount: pageSize,
		})
		if err != nil {
			return nil, fmt.Errorf("tiktok: GetAccountAnalytics list page: %w", err)
		}
		stop := false
		for _, v := range page.Videos {
			if v.CreateTime > 0 && time.Unix(v.CreateTime, 0).UTC().Before(windowStart) {
				stop = true
				break
			}
			out.VideoCount++
			out.ViewCount += v.ViewCount
			out.LikeCount += v.LikeCount
			out.CommentCount += v.CommentCount
			out.ShareCount += v.ShareCount
		}
		if stop || !page.HasMore {
			break
		}
		next := page.Cursor
		cursor = &next
	}
	return out, nil
}
