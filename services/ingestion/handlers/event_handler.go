package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"

	"github.com/go-playground/validator/v10"
	"github.com/nilansh/helios/ingestion/config"
	"github.com/nilansh/helios/ingestion/models"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/rs/zerolog/log"
	"github.com/segmentio/kafka-go"
)

var (
	// Prometheus metrics
	eventsIngested = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "helios_events_ingested_total",
			Help: "Total number of events ingested",
		},
		[]string{"service", "level", "status"},
	)

	ingestionLatency = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "helios_ingestion_latency_seconds",
			Help:    "Event ingestion latency in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"endpoint"},
	)

	kafkaProducerErrors = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "helios_kafka_producer_errors_total",
			Help: "Total number of Kafka producer errors",
		},
	)
)

// EventHandler handles event ingestion requests
type EventHandler struct {
	kafkaWriter *kafka.Writer
	validator   *validator.Validate
	config      *config.Config
	hostname    string
}

// NewEventHandler creates a new event handler
func NewEventHandler(kafkaWriter *kafka.Writer, cfg *config.Config) *EventHandler {
	hostname, _ := os.Hostname()

	return &EventHandler{
		kafkaWriter: kafkaWriter,
		validator:   validator.New(),
		config:      cfg,
		hostname:    hostname,
	}
}

// IngestEvent handles POST /api/v1/events
func (h *EventHandler) IngestEvent(w http.ResponseWriter, r *http.Request) {
	startTime := time.Now()
	defer func() {
		ingestionLatency.WithLabelValues("ingest_event").Observe(time.Since(startTime).Seconds())
	}()

	// Parse request body
	var event models.Event
	if err := json.NewDecoder(r.Body).Decode(&event); err != nil {
		h.respondError(w, http.StatusBadRequest, "Invalid JSON", err.Error())
		eventsIngested.WithLabelValues("unknown", "unknown", "error").Inc()
		return
	}

	// Validate event
	if err := h.validator.Struct(event); err != nil {
		h.respondError(w, http.StatusBadRequest, "Validation failed", err.Error())
		eventsIngested.WithLabelValues(event.Service, event.Level, "validation_error").Inc()
		return
	}

	// Enrich event
	if err := event.Validate(); err != nil {
		h.respondError(w, http.StatusBadRequest, "Event validation failed", err.Error())
		eventsIngested.WithLabelValues(event.Service, event.Level, "validation_error").Inc()
		return
	}
	event.Host = h.hostname

	// Convert to JSON
	eventJSON, err := event.ToJSON()
	if err != nil {
		h.respondError(w, http.StatusInternalServerError, "Failed to serialize event", err.Error())
		eventsIngested.WithLabelValues(event.Service, event.Level, "serialization_error").Inc()
		return
	}

	// Send to Kafka
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err = h.kafkaWriter.WriteMessages(ctx, kafka.Message{
		Key:   []byte(event.GetPartitionKey()),
		Value: eventJSON,
		Time:  event.Timestamp,
	})

	if err != nil {
		log.Error().
			Err(err).
			Str("service", event.Service).
			Str("level", event.Level).
			Msg("Failed to write to Kafka")

		kafkaProducerErrors.Inc()
		eventsIngested.WithLabelValues(event.Service, event.Level, "kafka_error").Inc()
		h.respondError(w, http.StatusServiceUnavailable, "Failed to ingest event", "Kafka producer error")
		return
	}

	// Log successful ingestion
	log.Info().
		Str("service", event.Service).
		Str("level", event.Level).
		Str("message", event.Message).
		Msg("Event ingested successfully")

	eventsIngested.WithLabelValues(event.Service, event.Level, "success").Inc()

	// Respond
	h.respondJSON(w, http.StatusAccepted, models.EventResponse{
		Status:    "accepted",
		Timestamp: time.Now(),
		Message:   "Event ingested successfully",
	})
}

// IngestEventBatch handles POST /api/v1/events/batch
func (h *EventHandler) IngestEventBatch(w http.ResponseWriter, r *http.Request) {
	startTime := time.Now()
	defer func() {
		ingestionLatency.WithLabelValues("ingest_batch").Observe(time.Since(startTime).Seconds())
	}()

	// Parse request body
	var batch models.EventBatch
	if err := json.NewDecoder(r.Body).Decode(&batch); err != nil {
		h.respondError(w, http.StatusBadRequest, "Invalid JSON", err.Error())
		return
	}

	// Validate batch
	if err := h.validator.Struct(batch); err != nil {
		h.respondError(w, http.StatusBadRequest, "Validation failed", err.Error())
		return
	}

	// Prepare Kafka messages
	messages := make([]kafka.Message, 0, len(batch.Events))
	successCount := 0
	errorCount := 0

	for i := range batch.Events {
		event := &batch.Events[i]

		// Validate and enrich each event
		if err := event.Validate(); err != nil {
			errorCount++
			continue
		}
		event.Host = h.hostname

		// Validate struct
		if err := h.validator.Struct(event); err != nil {
			errorCount++
			eventsIngested.WithLabelValues(event.Service, event.Level, "validation_error").Inc()
			continue
		}

		// Convert to JSON
		eventJSON, err := event.ToJSON()
		if err != nil {
			errorCount++
			eventsIngested.WithLabelValues(event.Service, event.Level, "serialization_error").Inc()
			continue
		}

		messages = append(messages, kafka.Message{
			Key:   []byte(event.GetPartitionKey()),
			Value: eventJSON,
			Time:  event.Timestamp,
		})
		successCount++
	}

	// Send batch to Kafka
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	err := h.kafkaWriter.WriteMessages(ctx, messages...)
	if err != nil {
		log.Error().Err(err).Int("batch_size", len(messages)).Msg("Failed to write batch to Kafka")
		kafkaProducerErrors.Inc()
		h.respondError(w, http.StatusServiceUnavailable, "Failed to ingest batch", "Kafka producer error")
		return
	}

	log.Info().
		Int("success_count", successCount).
		Int("error_count", errorCount).
		Int("total", len(batch.Events)).
		Msg("Batch ingested")

	// Update metrics for successful events
	for _, event := range batch.Events {
		eventsIngested.WithLabelValues(event.Service, event.Level, "success").Inc()
	}

	// Respond
	h.respondJSON(w, http.StatusAccepted, map[string]interface{}{
		"status":        "accepted",
		"total":         len(batch.Events),
		"success_count": successCount,
		"error_count":   errorCount,
		"timestamp":     time.Now(),
	})
}

// respondJSON sends a JSON response
func (h *EventHandler) respondJSON(w http.ResponseWriter, statusCode int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	json.NewEncoder(w).Encode(data)
}

// respondError sends an error response
func (h *EventHandler) respondError(w http.ResponseWriter, statusCode int, error string, details string) {
	h.respondJSON(w, statusCode, models.ErrorResponse{
		Status:  "error",
		Error:   error,
		Details: details,
	})
}
