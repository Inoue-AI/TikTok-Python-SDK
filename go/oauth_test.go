package tiktok

import (
	"context"
	"io"
	"net/http"
	"net/url"
	"strings"
	"testing"
)

func TestBuildAuthorizationURL(t *testing.T) {
	got, err := BuildAuthorizationURL(AuthorizationURLParams{
		ClientKey:   "ck",
		RedirectURI: "https://app.example.com/callback",
		Scopes:      []string{"user.info.basic", "video.publish"},
		State:       "csrf123",
	})
	if err != nil {
		t.Fatalf("BuildAuthorizationURL: %v", err)
	}
	if !strings.HasPrefix(got, AuthorizeURL+"?") {
		t.Fatalf("unexpected URL prefix: %s", got)
	}
	parsed, _ := url.Parse(got)
	q := parsed.Query()
	if q.Get("client_key") != "ck" || q.Get("response_type") != "code" {
		t.Errorf("missing core params: %s", got)
	}
	if q.Get("scope") != "user.info.basic,video.publish" {
		t.Errorf("unexpected scope: %s", q.Get("scope"))
	}
	if q.Get("state") != "csrf123" {
		t.Errorf("unexpected state: %s", q.Get("state"))
	}
	if q.Has("code_challenge") {
		t.Error("PKCE param should be absent unless requested")
	}
}

func TestBuildAuthorizationURL_PKCE(t *testing.T) {
	disable := true
	got, err := BuildAuthorizationURL(AuthorizationURLParams{
		ClientKey:       "ck",
		RedirectURI:     "https://app.example.com/cb",
		Scopes:          []string{"user.info.basic"},
		State:           "s",
		CodeChallenge:   "challenge123",
		DisableAutoAuth: &disable,
	})
	if err != nil {
		t.Fatalf("BuildAuthorizationURL: %v", err)
	}
	q, _ := url.Parse(got)
	vals := q.Query()
	if vals.Get("code_challenge") != "challenge123" || vals.Get("code_challenge_method") != "S256" {
		t.Errorf("unexpected PKCE params: %s", got)
	}
	if vals.Get("disable_auto_auth") != "1" {
		t.Errorf("expected disable_auto_auth=1, got %s", vals.Get("disable_auto_auth"))
	}
}

func TestBuildAuthorizationURL_Validation(t *testing.T) {
	if _, err := BuildAuthorizationURL(AuthorizationURLParams{RedirectURI: "x", Scopes: []string{"s"}}); err == nil {
		t.Error("expected error for missing client key")
	}
	if _, err := BuildAuthorizationURL(AuthorizationURLParams{ClientKey: "c", Scopes: []string{"s"}}); err == nil {
		t.Error("expected error for missing redirect URI")
	}
	if _, err := BuildAuthorizationURL(AuthorizationURLParams{ClientKey: "c", RedirectURI: "x"}); err == nil {
		t.Error("expected error for missing scopes")
	}
}

func TestExchangeCode_Success(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/v2/oauth/token/" {
			t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		body, _ := io.ReadAll(r.Body)
		s := string(body)
		if !strings.Contains(s, "grant_type=authorization_code") || !strings.Contains(s, "code=auth_xyz") {
			t.Errorf("body missing required fields: %s", s)
		}
		if !strings.Contains(s, "code_verifier=ver123") {
			t.Errorf("PKCE verifier not forwarded: %s", s)
		}
		_, _ = io.WriteString(w, `{"access_token":"A","refresh_token":"R","expires_in":86400,"refresh_expires_in":31536000,"open_id":"o","scope":"user.info.basic","token_type":"Bearer"}`)
	})
	out, err := c.ExchangeCode(context.Background(), ExchangeCodeParams{
		ClientKey:    "K",
		ClientSecret: "S",
		Code:         "auth_xyz",
		RedirectURI:  "https://app.example.com/cb",
		CodeVerifier: "ver123",
	})
	if err != nil {
		t.Fatalf("ExchangeCode: %v", err)
	}
	if out.AccessToken != "A" || out.RefreshToken != "R" || out.OpenID != "o" {
		t.Fatalf("unexpected token result: %+v", out)
	}
}

func TestExchangeCode_Validation(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		t.Error("server must not be called when required params are missing")
	})
	if _, err := c.ExchangeCode(context.Background(), ExchangeCodeParams{ClientKey: "K"}); err == nil {
		t.Fatal("expected validation error")
	}
}

func TestRevokeAccessToken_Success(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v2/oauth/revoke/" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		body, _ := io.ReadAll(r.Body)
		if !strings.Contains(string(body), "token=act.revoke") {
			t.Errorf("token not forwarded: %s", body)
		}
		_, _ = io.WriteString(w, `{}`)
	})
	if err := c.RevokeAccessToken(context.Background(), "K", "S", "act.revoke"); err != nil {
		t.Fatalf("RevokeAccessToken: %v", err)
	}
}

func TestRevokeAccessToken_Validation(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		t.Error("server must not be called when params are missing")
	})
	if err := c.RevokeAccessToken(context.Background(), "", "S", "tok"); err == nil {
		t.Fatal("expected validation error")
	}
}
