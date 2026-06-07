package tiktok

import (
	"context"
	"errors"
	"net/url"
	"strings"
)

// AuthorizeURL is the user-facing OAuth consent host. Note this is the
// www.tiktok.com host, distinct from the open.tiktokapis.com API host.
const AuthorizeURL = "https://www.tiktok.com/v2/auth/authorize/"

// AuthorizationURLParams configures BuildAuthorizationURL.
type AuthorizationURLParams struct {
	ClientKey   string   // TikTok app client key.
	RedirectURI string   // Callback URL registered with the app (exact match).
	Scopes      []string // OAuth scopes to request.
	State       string   // Opaque CSRF value echoed back to the callback.

	// CodeChallenge enables the PKCE flow when non-empty.
	CodeChallenge string
	// CodeChallengeMethod defaults to "S256" when CodeChallenge is set.
	CodeChallengeMethod string
	// DisableAutoAuth, when set, forces the consent screen.
	DisableAutoAuth *bool
}

// BuildAuthorizationURL assembles the URL to redirect a user to for consent.
// It performs no network call. It is a package-level function (not a *Client
// method) because the consent URL needs only the client key, not a constructed
// client.
func BuildAuthorizationURL(p AuthorizationURLParams) (string, error) {
	if p.ClientKey == "" {
		return "", errors.New("tiktok: BuildAuthorizationURL requires ClientKey")
	}
	if p.RedirectURI == "" {
		return "", errors.New("tiktok: BuildAuthorizationURL requires RedirectURI")
	}
	if len(p.Scopes) == 0 {
		return "", errors.New("tiktok: BuildAuthorizationURL requires at least one scope")
	}
	q := url.Values{}
	q.Set("client_key", p.ClientKey)
	q.Set("response_type", "code")
	q.Set("scope", strings.Join(p.Scopes, ","))
	q.Set("redirect_uri", p.RedirectURI)
	q.Set("state", p.State)
	if p.CodeChallenge != "" {
		method := p.CodeChallengeMethod
		if method == "" {
			method = "S256"
		}
		q.Set("code_challenge", p.CodeChallenge)
		q.Set("code_challenge_method", method)
	}
	if p.DisableAutoAuth != nil {
		if *p.DisableAutoAuth {
			q.Set("disable_auto_auth", "1")
		} else {
			q.Set("disable_auto_auth", "0")
		}
	}
	return AuthorizeURL + "?" + q.Encode(), nil
}

// TokenResult is the decoded OAuth2 token response, returned by both
// ExchangeCode and RefreshAccessToken.
type TokenResult struct {
	AccessToken      string `json:"access_token"`
	ExpiresIn        int64  `json:"expires_in"`
	RefreshToken     string `json:"refresh_token"`
	RefreshExpiresIn int64  `json:"refresh_expires_in"`
	OpenID           string `json:"open_id"`
	Scope            string `json:"scope"`
	TokenType        string `json:"token_type"`
}

// ExchangeCodeParams carries the inputs to the authorization_code grant.
type ExchangeCodeParams struct {
	ClientKey    string // TikTok app client key.
	ClientSecret string // TikTok app client secret.
	Code         string // Authorization code delivered to the redirect URI.
	RedirectURI  string // The same callback URL used to obtain the code.
	CodeVerifier string // PKCE verifier; required when a code_challenge was used.
}

// ExchangeCode exchanges an authorization code for an access/refresh token pair.
// It uses application credentials and does not require AccessToken on the
// *Client.
func (c *Client) ExchangeCode(ctx context.Context, p ExchangeCodeParams) (*TokenResult, error) {
	if p.ClientKey == "" || p.ClientSecret == "" || p.Code == "" || p.RedirectURI == "" {
		return nil, errors.New("tiktok: ExchangeCodeParams requires ClientKey, ClientSecret, Code, and RedirectURI")
	}
	form := url.Values{}
	form.Set("client_key", p.ClientKey)
	form.Set("client_secret", p.ClientSecret)
	form.Set("code", p.Code)
	form.Set("grant_type", "authorization_code")
	form.Set("redirect_uri", p.RedirectURI)
	if p.CodeVerifier != "" {
		form.Set("code_verifier", p.CodeVerifier)
	}

	out := &TokenResult{}
	if err := c.doForm(ctx, c.baseURL+"/v2/oauth/token/", form, out); err != nil {
		return nil, err
	}
	return out, nil
}

// RefreshTokenParams carries the inputs to the TikTok OAuth refresh endpoint.
type RefreshTokenParams struct {
	ClientKey    string // TikTok app client key.
	ClientSecret string // TikTok app client secret.
	RefreshToken string // The refresh token previously issued to the user.
}

// RefreshTokenResult is the decoded OAuth2 refresh response.
//
// Deprecated: use TokenResult, which ExchangeCode and RefreshAccessToken both
// return. RefreshTokenResult is retained as an alias for backward compatibility.
type RefreshTokenResult = TokenResult

// RefreshAccessToken exchanges a refresh token for a new access/refresh pair.
// TikTok rotates the refresh token on every refresh, so callers must persist
// the returned RefreshToken for the next cycle. This call uses application
// credentials, not the user access token.
func (c *Client) RefreshAccessToken(ctx context.Context, p RefreshTokenParams) (*TokenResult, error) {
	if p.ClientKey == "" || p.ClientSecret == "" || p.RefreshToken == "" {
		return nil, errors.New("tiktok: RefreshTokenParams requires ClientKey, ClientSecret, and RefreshToken")
	}
	form := url.Values{}
	form.Set("client_key", p.ClientKey)
	form.Set("client_secret", p.ClientSecret)
	form.Set("grant_type", "refresh_token")
	form.Set("refresh_token", p.RefreshToken)

	out := &TokenResult{}
	if err := c.doForm(ctx, c.baseURL+"/v2/oauth/token/", form, out); err != nil {
		return nil, err
	}
	return out, nil
}

// RevokeAccessToken revokes a user access token, invalidating the grant.
func (c *Client) RevokeAccessToken(ctx context.Context, clientKey, clientSecret, accessToken string) error {
	if clientKey == "" || clientSecret == "" || accessToken == "" {
		return errors.New("tiktok: RevokeAccessToken requires clientKey, clientSecret, and accessToken")
	}
	form := url.Values{}
	form.Set("client_key", clientKey)
	form.Set("client_secret", clientSecret)
	form.Set("token", accessToken)

	var out struct{}
	return c.doForm(ctx, c.baseURL+"/v2/oauth/revoke/", form, &out)
}
