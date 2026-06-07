package tiktok

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"testing"
)

func TestAddDataRequest_Success(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/v2/user/data/add/" {
			t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		// The Python SDK always sends fields=request_id as a query parameter.
		if got := r.URL.Query().Get("fields"); got != "request_id" {
			t.Errorf("expected fields=request_id, got %q", got)
		}
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		if body["data_format"] != "json" {
			t.Errorf("expected data_format=json, got %v", body["data_format"])
		}
		cats, _ := body["category_selection_list"].([]any)
		if len(cats) != 2 || cats[0] != "profile" || cats[1] != "video" {
			t.Errorf("unexpected category list: %+v", cats)
		}
		_, _ = io.WriteString(w, `{"data":{"request_id":987654321},"error":{"code":"ok","message":"","log_id":"abc"}}`)
	})

	out, err := c.AddDataRequest(context.Background(), AddDataRequestParams{
		DataFormat:            DataFormatJSON,
		CategorySelectionList: []DataCategory{DataCategoryProfile, DataCategoryVideo},
	})
	if err != nil {
		t.Fatalf("AddDataRequest: %v", err)
	}
	if out.RequestID != 987654321 {
		t.Fatalf("unexpected request id: %d", out.RequestID)
	}
}

func TestAddDataRequest_AllData(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		var body map[string]any
		_ = json.NewDecoder(r.Body).Decode(&body)
		if body["data_format"] != "text" {
			t.Errorf("expected data_format=text, got %v", body["data_format"])
		}
		cats, _ := body["category_selection_list"].([]any)
		if len(cats) != 1 || cats[0] != "all_data" {
			t.Errorf("unexpected category list: %+v", cats)
		}
		_, _ = io.WriteString(w, `{"data":{"request_id":111222333},"error":{"code":"ok"}}`)
	})

	out, err := c.AddDataRequest(context.Background(), AddDataRequestParams{
		DataFormat:            DataFormatText,
		CategorySelectionList: []DataCategory{DataCategoryAllData},
	})
	if err != nil {
		t.Fatalf("AddDataRequest: %v", err)
	}
	if out.RequestID != 111222333 {
		t.Fatalf("unexpected request id: %d", out.RequestID)
	}
}

func TestAddDataRequest_RequiresCategory(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		t.Error("server must not be called when no category is supplied")
	})
	if _, err := c.AddDataRequest(context.Background(), AddDataRequestParams{DataFormat: DataFormatJSON}); err == nil {
		t.Fatal("expected error for empty category list")
	}
}

func TestAddDataRequest_ScopeError(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusForbidden)
		_, _ = io.WriteString(w, `{"data":{},"error":{"code":"scope_not_authorized","message":"Required portability scope not granted.","log_id":"err001"}}`)
	})
	_, err := c.AddDataRequest(context.Background(), AddDataRequestParams{
		DataFormat:            DataFormatJSON,
		CategorySelectionList: []DataCategory{DataCategoryDirectMessage},
	})
	apiErr, ok := AsError(err)
	if !ok {
		t.Fatalf("expected *tiktok.Error, got %T: %v", err, err)
	}
	if apiErr.Code != "scope_not_authorized" || !apiErr.IsAuthError() {
		t.Fatalf("expected scope_not_authorized auth error, got %+v", apiErr)
	}
}

func TestCheckDataRequestStatus_DefaultFields(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/v2/user/data/check/" {
			t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		// nil fields => all status fields, in the Python SDK's declared order.
		want := "request_id,apply_time,collect_time,status,data_format,category_selection_list"
		if got := r.URL.Query().Get("fields"); got != want {
			t.Errorf("unexpected fields query:\n got=%q\nwant=%q", got, want)
		}
		var body map[string]any
		_ = json.NewDecoder(r.Body).Decode(&body)
		if body["request_id"].(float64) != 987654321 {
			t.Errorf("expected request_id=987654321, got %v", body["request_id"])
		}
		_, _ = io.WriteString(w, `{"data":{"request_id":987654321,"apply_time":1700000000,"collect_time":1700000005,"status":"pending","data_format":"json","category_selection_list":["profile","video"]},"error":{"code":"ok"}}`)
	})

	out, err := c.CheckDataRequestStatus(context.Background(), 987654321, nil)
	if err != nil {
		t.Fatalf("CheckDataRequestStatus: %v", err)
	}
	if out.Status == nil || *out.Status != DataRequestStatusPending {
		t.Fatalf("unexpected status: %+v", out.Status)
	}
	if out.DataFormat == nil || *out.DataFormat != DataFormatJSON {
		t.Fatalf("unexpected data format: %+v", out.DataFormat)
	}
	if out.ApplyTime == nil || *out.ApplyTime != 1700000000 {
		t.Fatalf("unexpected apply time: %+v", out.ApplyTime)
	}
	if len(out.CategorySelectionList) != 2 || out.CategorySelectionList[0] != DataCategoryProfile {
		t.Fatalf("unexpected category list: %+v", out.CategorySelectionList)
	}
}

func TestCheckDataRequestStatus_ExplicitFields(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if got := r.URL.Query().Get("fields"); got != "request_id,status" {
			t.Errorf("unexpected fields query: %q", got)
		}
		_, _ = io.WriteString(w, `{"data":{"request_id":999,"status":"downloading"},"error":{"code":"ok"}}`)
	})

	out, err := c.CheckDataRequestStatus(context.Background(), 999, []StatusField{StatusFieldRequestID, StatusFieldStatus})
	if err != nil {
		t.Fatalf("CheckDataRequestStatus: %v", err)
	}
	if out.Status == nil || *out.Status != DataRequestStatusDownloading {
		t.Fatalf("unexpected status: %+v", out.Status)
	}
	if out.RequestID == nil || *out.RequestID != 999 {
		t.Fatalf("unexpected request id: %+v", out.RequestID)
	}
	// Unrequested fields must remain nil.
	if out.DataFormat != nil || out.ApplyTime != nil {
		t.Fatalf("expected unrequested fields to be nil, got %+v", out)
	}
}

func TestCancelDataRequest_Success(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/v2/user/data/cancel/" {
			t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		// request_id is carried as a query parameter, not a JSON body.
		if got := r.URL.Query().Get("request_id"); got != "987654321" {
			t.Errorf("expected request_id=987654321 query, got %q", got)
		}
		body, _ := io.ReadAll(r.Body)
		if len(body) != 0 {
			t.Errorf("expected empty body, got %q", body)
		}
		_, _ = io.WriteString(w, `{"error":{"code":"ok","message":"","log_id":"cancel_log_123"}}`)
	})

	if err := c.CancelDataRequest(context.Background(), 987654321); err != nil {
		t.Fatalf("CancelDataRequest: %v", err)
	}
}

func TestCancelDataRequest_APIError(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, `{"error":{"code":"resource_not_found","message":"Request not found.","log_id":"err002"}}`)
	})
	err := c.CancelDataRequest(context.Background(), 0)
	apiErr, ok := AsError(err)
	if !ok || apiErr.Code != "resource_not_found" {
		t.Fatalf("expected resource_not_found error, got %v", err)
	}
}

func TestDownloadData_Success(t *testing.T) {
	fakeZip := []byte("PK\x03\x04")
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/v2/user/data/download/" {
			t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		var body map[string]any
		_ = json.NewDecoder(r.Body).Decode(&body)
		if body["request_id"].(float64) != 987654321 {
			t.Errorf("expected request_id=987654321, got %v", body["request_id"])
		}
		w.Header().Set("Content-Type", "application/zip")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(fakeZip)
	})

	data, err := c.DownloadData(context.Background(), 987654321)
	if err != nil {
		t.Fatalf("DownloadData: %v", err)
	}
	if len(data) != 4 || string(data) != "PK\x03\x04" {
		t.Fatalf("unexpected archive bytes: %q", data)
	}
}

func TestDownloadData_ErrorEnvelope(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = io.WriteString(w, `{"data":{},"error":{"code":"access_token_invalid","message":"bad token","log_id":"L"}}`)
	})
	_, err := c.DownloadData(context.Background(), 1)
	apiErr, ok := AsError(err)
	if !ok {
		t.Fatalf("expected *tiktok.Error, got %T: %v", err, err)
	}
	if apiErr.Code != "access_token_invalid" || apiErr.StatusCode != http.StatusUnauthorized {
		t.Fatalf("unexpected download error: %+v", apiErr)
	}
	if !apiErr.IsAuthError() {
		t.Fatalf("expected IsAuthError, got %+v", apiErr)
	}
}

func TestDownloadData_NonJSONFailure(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadGateway)
		_, _ = io.WriteString(w, `<html>gateway error</html>`)
	})
	_, err := c.DownloadData(context.Background(), 1)
	apiErr, ok := AsError(err)
	if !ok || apiErr.Code != "download_failed" || apiErr.StatusCode != http.StatusBadGateway {
		t.Fatalf("expected download_failed/502 error, got %v", err)
	}
}

func TestDownloadData_RequiresAccessToken(t *testing.T) {
	c := New(ClientOptions{}) // no token
	defer c.Close()
	if _, err := c.DownloadData(context.Background(), 1); err == nil {
		t.Fatal("expected access-token error for DownloadData without a token")
	}
}
