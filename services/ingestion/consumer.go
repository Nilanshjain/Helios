package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	_ "github.com/lib/pq"
	"github.com/nilansh/helios/ingestion/config"
	"github.com/nilansh/helios/ingestion/models"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"github.com/segmentio/kafka-go"
)

var (
	// Prometheus metrics
	eventsConsumed = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "helios_events_consumed_total",
			Help: "Total number of events consumed from Kafka",
		},
		[]string{"service", "level", "status"},
	)

	dbWriteLatency = promauto.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "helios_db_write_latency_seconds",
			Help:    "Database write latency in seconds",
			Buckets: prometheus.DefBuckets,
		},
	)

	batchSize = promauto.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "helios_consumer_batch_size",
			Help:    "Number of events written in each batch",
			Buckets: []float64{1, 10, 50, 100, 200, 500, 1000},
		},
	)

	consumerLagGauge = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "helios_consumer_lag",
			Help: "Current consumer lag (messages behind)",
		},
	)
)

// StorageWriter consumes events from Kafka and writes to TimescaleDB
type StorageWriter struct {
	reader   *kafka.Reader
	db       *sql.DB
	cfg      *config.Config
	batchCh  chan *models.Event
	shutdown chan struct{}
}

// NewStorageWriter creates a new storage writer instance
func NewStorageWriter(cfg *config.Config) (*StorageWriter, error) {
	// Initialize Kafka reader
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:        cfg.KafkaBrokers,
		Topic:          cfg.KafkaTopic,
		GroupID:        "storage-writers",
		MinBytes:       1e3,  // 1KB
		MaxBytes:       10e6, // 10MB
		CommitInterval: time.Second,
		StartOffset:    kafka.LastOffset,
		MaxWait:        500 * time.Millisecond,
	})

	// Initialize database connection
	dsn := fmt.Sprintf(
		"host=%s port=%d user=%s password=%s dbname=%s sslmode=disable",
		cfg.DBHost, cfg.DBPort, cfg.DBUser, cfg.DBPassword, cfg.DBName,
	)

	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Configure connection pool
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	log.Info().
		Str("host", cfg.DBHost).
		Int("port", cfg.DBPort).
		Str("database", cfg.DBName).
		Msg("Database connection established")

	return &StorageWriter{
		reader:   reader,
		db:       db,
		cfg:      cfg,
		batchCh:  make(chan *models.Event, 1000),
		shutdown: make(chan struct{}),
	}, nil
}

// Start starts the consumer
func (sw *StorageWriter) Start(ctx context.Context) error {
	log.Info().Msg("Starting storage writer consumer")

	// Start batch writer goroutine
	go sw.batchWriter(ctx)

	// Consume messages
	for {
		select {
		case <-ctx.Done():
			log.Info().Msg("Context cancelled, stopping consumer")
			return ctx.Err()
		case <-sw.shutdown:
			log.Info().Msg("Shutdown signal received")
			return nil
		default:
			msg, err := sw.reader.FetchMessage(ctx)
			if err != nil {
				if err == context.Canceled {
					return nil
				}
				log.Error().Err(err).Msg("Error fetching message")
				time.Sleep(time.Second)
				continue
			}

			// Parse event
			var event models.Event
			if err := json.Unmarshal(msg.Value, &event); err != nil {
				log.Error().
					Err(err).
					Str("raw_message", string(msg.Value)).
					Msg("Failed to unmarshal event")
				eventsConsumed.WithLabelValues("unknown", "unknown", "unmarshal_error").Inc()

				// Commit offset even for bad messages to avoid getting stuck
				if err := sw.reader.CommitMessages(ctx, msg); err != nil {
					log.Error().Err(err).Msg("Failed to commit offset")
				}
				continue
			}

			// Send to batch channel
			select {
			case sw.batchCh <- &event:
				eventsConsumed.WithLabelValues(event.Service, event.Level, "queued").Inc()
			case <-time.After(5 * time.Second):
				log.Warn().Msg("Batch channel full, dropping event")
				eventsConsumed.WithLabelValues(event.Service, event.Level, "dropped").Inc()
			}

			// Commit offset
			if err := sw.reader.CommitMessages(ctx, msg); err != nil {
				log.Error().Err(err).Msg("Failed to commit offset")
			}
		}
	}
}

// batchWriter writes events to database in batches
func (sw *StorageWriter) batchWriter(ctx context.Context) {
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()

	batch := make([]*models.Event, 0, 100)

	for {
		select {
		case <-ctx.Done():
			// Write remaining batch before shutdown
			if len(batch) > 0 {
				sw.writeBatch(batch)
			}
			return

		case event := <-sw.batchCh:
			batch = append(batch, event)

			// Write when batch is full
			if len(batch) >= 100 {
				sw.writeBatch(batch)
				batch = make([]*models.Event, 0, 100)
			}

		case <-ticker.C:
			// Write batch every second even if not full
			if len(batch) > 0 {
				sw.writeBatch(batch)
				batch = make([]*models.Event, 0, 100)
			}
		}
	}
}

// writeBatch writes a batch of events to TimescaleDB
func (sw *StorageWriter) writeBatch(events []*models.Event) {
	if len(events) == 0 {
		return
	}

	startTime := time.Now()
	defer func() {
		dbWriteLatency.Observe(time.Since(startTime).Seconds())
		batchSize.Observe(float64(len(events)))
	}()

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// Begin transaction
	tx, err := sw.db.BeginTx(ctx, nil)
	if err != nil {
		log.Error().Err(err).Msg("Failed to begin transaction")
		sw.markEventsAsFailed(events)
		return
	}
	defer tx.Rollback()

	// Prepare insert statement
	stmt, err := tx.PrepareContext(ctx, `
		INSERT INTO events (time, service, level, message, metadata, trace_id, span_id, host, ingested_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
	`)
	if err != nil {
		log.Error().Err(err).Msg("Failed to prepare statement")
		sw.markEventsAsFailed(events)
		return
	}
	defer stmt.Close()

	// Insert each event
	successCount := 0
	for _, event := range events {
		// Convert metadata to JSON
		var metadataJSON []byte
		if event.Metadata != nil {
			metadataJSON, err = json.Marshal(event.Metadata)
			if err != nil {
				log.Error().Err(err).Str("service", event.Service).Msg("Failed to marshal metadata")
				eventsConsumed.WithLabelValues(event.Service, event.Level, "marshal_error").Inc()
				continue
			}
		}

		_, err := stmt.ExecContext(ctx,
			event.Timestamp,
			event.Service,
			event.Level,
			event.Message,
			metadataJSON,
			event.TraceID,
			event.SpanID,
			event.Host,
			event.IngestedAt,
		)

		if err != nil {
			log.Error().
				Err(err).
				Str("service", event.Service).
				Str("level", event.Level).
				Msg("Failed to insert event")
			eventsConsumed.WithLabelValues(event.Service, event.Level, "db_error").Inc()
			continue
		}

		successCount++
		eventsConsumed.WithLabelValues(event.Service, event.Level, "success").Inc()
	}

	// Commit transaction
	if err := tx.Commit(); err != nil {
		log.Error().Err(err).Msg("Failed to commit transaction")
		sw.markEventsAsFailed(events)
		return
	}

	log.Info().
		Int("batch_size", len(events)).
		Int("success_count", successCount).
		Float64("latency_ms", float64(time.Since(startTime).Milliseconds())).
		Msg("Batch written to database")
}

// markEventsAsFailed marks events as failed in metrics
func (sw *StorageWriter) markEventsAsFailed(events []*models.Event) {
	for _, event := range events {
		eventsConsumed.WithLabelValues(event.Service, event.Level, "failed").Inc()
	}
}

// Close closes the consumer and database connections
func (sw *StorageWriter) Close() error {
	close(sw.shutdown)

	if err := sw.reader.Close(); err != nil {
		log.Error().Err(err).Msg("Error closing Kafka reader")
	}

	if err := sw.db.Close(); err != nil {
		log.Error().Err(err).Msg("Error closing database connection")
		return err
	}

	log.Info().Msg("Storage writer closed successfully")
	return nil
}

func main() {
	// Configure structured logging
	zerolog.TimeFieldFormat = zerolog.TimeFormatUnix
	log.Logger = log.Output(zerolog.ConsoleWriter{Out: os.Stderr, TimeFormat: time.RFC3339})

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to load configuration")
	}

	// Set log level
	level, err := zerolog.ParseLevel(cfg.LogLevel)
	if err != nil {
		level = zerolog.InfoLevel
	}
	zerolog.SetGlobalLevel(level)

	log.Info().Msg("Starting Helios Storage Writer")

	// Create storage writer
	writer, err := NewStorageWriter(cfg)
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to create storage writer")
	}
	defer writer.Close()

	// Create context for graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Start consumer in goroutine
	errCh := make(chan error, 1)
	go func() {
		if err := writer.Start(ctx); err != nil {
			errCh <- err
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	select {
	case sig := <-quit:
		log.Info().Str("signal", sig.String()).Msg("Shutdown signal received")
		cancel()
	case err := <-errCh:
		log.Error().Err(err).Msg("Consumer error")
		cancel()
	}

	// Wait a bit for graceful shutdown
	time.Sleep(2 * time.Second)

	log.Info().Msg("Storage writer stopped")
}
