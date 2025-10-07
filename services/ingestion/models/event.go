package models

import (
	"encoding/json"
	"time"
)

// Event represents a single event ingested into the system
type Event struct {
	Timestamp time.Time              `json:"timestamp" validate:"required"`
	Service   string                 `json:"service" validate:"required,min=1,max=255"`
	Level     string                 `json:"level" validate:"required,oneof=DEBUG INFO WARN ERROR CRITICAL"`
	Message   string                 `json:"message" validate:"required,min=1"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
	TraceID   string                 `json:"trace_id,omitempty"`
	SpanID    string                 `json:"span_id,omitempty"`

	// Enriched fields (added by ingestion service)
	IngestedAt time.Time `json:"ingested_at,omitempty"`
	Host       string    `json:"host,omitempty"`
}

// EventBatch represents a batch of events
type EventBatch struct {
	Events []Event `json:"events" validate:"required,min=1,max=1000,dive"`
}

// Validate performs additional validation logic
func (e *Event) Validate() error {
	// If timestamp is zero, set to current time
	if e.Timestamp.IsZero() {
		e.Timestamp = time.Now()
	}

	// Enrich with ingestion timestamp
	e.IngestedAt = time.Now()

	return nil
}

// ToJSON converts event to JSON bytes for Kafka
func (e *Event) ToJSON() ([]byte, error) {
	return json.Marshal(e)
}

// GetPartitionKey returns the partition key for Kafka (service name)
func (e *Event) GetPartitionKey() string {
	return e.Service
}

// EventResponse represents the API response after ingesting an event
type EventResponse struct {
	Status    string    `json:"status"`
	EventID   string    `json:"event_id,omitempty"`
	Timestamp time.Time `json:"timestamp"`
	Message   string    `json:"message,omitempty"`
}

// ErrorResponse represents an API error response
type ErrorResponse struct {
	Status  string `json:"status"`
	Error   string `json:"error"`
	Details string `json:"details,omitempty"`
}
