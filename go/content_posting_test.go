package tiktok

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"
)

func TestQueryCreatorInfo_Success(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/v2/post/publish/creator_info/query/" {
			t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		// The endpoint requires a JSON object body, not an empty payload.
		body, _ := io.ReadAll(r.Body)
		if string(body) != "{}" {
			t.Errorf("expected {} body, got %q", body)
		}
		_, _ = io.WriteString(w, `{"data":{"creator_username":"u","creator_nickname":"N","privacy_level_options":["PUBLIC_TO_EVERYONE","SELF_ONLY"],"comment_disabled":false,"duet_disabled":false,"stitch_disabled":true,"max_video_post_duration_sec":60},"error":{"code":"ok"}}`)
	})

	info, err := c.QueryCreatorInfo(context.Background())
	if err != nil {
		t.Fatalf("QueryCreatorInfo: %v", err)
	}
	if info.CreatorUsername != "u" || info.MaxVideoPostDurationSec != 60 || !info.StitchDisabled {
		t.Fatalf("unexpected creator info: %+v", info)
	}
	if len(info.PrivacyLevelOptions) != 2 || info.PrivacyLevelOptions[0] != PrivacyPublicToEveryone {
		t.Fatalf("unexpected privacy options: %+v", info.PrivacyLevelOptions)
	}
}

func TestInitVideoPost_PullFromURL(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v2/post/publish/video/init/" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		src, _ := body["source_info"].(map[string]any)
		if src["source"] != "PULL_FROM_URL" || src["video_url"] != "https://x/v.mp4" {
			t.Errorf("unexpected source_info: %+v", src)
		}
		post, _ := body["post_info"].(map[string]any)
		if post["privacy_level"] != "PUBLIC_TO_EVERYONE" || post["title"] != "hi" {
			t.Errorf("unexpected post_info: %+v", post)
		}
		_, _ = io.WriteString(w, `{"data":{"publish_id":"pub_1"},"error":{"code":"ok"}}`)
	})

	title := "hi"
	out, err := c.InitVideoPost(context.Background(),
		PostInfo{PrivacyLevel: PrivacyPublicToEveryone, Title: &title},
		SourceInfo{Source: SourcePullFromURL, VideoURL: "https://x/v.mp4"},
	)
	if err != nil {
		t.Fatalf("InitVideoPost: %v", err)
	}
	if out.PublishID != "pub_1" || out.UploadURL != "" {
		t.Fatalf("unexpected result: %+v", out)
	}
}

func TestInitVideoPost_FileUploadMissingParams(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		t.Error("server must not be called when FILE_UPLOAD params are missing")
	})
	_, err := c.InitVideoPost(context.Background(),
		PostInfo{PrivacyLevel: PrivacySelfOnly},
		SourceInfo{Source: SourceFileUpload}, // sizes omitted
	)
	if err == nil {
		t.Fatal("expected error for missing FILE_UPLOAD params")
	}
}

func TestPostVideoFromURL_Convenience(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		var body map[string]any
		_ = json.NewDecoder(r.Body).Decode(&body)
		src, _ := body["source_info"].(map[string]any)
		if src["source"] != "PULL_FROM_URL" {
			t.Errorf("expected PULL_FROM_URL, got %+v", src)
		}
		_, _ = io.WriteString(w, `{"data":{"publish_id":"pub_url"},"error":{"code":"ok"}}`)
	})
	out, err := c.PostVideoFromURL(context.Background(), "https://x/v.mp4", PostInfo{PrivacyLevel: PrivacyPublicToEveryone})
	if err != nil {
		t.Fatalf("PostVideoFromURL: %v", err)
	}
	if out.PublishID != "pub_url" {
		t.Fatalf("unexpected publish id: %s", out.PublishID)
	}
}

func TestPostPhotos_Success(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v2/post/publish/content/init/" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		var body map[string]any
		_ = json.NewDecoder(r.Body).Decode(&body)
		if body["media_type"] != "PHOTO" || body["post_mode"] != "DIRECT_POST" {
			t.Errorf("unexpected envelope: %+v", body)
		}
		_, _ = io.WriteString(w, `{"data":{"publish_id":"photo_1"},"error":{"code":"ok"}}`)
	})
	title := "carousel"
	out, err := c.PostPhotos(context.Background(), PostPhotosParams{
		PhotoImageURLs: []string{"https://x/1.jpg", "https://x/2.jpg"},
		PrivacyLevel:   PrivacyPublicToEveryone,
		Title:          &title,
	})
	if err != nil {
		t.Fatalf("PostPhotos: %v", err)
	}
	if out.PublishID != "photo_1" {
		t.Fatalf("unexpected publish id: %s", out.PublishID)
	}
}

func TestPostPhotos_RequiresURLs(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		t.Error("server must not be called when no photo URLs are supplied")
	})
	if _, err := c.PostPhotos(context.Background(), PostPhotosParams{PrivacyLevel: PrivacySelfOnly}); err == nil {
		t.Fatal("expected error for empty photo URLs")
	}
}

func TestGetPostStatus_Failed(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, `{"data":{"status":"FAILED","fail_reason":"duration_check_failed"},"error":{"code":"ok"}}`)
	})
	out, err := c.GetPostStatus(context.Background(), "pub_x")
	if err != nil {
		t.Fatalf("GetPostStatus: %v", err)
	}
	if out.Status != StatusFailed || out.FailReason != "duration_check_failed" {
		t.Fatalf("unexpected status: %+v", out)
	}
}

func TestUploadVideoFile_ChunksWithCorrectRanges(t *testing.T) {
	var (
		mu     sync.Mutex
		ranges []string
	)
	c, srv := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPut {
			t.Errorf("expected PUT, got %s", r.Method)
		}
		mu.Lock()
		ranges = append(ranges, r.Header.Get("Content-Range"))
		mu.Unlock()
		_, _ = io.Copy(io.Discard, r.Body)
		w.WriteHeader(http.StatusOK)
	})

	// 25-byte file, 10-byte chunks => 3 chunks (10 + 10 + 5).
	dir := t.TempDir()
	fp := filepath.Join(dir, "clip.mp4")
	if err := os.WriteFile(fp, []byte("X23456789Y23456789Z2345"), 0o600); err != nil {
		t.Fatalf("write temp file: %v", err)
	}

	if err := c.UploadVideoFile(context.Background(), srv.URL+"/upload/", fp, ContentTypeMP4, 10); err != nil {
		t.Fatalf("UploadVideoFile: %v", err)
	}

	want := []string{"bytes 0-9/23", "bytes 10-19/23", "bytes 20-22/23"}
	mu.Lock()
	defer mu.Unlock()
	if len(ranges) != len(want) {
		t.Fatalf("expected %d chunks, got %d (%v)", len(want), len(ranges), ranges)
	}
	for i := range want {
		if ranges[i] != want[i] {
			t.Errorf("chunk %d: want %q, got %q", i, want[i], ranges[i])
		}
	}
}

func TestUploadVideoChunk_FailureSurfacesError(t *testing.T) {
	c, srv := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	})
	err := c.UploadVideoChunk(context.Background(), srv.URL+"/upload/", []byte("abc"), 0, 3, ContentTypeMP4)
	apiErr, ok := AsError(err)
	if !ok || apiErr.StatusCode != http.StatusInternalServerError {
		t.Fatalf("expected upload error with 500, got %v", err)
	}
}

func TestWaitForPostCompletion_PollsUntilTerminal(t *testing.T) {
	var calls int32
	mu := &sync.Mutex{}
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		calls++
		n := calls
		mu.Unlock()
		if n < 2 {
			_, _ = io.WriteString(w, `{"data":{"status":"PROCESSING_UPLOAD"},"error":{"code":"ok"}}`)
			return
		}
		_, _ = io.WriteString(w, `{"data":{"status":"PUBLISH_COMPLETE","publicaly_available_post_id":[7000]},"error":{"code":"ok"}}`)
	})

	out, err := c.WaitForPostCompletion(context.Background(), "pub_x", time.Millisecond, time.Second)
	if err != nil {
		t.Fatalf("WaitForPostCompletion: %v", err)
	}
	if out.Status != StatusPublishComplete || len(out.PublicallyAvailablePostID) != 1 || out.PublicallyAvailablePostID[0] != 7000 {
		t.Fatalf("unexpected terminal status: %+v", out)
	}
}

func TestWaitForPostCompletion_Timeout(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, `{"data":{"status":"PROCESSING_UPLOAD"},"error":{"code":"ok"}}`)
	})
	_, err := c.WaitForPostCompletion(context.Background(), "pub_y", 5*time.Millisecond, 15*time.Millisecond)
	if err == nil {
		t.Fatal("expected timeout error")
	}
}
