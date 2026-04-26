package tiktok

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func newTestClient(t *testing.T, handler http.HandlerFunc) (*Client, *httptest.Server) {
	t.Helper()
	srv := httptest.NewServer(handler)
	t.Cleanup(srv.Close)
	c := New(ClientOptions{
		AccessToken: "test-token",
		BaseURL:     srv.URL,
		Timeout:     5 * time.Second,
	})
	t.Cleanup(func() { _ = c.Close() })
	return c, srv
}

func TestNew_DefaultsHTTPClient(t *testing.T) {
	c := New(ClientOptions{AccessToken: "x"})
	defer c.Close()
	if c.HTTPClient() == http.DefaultClient {
		t.Fatal("New must NOT reuse http.DefaultClient")
	}
	if c.HTTPClient().Timeout == 0 {
		t.Fatal("New must set an explicit Timeout on the http.Client")
	}
	tr, ok := c.HTTPClient().Transport.(*http.Transport)
	if !ok {
		t.Fatalf("expected *http.Transport, got %T", c.HTTPClient().Transport)
	}
	if tr.MaxIdleConnsPerHost == 0 {
		t.Fatal("Transport must set MaxIdleConnsPerHost")
	}
	if tr.IdleConnTimeout == 0 {
		t.Fatal("Transport must set IdleConnTimeout")
	}
}

func TestNew_CustomHTTPClientNotMutated(t *testing.T) {
	custom := &http.Client{Timeout: 1 * time.Second}
	c := New(ClientOptions{AccessToken: "x", HTTPClient: custom})
	defer c.Close()
	if c.HTTPClient() != custom {
		t.Fatal("custom HTTPClient should be reused as-is")
	}
}

func TestGetUser_Success(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			t.Errorf("expected GET, got %s", r.Method)
		}
		if r.URL.Path != "/v2/user/info/" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		if got := r.URL.Query().Get("fields"); got != "open_id,display_name,follower_count" {
			t.Errorf("unexpected fields query: %s", got)
		}
		if got := r.Header.Get("Authorization"); got != "Bearer test-token" {
			t.Errorf("missing/incorrect auth header: %q", got)
		}
		_, _ = io.WriteString(w, `{"data":{"user":{"open_id":"abc","display_name":"Alice","follower_count":42}},"error":{"code":"ok","message":"","log_id":"L"}}`)
	})

	user, err := c.GetUser(context.Background(), []string{"open_id", "display_name", "follower_count"})
	if err != nil {
		t.Fatalf("GetUser failed: %v", err)
	}
	if user.OpenID != "abc" || user.DisplayName != "Alice" || user.FollowerCount != 42 {
		t.Fatalf("unexpected user: %+v", user)
	}
}

func TestGetUser_RequiresFields(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		t.Error("server must not be called when fields are missing")
	})
	if _, err := c.GetUser(context.Background(), nil); err == nil {
		t.Fatal("expected error for missing fields")
	}
}

func TestGetUser_APIError(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = io.WriteString(w, `{"data":{},"error":{"code":"access_token_invalid","message":"bad token","log_id":"X"}}`)
	})
	_, err := c.GetUser(context.Background(), []string{"open_id"})
	if err == nil {
		t.Fatal("expected error")
	}
	apiErr, ok := AsError(err)
	if !ok {
		t.Fatalf("expected *tiktok.Error, got %T: %v", err, err)
	}
	if !apiErr.IsAuthError() {
		t.Fatalf("expected IsAuthError, got %+v", apiErr)
	}
	if apiErr.StatusCode != http.StatusUnauthorized {
		t.Fatalf("unexpected status code: %d", apiErr.StatusCode)
	}
	if apiErr.LogID != "X" {
		t.Fatalf("expected LogID propagated, got %q", apiErr.LogID)
	}
}

func TestListVideos_PassesCursorAndPageSize(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("expected POST, got %s", r.Method)
		}
		if r.URL.Path != "/v2/video/list/" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("body decode: %v", err)
		}
		if body["max_count"].(float64) != 5 {
			t.Errorf("expected max_count=5, got %v", body["max_count"])
		}
		if body["cursor"].(float64) != 12345 {
			t.Errorf("expected cursor=12345, got %v", body["cursor"])
		}
		_, _ = io.WriteString(w, `{"data":{"videos":[{"id":"v1","view_count":10}],"cursor":99,"has_more":false},"error":{"code":"ok"}}`)
	})

	cursor := int64(12345)
	page, err := c.ListVideos(context.Background(), ListVideosParams{
		Fields:   []string{"id", "view_count"},
		Cursor:   &cursor,
		MaxCount: 5,
	})
	if err != nil {
		t.Fatalf("ListVideos: %v", err)
	}
	if len(page.Videos) != 1 || page.Videos[0].ID != "v1" {
		t.Fatalf("unexpected videos: %+v", page.Videos)
	}
	if page.Cursor != 99 || page.HasMore {
		t.Fatalf("unexpected cursor/hasMore: %+v", page)
	}
}

func TestQueryVideos_LimitsBatch(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		t.Error("server must not be called when batch is too large")
	})
	ids := make([]string, 21)
	for i := range ids {
		ids[i] = "x"
	}
	if _, err := c.QueryVideos(context.Background(), ids, []string{"id"}); err == nil {
		t.Fatal("expected error for >20 IDs")
	}
}

func TestGetVideo_NotFound(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, `{"data":{"videos":[]},"error":{"code":"ok"}}`)
	})
	_, err := c.GetVideo(context.Background(), "nope", []string{"id"})
	apiErr, ok := AsError(err)
	if !ok || apiErr.Code != "resource_not_found" {
		t.Fatalf("expected resource_not_found, got %v", err)
	}
}

func TestRefreshAccessToken_Success(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/v2/oauth/token/" {
			t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		ct := r.Header.Get("Content-Type")
		if !strings.HasPrefix(ct, "application/x-www-form-urlencoded") {
			t.Errorf("expected form content type, got %q", ct)
		}
		body, _ := io.ReadAll(r.Body)
		if !strings.Contains(string(body), "refresh_token=R") || !strings.Contains(string(body), "grant_type=refresh_token") {
			t.Errorf("body missing required form fields: %s", body)
		}
		_, _ = io.WriteString(w, `{"access_token":"NEW","refresh_token":"NEXT","expires_in":3600,"refresh_expires_in":7200,"open_id":"o1","scope":"user.info.basic","token_type":"Bearer"}`)
	})
	out, err := c.RefreshAccessToken(context.Background(), RefreshTokenParams{
		ClientKey:    "K",
		ClientSecret: "S",
		RefreshToken: "R",
	})
	if err != nil {
		t.Fatalf("RefreshAccessToken: %v", err)
	}
	if out.AccessToken != "NEW" || out.RefreshToken != "NEXT" || out.ExpiresIn != 3600 {
		t.Fatalf("unexpected refresh result: %+v", out)
	}
}

func TestRefreshAccessToken_OAuthError(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		_, _ = io.WriteString(w, `{"error":"invalid_request","error_description":"missing refresh_token","log_id":"L"}`)
	})
	_, err := c.RefreshAccessToken(context.Background(), RefreshTokenParams{
		ClientKey: "K", ClientSecret: "S", RefreshToken: "R",
	})
	apiErr, ok := AsError(err)
	if !ok {
		t.Fatalf("expected *Error, got %v", err)
	}
	if apiErr.Code != "invalid_request" || apiErr.StatusCode != http.StatusBadRequest {
		t.Fatalf("unexpected oauth error: %+v", apiErr)
	}
}

func TestGetAccountAnalytics_AggregatesAndStopsOnWindow(t *testing.T) {
	now := time.Now().UTC()
	old := now.Add(-90 * 24 * time.Hour).Unix()
	recent := now.Add(-1 * 24 * time.Hour).Unix()
	calls := 0
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		calls++
		switch r.URL.Path {
		case "/v2/user/info/":
			_, _ = io.WriteString(w, `{"data":{"user":{"open_id":"o","follower_count":1000,"following_count":50}},"error":{"code":"ok"}}`)
		case "/v2/video/list/":
			_, _ = io.WriteString(w, `{"data":{"videos":[`+
				`{"id":"v1","create_time":`+jsonInt(recent)+`,"view_count":10,"like_count":2,"comment_count":1,"share_count":0},`+
				`{"id":"v2","create_time":`+jsonInt(old)+`,"view_count":999,"like_count":999,"comment_count":999,"share_count":999}`+
				`],"cursor":0,"has_more":false},"error":{"code":"ok"}}`)
		default:
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
	})
	out, err := c.GetAccountAnalytics(context.Background(), AccountAnalyticsParams{Window: 30 * 24 * time.Hour})
	if err != nil {
		t.Fatalf("GetAccountAnalytics: %v", err)
	}
	if out.VideoCount != 1 || out.ViewCount != 10 || out.LikeCount != 2 {
		t.Fatalf("expected only the recent video to be counted, got %+v", out)
	}
	if out.FollowerCount != 1000 {
		t.Fatalf("expected follower count from user info, got %d", out.FollowerCount)
	}
	if calls < 2 {
		t.Fatalf("expected at least 2 HTTP calls, got %d", calls)
	}
}

func TestDoJSON_RequiresAccessToken(t *testing.T) {
	c := New(ClientOptions{}) // no token
	defer c.Close()
	_, err := c.GetUser(context.Background(), []string{"open_id"})
	if err == nil || !strings.Contains(err.Error(), "access token") {
		t.Fatalf("expected access-token error, got %v", err)
	}
}

func TestErrorTypes(t *testing.T) {
	e := &Error{StatusCode: 503, Code: "internal_error"}
	if !e.IsServerError() {
		t.Fatal("expected IsServerError")
	}
	rl := &Error{Code: "rate_limit_exceeded"}
	if !rl.IsRateLimited() {
		t.Fatal("expected IsRateLimited")
	}
	wrapped := errors.New("wrapped: " + e.Error())
	if _, ok := AsError(wrapped); ok {
		t.Fatal("plain error should not unwrap to *Error")
	}
}

func jsonInt(v int64) string {
	b, _ := json.Marshal(v)
	return string(b)
}
