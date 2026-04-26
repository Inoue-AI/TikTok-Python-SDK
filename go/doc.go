// Package tiktok provides a typed, context-aware Go client for the TikTok
// Open API (Display, Content Posting, OAuth/refresh, and Account Analytics).
//
// The client mirrors the Python SDK shape so that backend services can swap
// implementations without behavioural drift. Every public method takes
// context.Context as its first parameter, every HTTP call uses the reusable
// *http.Client owned by the Client value (never http.DefaultClient), and all
// HTTP timeouts are explicit.
//
// Construct a client with New, then call methods on the returned *Client:
//
//	client := tiktok.New(tiktok.ClientOptions{
//	    AccessToken: "USER_ACCESS_TOKEN",
//	    Timeout:     30 * time.Second,
//	})
//	defer client.Close()
//
//	user, err := client.GetUser(ctx, []string{"open_id", "display_name"})
//	if err != nil {
//	    return err
//	}
//
// Token refresh requires the application client credentials and does not
// consume the user access token:
//
//	tokens, err := client.RefreshAccessToken(ctx, tiktok.RefreshTokenParams{
//	    ClientKey:    clientKey,
//	    ClientSecret: clientSecret,
//	    RefreshToken: refreshToken,
//	})
package tiktok
