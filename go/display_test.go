package tiktok

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"testing"
)

func TestIterVideos_FollowsCursors(t *testing.T) {
	var pages int
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v2/video/list/" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		var body map[string]any
		_ = json.NewDecoder(r.Body).Decode(&body)
		pages++
		switch pages {
		case 1:
			// First page: no cursor in the body, more available.
			if _, ok := body["cursor"]; ok {
				t.Errorf("first page must not carry a cursor, got %+v", body)
			}
			_, _ = io.WriteString(w, `{"data":{"videos":[{"id":"v1"},{"id":"v2"}],"cursor":100,"has_more":true},"error":{"code":"ok"}}`)
		case 2:
			// Second page: must echo the cursor from page 1, no more pages.
			if body["cursor"].(float64) != 100 {
				t.Errorf("expected cursor=100 on page 2, got %v", body["cursor"])
			}
			_, _ = io.WriteString(w, `{"data":{"videos":[{"id":"v3"}],"cursor":200,"has_more":false},"error":{"code":"ok"}}`)
		default:
			t.Errorf("unexpected extra page request #%d", pages)
		}
	})

	videos, err := c.IterVideos(context.Background(), IterVideosParams{Fields: []string{"id"}})
	if err != nil {
		t.Fatalf("IterVideos: %v", err)
	}
	if pages != 2 {
		t.Fatalf("expected exactly 2 page requests, got %d", pages)
	}
	if len(videos) != 3 {
		t.Fatalf("expected 3 videos, got %d (%+v)", len(videos), videos)
	}
	if videos[0].ID != "v1" || videos[1].ID != "v2" || videos[2].ID != "v3" {
		t.Fatalf("unexpected video order: %+v", videos)
	}
}

func TestIterVideos_RespectsLimit(t *testing.T) {
	var pages int
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		pages++
		// Always report has_more=true so only the Limit can stop the walk.
		_, _ = io.WriteString(w, `{"data":{"videos":[{"id":"a"},{"id":"b"},{"id":"c"}],"cursor":1,"has_more":true},"error":{"code":"ok"}}`)
	})

	videos, err := c.IterVideos(context.Background(), IterVideosParams{Fields: []string{"id"}, Limit: 2})
	if err != nil {
		t.Fatalf("IterVideos: %v", err)
	}
	if len(videos) != 2 {
		t.Fatalf("expected Limit to cap at 2 videos, got %d", len(videos))
	}
	if pages != 1 {
		t.Fatalf("expected the walk to stop after the first page when Limit is reached, got %d pages", pages)
	}
}

func TestIterVideos_RequiresFields(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		t.Error("server must not be called when fields are missing")
	})
	if _, err := c.IterVideos(context.Background(), IterVideosParams{}); err == nil {
		t.Fatal("expected error for missing fields")
	}
}

func TestIterVideos_ContextCancelled(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, `{"data":{"videos":[{"id":"x"}],"cursor":1,"has_more":true},"error":{"code":"ok"}}`)
	})
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // cancel before the call so the ctx.Err() guard trips immediately.
	if _, err := c.IterVideos(ctx, IterVideosParams{Fields: []string{"id"}}); err == nil {
		t.Fatal("expected context cancellation error")
	}
}
