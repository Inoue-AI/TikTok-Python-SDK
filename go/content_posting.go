package tiktok

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"net/http"
	"os"
	"time"
)

// PrivacyLevel enumerates the visibility options for a posted video or photo.
type PrivacyLevel string

const (
	PrivacyPublicToEveryone    PrivacyLevel = "PUBLIC_TO_EVERYONE"
	PrivacyMutualFollowFriends PrivacyLevel = "MUTUAL_FOLLOW_FRIENDS"
	PrivacyFollowerOfCreator   PrivacyLevel = "FOLLOWER_OF_CREATOR"
	PrivacySelfOnly            PrivacyLevel = "SELF_ONLY"
)

// VideoSource enumerates the upload methods for video content.
type VideoSource string

const (
	SourceFileUpload  VideoSource = "FILE_UPLOAD"
	SourcePullFromURL VideoSource = "PULL_FROM_URL"
)

// VideoContentType enumerates the accepted MIME types for video uploads.
type VideoContentType string

const (
	ContentTypeMP4       VideoContentType = "video/mp4"
	ContentTypeQuickTime VideoContentType = "video/quicktime"
	ContentTypeWebM      VideoContentType = "video/webm"
)

// PostStatus enumerates the values returned by the Get Post Status endpoint.
type PostStatus string

const (
	StatusProcessingUpload   PostStatus = "PROCESSING_UPLOAD"
	StatusProcessingDownload PostStatus = "PROCESSING_DOWNLOAD"
	StatusSendToUserInbox    PostStatus = "SEND_TO_USER_INBOX"
	StatusPublishComplete    PostStatus = "PUBLISH_COMPLETE"
	StatusFailed             PostStatus = "FAILED"
)

// DefaultVideoChunkSize is the default per-chunk size for FILE_UPLOAD (10 MB).
// TikTok accepts chunks between 5 MB and 64 MB.
const DefaultVideoChunkSize = 10 * 1024 * 1024

// DefaultPollInterval is the wait between status polls in WaitForPostCompletion.
const DefaultPollInterval = 3 * time.Second

// DefaultPollTimeout is the maximum total wait in WaitForPostCompletion.
const DefaultPollTimeout = 5 * time.Minute

// CreatorInfo is the capability payload returned by the creator-info endpoint.
type CreatorInfo struct {
	CreatorAvatarURL        string         `json:"creator_avatar_url"`
	CreatorUsername         string         `json:"creator_username"`
	CreatorNickname         string         `json:"creator_nickname"`
	PrivacyLevelOptions     []PrivacyLevel `json:"privacy_level_options"`
	CommentDisabled         bool           `json:"comment_disabled"`
	DuetDisabled            bool           `json:"duet_disabled"`
	StitchDisabled          bool           `json:"stitch_disabled"`
	MaxVideoPostDurationSec int            `json:"max_video_post_duration_sec"`
}

// VideoInitResult is the response from the video/inbox init endpoints. UploadURL
// is populated only for the FILE_UPLOAD source.
type VideoInitResult struct {
	PublishID string `json:"publish_id"`
	UploadURL string `json:"upload_url,omitempty"`
}

// PhotoInitResult is the response from the photo-post init endpoint.
type PhotoInitResult struct {
	PublishID string `json:"publish_id"`
}

// PostStatusResult is the response from the status-fetch endpoint. The
// PublicallyAvailablePostID field name mirrors the TikTok API verbatim, which
// misspells "publicly".
type PostStatusResult struct {
	Status                    PostStatus `json:"status"`
	FailReason                string     `json:"fail_reason,omitempty"`
	PublicallyAvailablePostID []int64    `json:"publicaly_available_post_id,omitempty"`
	UploadedBytes             int64      `json:"uploaded_bytes,omitempty"`
	DownloadedBytes           int64      `json:"downloaded_bytes,omitempty"`
}

// PostInfo carries the optional caption/visibility metadata for a video post.
// Pointer fields are omitted from the request when nil, mirroring the Python
// SDK's "only send provided fields" behaviour.
type PostInfo struct {
	PrivacyLevel          PrivacyLevel
	Title                 *string
	DisableDuet           *bool
	DisableStitch         *bool
	DisableComment        *bool
	VideoCoverTimestampMS *int64
	BrandContentToggle    *bool
	BrandOrganicToggle    *bool
	IsAIGC                *bool
}

func (p PostInfo) toMap() map[string]any {
	m := map[string]any{"privacy_level": string(p.PrivacyLevel)}
	if p.Title != nil {
		m["title"] = *p.Title
	}
	if p.DisableDuet != nil {
		m["disable_duet"] = *p.DisableDuet
	}
	if p.DisableStitch != nil {
		m["disable_stitch"] = *p.DisableStitch
	}
	if p.DisableComment != nil {
		m["disable_comment"] = *p.DisableComment
	}
	if p.VideoCoverTimestampMS != nil {
		m["video_cover_timestamp_ms"] = *p.VideoCoverTimestampMS
	}
	if p.BrandContentToggle != nil {
		m["brand_content_toggle"] = *p.BrandContentToggle
	}
	if p.BrandOrganicToggle != nil {
		m["brand_organic_toggle"] = *p.BrandOrganicToggle
	}
	if p.IsAIGC != nil {
		m["is_aigc"] = *p.IsAIGC
	}
	return m
}

// SourceInfo carries the upload source parameters for a video post. For
// SourceFileUpload set VideoSize, ChunkSize and TotalChunkCount; for
// SourcePullFromURL set VideoURL.
type SourceInfo struct {
	Source          VideoSource
	VideoSize       int64
	ChunkSize       int64
	TotalChunkCount int
	VideoURL        string
}

func (s SourceInfo) toMap() (map[string]any, error) {
	switch s.Source {
	case SourceFileUpload:
		if s.VideoSize <= 0 || s.ChunkSize <= 0 || s.TotalChunkCount <= 0 {
			return nil, errors.New("tiktok: FILE_UPLOAD requires VideoSize, ChunkSize and TotalChunkCount")
		}
		return map[string]any{
			"source":            string(s.Source),
			"video_size":        s.VideoSize,
			"chunk_size":        s.ChunkSize,
			"total_chunk_count": s.TotalChunkCount,
		}, nil
	case SourcePullFromURL:
		if s.VideoURL == "" {
			return nil, errors.New("tiktok: PULL_FROM_URL requires VideoURL")
		}
		return map[string]any{
			"source":    string(s.Source),
			"video_url": s.VideoURL,
		}, nil
	default:
		return nil, fmt.Errorf("tiktok: unknown video source %q", s.Source)
	}
}

// QueryCreatorInfo returns capability information about the authenticated
// creator. Inspect the result to determine which privacy levels are available
// before constructing a post.
//
// Scope: video.publish.
func (c *Client) QueryCreatorInfo(ctx context.Context) (*CreatorInfo, error) {
	data, err := c.doJSON(ctx, http.MethodPost, c.baseURL+"/v2/post/publish/creator_info/query/", emptyBody{}, nil)
	if err != nil {
		return nil, err
	}
	out := &CreatorInfo{}
	if err := json.Unmarshal(data, out); err != nil {
		return nil, fmt.Errorf("tiktok: decode creator info: %w", err)
	}
	return out, nil
}

// InitVideoPost initialises a direct video post and obtains a publish ID (and,
// for FILE_UPLOAD, an upload URL).
//
// Scope: video.publish.
func (c *Client) InitVideoPost(ctx context.Context, info PostInfo, source SourceInfo) (*VideoInitResult, error) {
	sourceMap, err := source.toMap()
	if err != nil {
		return nil, err
	}
	body := map[string]any{
		"post_info":   info.toMap(),
		"source_info": sourceMap,
	}
	data, err := c.doJSON(ctx, http.MethodPost, c.baseURL+"/v2/post/publish/video/init/", body, nil)
	if err != nil {
		return nil, err
	}
	out := &VideoInitResult{}
	if err := json.Unmarshal(data, out); err != nil {
		return nil, fmt.Errorf("tiktok: decode video init: %w", err)
	}
	return out, nil
}

// InitInboxVideo initialises an inbox (draft) video upload. No post metadata is
// required; the creator publishes from their TikTok inbox.
//
// Scope: video.upload.
func (c *Client) InitInboxVideo(ctx context.Context, source SourceInfo) (*VideoInitResult, error) {
	sourceMap, err := source.toMap()
	if err != nil {
		return nil, err
	}
	body := map[string]any{"source_info": sourceMap}
	data, err := c.doJSON(ctx, http.MethodPost, c.baseURL+"/v2/post/publish/inbox/video/init/", body, nil)
	if err != nil {
		return nil, err
	}
	out := &VideoInitResult{}
	if err := json.Unmarshal(data, out); err != nil {
		return nil, fmt.Errorf("tiktok: decode inbox init: %w", err)
	}
	return out, nil
}

// UploadVideoChunk uploads a single binary chunk to the pre-signed upload URL
// returned by InitVideoPost / InitInboxVideo.
func (c *Client) UploadVideoChunk(ctx context.Context, uploadURL string, data []byte, startByte, totalBytes int64, contentType VideoContentType) error {
	if uploadURL == "" {
		return errors.New("tiktok: UploadVideoChunk requires a non-empty upload URL")
	}
	endByte := startByte + int64(len(data)) - 1
	contentRange := fmt.Sprintf("bytes %d-%d/%d", startByte, endByte, totalBytes)
	return c.putChunk(ctx, uploadURL, data, string(contentType), contentRange)
}

// UploadVideoFile uploads an entire video file from disk, chunking it
// automatically. content type defaults to video/mp4 and chunkSize defaults to
// DefaultVideoChunkSize when non-positive.
func (c *Client) UploadVideoFile(ctx context.Context, uploadURL, filePath string, contentType VideoContentType, chunkSize int64) error {
	if contentType == "" {
		contentType = ContentTypeMP4
	}
	if chunkSize <= 0 {
		chunkSize = DefaultVideoChunkSize
	}
	f, err := os.Open(filePath) //nolint:gosec // path supplied by the caller, not user input
	if err != nil {
		return fmt.Errorf("tiktok: open %s: %w", filePath, err)
	}
	defer f.Close()

	stat, err := f.Stat()
	if err != nil {
		return fmt.Errorf("tiktok: stat %s: %w", filePath, err)
	}
	totalBytes := stat.Size()

	buf := make([]byte, chunkSize)
	var start int64
	for {
		if err := ctx.Err(); err != nil {
			return err
		}
		n, readErr := f.Read(buf)
		if n > 0 {
			chunk := make([]byte, n)
			copy(chunk, buf[:n])
			if err := c.UploadVideoChunk(ctx, uploadURL, chunk, start, totalBytes, contentType); err != nil {
				return err
			}
			start += int64(n)
		}
		if readErr == io.EOF {
			break
		}
		if readErr != nil {
			return fmt.Errorf("tiktok: read %s: %w", filePath, readErr)
		}
	}
	return nil
}

// PostVideoFromURL direct-posts a video by public URL in a single call.
//
// Scope: video.publish.
func (c *Client) PostVideoFromURL(ctx context.Context, videoURL string, info PostInfo) (*VideoInitResult, error) {
	return c.InitVideoPost(ctx, info, SourceInfo{Source: SourcePullFromURL, VideoURL: videoURL})
}

// PostVideoFromFile direct-posts a video from disk, running the full
// init-then-upload flow. After it returns the post is processing; use
// GetPostStatus / WaitForPostCompletion to monitor it.
//
// Scope: video.publish.
func (c *Client) PostVideoFromFile(ctx context.Context, filePath string, info PostInfo, contentType VideoContentType, chunkSize int64) (*VideoInitResult, error) {
	if chunkSize <= 0 {
		chunkSize = DefaultVideoChunkSize
	}
	stat, err := os.Stat(filePath)
	if err != nil {
		return nil, fmt.Errorf("tiktok: stat %s: %w", filePath, err)
	}
	totalBytes := stat.Size()
	totalChunks := int(math.Ceil(float64(totalBytes) / float64(chunkSize)))

	init, err := c.InitVideoPost(ctx, info, SourceInfo{
		Source:          SourceFileUpload,
		VideoSize:       totalBytes,
		ChunkSize:       chunkSize,
		TotalChunkCount: totalChunks,
	})
	if err != nil {
		return nil, err
	}
	if init.UploadURL == "" {
		return nil, errors.New("tiktok: TikTok did not return an upload_url for FILE_UPLOAD")
	}
	if err := c.UploadVideoFile(ctx, init.UploadURL, filePath, contentType, chunkSize); err != nil {
		return nil, err
	}
	return init, nil
}

// PostPhotosParams configures PostPhotos.
type PostPhotosParams struct {
	PhotoImageURLs  []string     // Public image URLs (1-35).
	PrivacyLevel    PrivacyLevel // Visibility of the post.
	PhotoCoverIndex int          // Zero-based cover index (default 0).
	Title           *string
	Description     *string
	DisableComment  *bool
	AutoAddMusic    *bool
}

// PostPhotos direct-posts a photo carousel.
//
// Scope: video.publish.
func (c *Client) PostPhotos(ctx context.Context, p PostPhotosParams) (*PhotoInitResult, error) {
	if len(p.PhotoImageURLs) == 0 {
		return nil, errors.New("tiktok: PostPhotos requires at least one photo URL")
	}
	postInfo := map[string]any{"privacy_level": string(p.PrivacyLevel)}
	if p.Title != nil {
		postInfo["title"] = *p.Title
	}
	if p.Description != nil {
		postInfo["description"] = *p.Description
	}
	if p.DisableComment != nil {
		postInfo["disable_comment"] = *p.DisableComment
	}
	if p.AutoAddMusic != nil {
		postInfo["auto_add_music"] = *p.AutoAddMusic
	}
	body := map[string]any{
		"post_info": postInfo,
		"source_info": map[string]any{
			"source":            "PULL_FROM_URL",
			"photo_cover_index": p.PhotoCoverIndex,
			"photo_images":      p.PhotoImageURLs,
		},
		"post_mode":  "DIRECT_POST",
		"media_type": "PHOTO",
	}
	data, err := c.doJSON(ctx, http.MethodPost, c.baseURL+"/v2/post/publish/content/init/", body, nil)
	if err != nil {
		return nil, err
	}
	out := &PhotoInitResult{}
	if err := json.Unmarshal(data, out); err != nil {
		return nil, fmt.Errorf("tiktok: decode photo init: %w", err)
	}
	return out, nil
}

// GetPostStatus fetches the current processing status of a publish action.
//
// Scope: video.publish or video.upload.
func (c *Client) GetPostStatus(ctx context.Context, publishID string) (*PostStatusResult, error) {
	if publishID == "" {
		return nil, errors.New("tiktok: GetPostStatus requires a non-empty publish ID")
	}
	body := map[string]any{"publish_id": publishID}
	data, err := c.doJSON(ctx, http.MethodPost, c.baseURL+"/v2/post/publish/status/fetch/", body, nil)
	if err != nil {
		return nil, err
	}
	out := &PostStatusResult{}
	if err := json.Unmarshal(data, out); err != nil {
		return nil, fmt.Errorf("tiktok: decode post status: %w", err)
	}
	return out, nil
}

// WaitForPostCompletion polls GetPostStatus until the post reaches a terminal
// state (PUBLISH_COMPLETE or FAILED), the timeout elapses, or ctx is cancelled.
// pollInterval and timeout default to DefaultPollInterval / DefaultPollTimeout
// when non-positive.
func (c *Client) WaitForPostCompletion(ctx context.Context, publishID string, pollInterval, timeout time.Duration) (*PostStatusResult, error) {
	if pollInterval <= 0 {
		pollInterval = DefaultPollInterval
	}
	if timeout <= 0 {
		timeout = DefaultPollTimeout
	}
	deadlineCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	ticker := time.NewTicker(pollInterval)
	defer ticker.Stop()

	for {
		status, err := c.GetPostStatus(deadlineCtx, publishID)
		if err != nil {
			return nil, err
		}
		if status.Status == StatusPublishComplete || status.Status == StatusFailed {
			return status, nil
		}
		select {
		case <-deadlineCtx.Done():
			return nil, fmt.Errorf("tiktok: post %q did not reach a terminal state: %w", publishID, deadlineCtx.Err())
		case <-ticker.C:
		}
	}
}

// emptyBody marshals to {} so the creator-info endpoint receives a JSON object
// body (it rejects an empty payload).
type emptyBody struct{}

func (emptyBody) MarshalJSON() ([]byte, error) { return []byte("{}"), nil }
