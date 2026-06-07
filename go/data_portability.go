package tiktok

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
)

// Data Portability API.
//
// These endpoints let an authenticated user export and download their TikTok
// data. They wrap:
//
//   - POST /v2/user/data/add/      — initiate a data export request
//   - POST /v2/user/data/check/    — check the status of a request
//   - POST /v2/user/data/cancel/   — cancel a pending request
//   - POST /v2/user/data/download/ — download the exported zip archive
//
// Availability note: the Data Portability API is available only to users in the
// European Economic Area (EEA) or the United Kingdom (UK). Calls from other
// regions are rejected upstream regardless of token validity.
//
// Reference: https://developers.tiktok.com/doc/data-portability-api-get-started

// DataCategory enumerates the data categories that can be requested via the
// Data Portability API. Each category corresponds to one or more portability.*
// OAuth scopes that the user must have granted.
type DataCategory string

const (
	// DataCategoryAllData maps to portability.all.single / portability.all.ongoing.
	DataCategoryAllData DataCategory = "all_data"
	// DataCategoryActivity maps to portability.activity.single / .ongoing.
	DataCategoryActivity DataCategory = "activity"
	// DataCategoryVideo maps to portability.postsandprofile.single / .ongoing.
	DataCategoryVideo DataCategory = "video"
	// DataCategoryProfile maps to portability.postsandprofile.single / .ongoing.
	DataCategoryProfile DataCategory = "profile"
	// DataCategoryDirectMessage maps to portability.directmessages.single / .ongoing.
	DataCategoryDirectMessage DataCategory = "direct_message"
)

// DataFormat enumerates the output format for a data export archive.
type DataFormat string

const (
	// DataFormatText requests the export in plain-text format.
	DataFormatText DataFormat = "text"
	// DataFormatJSON requests the export in JSON format.
	DataFormatJSON DataFormat = "json"
)

// DataRequestStatus enumerates the processing states of a data export request.
type DataRequestStatus string

const (
	// DataRequestStatusPending indicates the export is still being prepared.
	DataRequestStatusPending DataRequestStatus = "pending"
	// DataRequestStatusDownloading indicates the archive is ready to download.
	DataRequestStatusDownloading DataRequestStatus = "downloading"
	// DataRequestStatusExpired indicates the export window has elapsed.
	DataRequestStatusExpired DataRequestStatus = "expired"
	// DataRequestStatusCancelled indicates the request was cancelled.
	DataRequestStatusCancelled DataRequestStatus = "cancelled"
)

// StatusField enumerates the fields that can be requested from
// /v2/user/data/check/ via the fields query parameter.
type StatusField string

const (
	// StatusFieldRequestID requests the request_id field.
	StatusFieldRequestID StatusField = "request_id"
	// StatusFieldApplyTime requests the apply_time field.
	StatusFieldApplyTime StatusField = "apply_time"
	// StatusFieldCollectTime requests the collect_time field.
	StatusFieldCollectTime StatusField = "collect_time"
	// StatusFieldStatus requests the status field.
	StatusFieldStatus StatusField = "status"
	// StatusFieldDataFormat requests the data_format field.
	StatusFieldDataFormat StatusField = "data_format"
	// StatusFieldCategorySelectionList requests the category_selection_list field.
	StatusFieldCategorySelectionList StatusField = "category_selection_list"
)

// allStatusFields is the default set requested by CheckDataRequestStatus when no
// explicit field list is supplied. The order mirrors the Python SDK so the
// serialised fields query parameter is byte-identical.
var allStatusFields = []StatusField{
	StatusFieldRequestID,
	StatusFieldApplyTime,
	StatusFieldCollectTime,
	StatusFieldStatus,
	StatusFieldDataFormat,
	StatusFieldCategorySelectionList,
}

// AddDataRequestResult is the response data from /v2/user/data/add/.
type AddDataRequestResult struct {
	// RequestID is the unique identifier for the export request. Persist it; it
	// is required by the status-check, cancel, and download endpoints.
	RequestID int64 `json:"request_id"`
}

// DataRequestStatusResult is the response data from /v2/user/data/check/.
//
// Only fields included in the fields query parameter are populated by TikTok;
// all others are left at their zero value. Pointer fields distinguish "field
// not requested / not returned" (nil) from a returned zero value.
type DataRequestStatusResult struct {
	RequestID             *int64             `json:"request_id,omitempty"`
	ApplyTime             *int64             `json:"apply_time,omitempty"`
	CollectTime           *int64             `json:"collect_time,omitempty"`
	Status                *DataRequestStatus `json:"status,omitempty"`
	DataFormat            *DataFormat        `json:"data_format,omitempty"`
	CategorySelectionList []DataCategory     `json:"category_selection_list,omitempty"`
}

// AddDataRequestParams configures AddDataRequest.
type AddDataRequestParams struct {
	// DataFormat is the output format for the archive ("json" or "text").
	DataFormat DataFormat
	// CategorySelectionList is one or more data categories to include in the
	// export. The user must have granted the corresponding portability.* scopes.
	CategorySelectionList []DataCategory
}

// AddDataRequest initiates a new data export request.
//
// It POSTs to /v2/user/data/add/ with the requested format and categories, and
// always passes fields=request_id as a query parameter (mirroring the Python
// SDK). The returned RequestID is required by all subsequent calls.
//
// Availability: EEA / UK users only.
//
// Scope: varies by category (see DataCategory).
func (c *Client) AddDataRequest(ctx context.Context, p AddDataRequestParams) (*AddDataRequestResult, error) {
	if len(p.CategorySelectionList) == 0 {
		return nil, errors.New("tiktok: AddDataRequest requires at least one category")
	}
	categories := make([]string, len(p.CategorySelectionList))
	for i, cat := range p.CategorySelectionList {
		categories[i] = string(cat)
	}
	body := map[string]any{
		"data_format":             string(p.DataFormat),
		"category_selection_list": categories,
	}
	q := url.Values{}
	q.Set("fields", "request_id")

	data, err := c.doJSON(ctx, http.MethodPost, c.baseURL+"/v2/user/data/add/", body, q)
	if err != nil {
		return nil, err
	}
	out := &AddDataRequestResult{}
	if err := json.Unmarshal(data, out); err != nil {
		return nil, fmt.Errorf("tiktok: decode add data request: %w", err)
	}
	return out, nil
}

// CheckDataRequestStatus checks the processing status of an export request.
//
// It POSTs to /v2/user/data/check/ with the request_id in the JSON body and the
// requested status fields as a comma-separated fields query parameter. When
// fields is nil, all available status fields are requested (matching the Python
// SDK default).
//
// Availability: EEA / UK users only.
//
// Scope: same scopes used when creating the request.
func (c *Client) CheckDataRequestStatus(ctx context.Context, requestID int64, fields []StatusField) (*DataRequestStatusResult, error) {
	requested := fields
	if requested == nil {
		requested = allStatusFields
	}
	fieldStrings := make([]string, len(requested))
	for i, f := range requested {
		fieldStrings[i] = string(f)
	}
	q := url.Values{}
	q.Set("fields", strings.Join(fieldStrings, ","))

	body := map[string]any{"request_id": requestID}
	data, err := c.doJSON(ctx, http.MethodPost, c.baseURL+"/v2/user/data/check/", body, q)
	if err != nil {
		return nil, err
	}
	out := &DataRequestStatusResult{}
	if err := json.Unmarshal(data, out); err != nil {
		return nil, fmt.Errorf("tiktok: decode data request status: %w", err)
	}
	return out, nil
}

// CancelDataRequest cancels a pending data export request.
//
// It POSTs to /v2/user/data/cancel/ with the request_id as a query parameter
// (no JSON body), mirroring the Python SDK. It returns nil on success.
//
// Availability: EEA / UK users only.
//
// Scope: same scopes used when creating the request.
func (c *Client) CancelDataRequest(ctx context.Context, requestID int64) error {
	q := url.Values{}
	q.Set("request_id", strconv.FormatInt(requestID, 10))

	_, err := c.doJSON(ctx, http.MethodPost, c.baseURL+"/v2/user/data/cancel/", nil, q)
	return err
}

// DownloadData downloads the exported data archive as raw bytes.
//
// It POSTs to /v2/user/data/download/ with the request_id in the JSON body and
// returns the complete zip archive. Call it only once the request status is
// DataRequestStatusDownloading (or after the TikTok webhook notification).
// Errors are still surfaced as *tiktok.Error from the JSON error envelope.
//
// Availability: EEA / UK users only.
//
// Scope: same scopes used when creating the request.
func (c *Client) DownloadData(ctx context.Context, requestID int64) ([]byte, error) {
	body := map[string]any{"request_id": requestID}
	return c.doRaw(ctx, http.MethodPost, c.baseURL+"/v2/user/data/download/", body, nil)
}
