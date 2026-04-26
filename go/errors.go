package tiktok

import (
	"errors"
	"fmt"
)

// Error represents an upstream TikTok API error. TikTok always returns an
// "error" object inside the JSON body even when the HTTP status is 200, so
// both the platform code and the HTTP status are surfaced.
type Error struct {
	StatusCode int    // HTTP status code returned by TikTok.
	Code       string // TikTok error code (e.g. "rate_limit_exceeded").
	Message    string // Human-readable description from the API.
	LogID      string // Opaque request identifier useful for support tickets.
	Body       []byte // Raw response body, retained for diagnostics.
}

// Error implements the error interface.
func (e *Error) Error() string {
	return fmt.Sprintf("tiktok: [%s] %s (http=%d log_id=%s)", e.Code, e.Message, e.StatusCode, e.LogID)
}

// IsAuthError reports whether the error indicates an authentication or scope
// failure that the caller cannot recover from without a new token.
func (e *Error) IsAuthError() bool {
	switch e.Code {
	case "access_token_invalid", "access_token_expired", "scope_not_authorized", "permission_denied":
		return true
	}
	return false
}

// IsRateLimited reports whether the error indicates a TikTok-imposed rate limit.
func (e *Error) IsRateLimited() bool {
	switch e.Code {
	case "rate_limit_exceeded", "spam_risk_too_many_posts":
		return true
	}
	return false
}

// IsServerError reports whether the upstream returned a 5xx-style failure.
func (e *Error) IsServerError() bool {
	if e.StatusCode >= 500 {
		return true
	}
	switch e.Code {
	case "internal_error", "server_error":
		return true
	}
	return false
}

// AsError unwraps any error returned by this package into a *Error if it is
// one. It returns the typed error and true if so, otherwise nil and false.
func AsError(err error) (*Error, bool) {
	var apiErr *Error
	if errors.As(err, &apiErr) {
		return apiErr, true
	}
	return nil, false
}
