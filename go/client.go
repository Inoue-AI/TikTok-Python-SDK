package tiktok

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// DefaultBaseURL is the production TikTok Open API root.
const DefaultBaseURL = "https://open.tiktokapis.com"

// DefaultTimeout is the per-request timeout used when ClientOptions.Timeout
// is zero. 30s matches the Python SDK default.
const DefaultTimeout = 30 * time.Second

// ClientOptions configures a *Client created via New.
//
// All fields are optional except AccessToken when the client will be used to
// call user-scoped endpoints. RefreshAccessToken does NOT require AccessToken.
type ClientOptions struct {
	// AccessToken is the TikTok user access token (required for user-scoped
	// endpoints; not required for RefreshAccessToken).
	AccessToken string

	// BaseURL overrides the production TikTok API host. Useful for testing.
	BaseURL string

	// Timeout sets the per-request total timeout. Defaults to DefaultTimeout.
	Timeout time.Duration

	// HTTPClient lets callers inject a fully configured *http.Client. When
	// nil, New constructs a client with bounded idle connections, an explicit
	// Timeout, and an IdleConnTimeout. The package never falls back to
	// http.DefaultClient.
	HTTPClient *http.Client

	// UserAgent overrides the User-Agent header. Defaults to "inoue-tiktok-sdk-go/1".
	UserAgent string
}

// Client is the TikTok API client. It is safe for concurrent use by multiple
// goroutines. Callers must invoke Close (or use defer client.Close()) when the
// client is no longer needed so that idle TCP connections are released.
type Client struct {
	httpClient  *http.Client
	baseURL     string
	accessToken string
	userAgent   string
	ownsHTTP    bool // true when New created the *http.Client (so Close may shut it down).
}

// New constructs a *Client with the supplied options.
func New(opts ClientOptions) *Client {
	timeout := opts.Timeout
	if timeout <= 0 {
		timeout = DefaultTimeout
	}
	baseURL := strings.TrimRight(opts.BaseURL, "/")
	if baseURL == "" {
		baseURL = DefaultBaseURL
	}
	ua := opts.UserAgent
	if ua == "" {
		ua = "inoue-tiktok-sdk-go/1"
	}
	c := &Client{
		baseURL:     baseURL,
		accessToken: opts.AccessToken,
		userAgent:   ua,
	}
	if opts.HTTPClient != nil {
		c.httpClient = opts.HTTPClient
		c.ownsHTTP = false
	} else {
		c.httpClient = &http.Client{
			Timeout: timeout,
			Transport: &http.Transport{
				MaxIdleConns:          100,
				MaxIdleConnsPerHost:   20,
				IdleConnTimeout:       90 * time.Second,
				TLSHandshakeTimeout:   10 * time.Second,
				ExpectContinueTimeout: 1 * time.Second,
				ResponseHeaderTimeout: timeout,
			},
		}
		c.ownsHTTP = true
	}
	return c
}

// Close releases any idle TCP connections held by the underlying *http.Client.
// It is safe to call multiple times. If the caller injected their own
// *http.Client via ClientOptions.HTTPClient, Close is a no-op for that client.
func (c *Client) Close() error {
	if c == nil || c.httpClient == nil {
		return nil
	}
	if c.ownsHTTP {
		if t, ok := c.httpClient.Transport.(*http.Transport); ok {
			t.CloseIdleConnections()
		}
	}
	return nil
}

// HTTPClient returns the underlying *http.Client. Exposed for advanced
// instrumentation only; callers should not mutate the returned client.
func (c *Client) HTTPClient() *http.Client { return c.httpClient }

// envelope mirrors the wrapper TikTok always returns:
//
//	{ "data": {...}, "error": { "code": "ok", "message": "", "log_id": "..." } }
type envelope struct {
	Data  json.RawMessage `json:"data"`
	Error errorPayload    `json:"error"`
}

type errorPayload struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	LogID   string `json:"log_id"`
}

// doJSON executes an authenticated request that expects a JSON envelope
// response. The decoded "data" payload is returned as raw bytes so the caller
// can validate it into the appropriate model.
func (c *Client) doJSON(ctx context.Context, method, fullURL string, body any, query url.Values) (json.RawMessage, error) {
	if c.accessToken == "" {
		return nil, errors.New("tiktok: access token is required for this endpoint")
	}

	var bodyReader io.Reader
	if body != nil {
		buf, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("tiktok: marshal request body: %w", err)
		}
		bodyReader = bytes.NewReader(buf)
	}

	if len(query) > 0 {
		if strings.Contains(fullURL, "?") {
			fullURL += "&" + query.Encode()
		} else {
			fullURL += "?" + query.Encode()
		}
	}

	req, err := http.NewRequestWithContext(ctx, method, fullURL, bodyReader)
	if err != nil {
		return nil, fmt.Errorf("tiktok: build request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+c.accessToken)
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", c.userAgent)
	if body != nil {
		req.Header.Set("Content-Type", "application/json; charset=UTF-8")
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("tiktok: %s %s: %w", method, fullURL, err)
	}
	defer resp.Body.Close()

	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("tiktok: read response: %w", err)
	}

	if len(raw) == 0 {
		return nil, &Error{
			StatusCode: resp.StatusCode,
			Code:       "empty_response",
			Message:    fmt.Sprintf("TikTok returned an empty response body (HTTP %d, url=%s)", resp.StatusCode, fullURL),
		}
	}

	var env envelope
	if err := json.Unmarshal(raw, &env); err != nil {
		return nil, &Error{
			StatusCode: resp.StatusCode,
			Code:       "invalid_response",
			Message:    fmt.Sprintf("TikTok returned a non-JSON response: %v", err),
			Body:       raw,
		}
	}

	if env.Error.Code != "" && env.Error.Code != "ok" {
		return nil, &Error{
			StatusCode: resp.StatusCode,
			Code:       env.Error.Code,
			Message:    env.Error.Message,
			LogID:      env.Error.LogID,
			Body:       raw,
		}
	}

	return env.Data, nil
}

// doForm executes an unauthenticated POST that submits an
// application/x-www-form-urlencoded body. Used by the OAuth refresh endpoint,
// which is application-credential rather than user-token authenticated.
func (c *Client) doForm(ctx context.Context, fullURL string, form url.Values, out any) error {
	body := strings.NewReader(form.Encode())
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, fullURL, body)
	if err != nil {
		return fmt.Errorf("tiktok: build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", c.userAgent)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("tiktok: POST %s: %w", fullURL, err)
	}
	defer resp.Body.Close()

	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("tiktok: read response: %w", err)
	}

	if resp.StatusCode >= 400 {
		// TikTok's OAuth endpoint returns errors in OAuth2 shape.
		var oauthErr struct {
			Error            string `json:"error"`
			ErrorDescription string `json:"error_description"`
			LogID            string `json:"log_id"`
		}
		_ = json.Unmarshal(raw, &oauthErr)
		code := oauthErr.Error
		if code == "" {
			code = "oauth_error"
		}
		return &Error{
			StatusCode: resp.StatusCode,
			Code:       code,
			Message:    oauthErr.ErrorDescription,
			LogID:      oauthErr.LogID,
			Body:       raw,
		}
	}

	if err := json.Unmarshal(raw, out); err != nil {
		return &Error{
			StatusCode: resp.StatusCode,
			Code:       "invalid_response",
			Message:    fmt.Sprintf("TikTok OAuth returned non-JSON: %v", err),
			Body:       raw,
		}
	}
	return nil
}
