package models

import (
	"encoding/json"
	"testing"
	"time"
)

func TestEvent_Validate(t *testing.T) {
	tests := []struct {
		name    string
		event   Event
		wantErr bool
	}{
		{
			name: "valid event with timestamp",
			event: Event{
				Timestamp: time.Now(),
				Service:   "test-service",
				Level:     "INFO",
				Message:   "test message",
			},
			wantErr: false,
		},
		{
			name: "valid event without timestamp - should set current time",
			event: Event{
				Service: "test-service",
				Level:   "ERROR",
				Message: "error message",
			},
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			initialTimestamp := tt.event.Timestamp
			err := tt.event.Validate()

			if (err != nil) != tt.wantErr {
				t.Errorf("Event.Validate() error = %v, wantErr %v", err, tt.wantErr)
				return
			}

			// Check that IngestedAt is set
			if tt.event.IngestedAt.IsZero() {
				t.Error("Event.Validate() should set IngestedAt")
			}

			// Check that Timestamp is set if it was initially zero
			if initialTimestamp.IsZero() && tt.event.Timestamp.IsZero() {
				t.Error("Event.Validate() should set Timestamp if it was zero")
			}
		})
	}
}

func TestEvent_ToJSON(t *testing.T) {
	event := Event{
		Timestamp: time.Date(2024, 1, 1, 12, 0, 0, 0, time.UTC),
		Service:   "test-service",
		Level:     "INFO",
		Message:   "test message",
		Metadata: map[string]interface{}{
			"key": "value",
		},
	}

	jsonBytes, err := event.ToJSON()
	if err != nil {
		t.Fatalf("Event.ToJSON() error = %v", err)
	}

	// Verify it's valid JSON
	var decoded Event
	if err := json.Unmarshal(jsonBytes, &decoded); err != nil {
		t.Errorf("Failed to unmarshal JSON: %v", err)
	}

	// Verify key fields
	if decoded.Service != event.Service {
		t.Errorf("Service mismatch: got %s, want %s", decoded.Service, event.Service)
	}
	if decoded.Level != event.Level {
		t.Errorf("Level mismatch: got %s, want %s", decoded.Level, event.Level)
	}
	if decoded.Message != event.Message {
		t.Errorf("Message mismatch: got %s, want %s", decoded.Message, event.Message)
	}
}

func TestEvent_GetPartitionKey(t *testing.T) {
	tests := []struct {
		name    string
		service string
		want    string
	}{
		{
			name:    "standard service name",
			service: "payment-service",
			want:    "payment-service",
		},
		{
			name:    "service with special chars",
			service: "api-gateway-v2",
			want:    "api-gateway-v2",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			event := Event{Service: tt.service}
			if got := event.GetPartitionKey(); got != tt.want {
				t.Errorf("Event.GetPartitionKey() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestEventBatch_Validation(t *testing.T) {
	// Test that EventBatch can hold multiple events
	batch := EventBatch{
		Events: []Event{
			{
				Timestamp: time.Now(),
				Service:   "service-1",
				Level:     "INFO",
				Message:   "message 1",
			},
			{
				Timestamp: time.Now(),
				Service:   "service-2",
				Level:     "ERROR",
				Message:   "message 2",
			},
		},
	}

	if len(batch.Events) != 2 {
		t.Errorf("EventBatch should contain 2 events, got %d", len(batch.Events))
	}
}

// Benchmark tests for performance validation
func BenchmarkEvent_ToJSON(b *testing.B) {
	event := Event{
		Timestamp: time.Now(),
		Service:   "benchmark-service",
		Level:     "INFO",
		Message:   "benchmark test message",
		Metadata: map[string]interface{}{
			"latency_ms": 100,
			"endpoint":   "/api/test",
		},
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := event.ToJSON()
		if err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkEvent_Validate(b *testing.B) {
	event := Event{
		Timestamp: time.Now(),
		Service:   "benchmark-service",
		Level:     "INFO",
		Message:   "benchmark test message",
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		err := event.Validate()
		if err != nil {
			b.Fatal(err)
		}
	}
}
