package tiktok

import (
	"context"
	"errors"
	"net/url"
)

// RefreshTokenParams carries the inputs to the TikTok OAuth refresh endpoint.
type RefreshTokenParams struct {
	ClientKey    string // TikTok app client key.
	ClientSecret string // TikTok app client secret.
	RefreshToken string // The refresh token previously issued to the user.
}

// RefreshTokenResult is the decoded OAuth2 response.
type RefreshTokenResult struct {
	AccessToken           string `json:"access_token"`
	ExpiresIn             int64  `json:"expires_in"`
	RefreshToken          string `json:"refresh_token"`
	RefreshExpiresIn      int64  `json:"refresh_expires_in"`
	OpenID                string `json:"open_id"`
	Scope                 string `json:"scope"`
	TokenType             string `json:"token_type"`
}

// RefreshAccessToken exchanges a refresh token for a new access/refresh pair.
// This call uses application credentials, not the user access token, so it
// works on a *Client constructed without an AccessToken.
func (c *Client) RefreshAccessToken(ctx context.Context, p RefreshTokenParams) (*RefreshTokenResult, error) {
	if p.ClientKey == "" || p.ClientSecret == "" || p.RefreshToken == "" {
		return nil, errors.New("tiktok: RefreshTokenParams requires ClientKey, ClientSecret, and RefreshToken")
	}
	form := url.Values{}
	form.Set("client_key", p.ClientKey)
	form.Set("client_secret", p.ClientSecret)
	form.Set("grant_type", "refresh_token")
	form.Set("refresh_token", p.RefreshToken)

	out := &RefreshTokenResult{}
	if err := c.doForm(ctx, c.baseURL+"/v2/oauth/token/", form, out); err != nil {
		return nil, err
	}
	return out, nil
}
