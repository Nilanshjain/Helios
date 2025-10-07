package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/nilansh/helios/ingestion/config"
	"github.com/nilansh/helios/ingestion/handlers"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"github.com/segmentio/kafka-go"
)

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

	log.Info().Msg("Starting Helios Ingestion Service")
	log.Info().Str("version", "1.0.0").Msg("Service configuration loaded")

	// Initialize Kafka producer
	kafkaWriter := &kafka.Writer{
		Addr:         kafka.TCP(cfg.KafkaBrokers...),
		Topic:        cfg.KafkaTopic,
		Balancer:     &kafka.Hash{}, // Partition by service name
		BatchSize:    100,
		BatchTimeout: 10 * time.Millisecond,
		Compression:  kafka.Snappy,
		MaxAttempts:  3,
		RequiredAcks: kafka.RequireOne,
		Async:        false, // Synchronous writes for reliability
	}
	defer kafkaWriter.Close()

	log.Info().
		Strs("brokers", cfg.KafkaBrokers).
		Str("topic", cfg.KafkaTopic).
		Msg("Kafka producer initialized")

	// Initialize handler
	eventHandler := handlers.NewEventHandler(kafkaWriter, cfg)

	// Create router
	r := chi.NewRouter()

	// Middleware
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(middleware.Timeout(30 * time.Second))

	// Health check endpoint
	r.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"healthy","service":"ingestion"}`))
	})

	// Readiness check endpoint
	r.Get("/ready", func(w http.ResponseWriter, r *http.Request) {
		// Check if Kafka is reachable
		if err := kafkaWriter.WriteMessages(context.Background()); err == nil || err.Error() == "no messages provided" {
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`{"status":"ready"}`))
			return
		}
		w.WriteHeader(http.StatusServiceUnavailable)
		w.Write([]byte(`{"status":"not ready"}`))
	})

	// API routes
	r.Route("/api/v1", func(r chi.Router) {
		r.Post("/events", eventHandler.IngestEvent)
		r.Post("/events/batch", eventHandler.IngestEventBatch)
	})

	// Start HTTP server
	server := &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.ServerPort),
		Handler:      r,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start metrics server
	metricsRouter := chi.NewRouter()
	metricsRouter.Handle("/metrics", promhttp.Handler())

	metricsServer := &http.Server{
		Addr:    fmt.Sprintf(":%d", cfg.MetricsPort),
		Handler: metricsRouter,
	}

	// Start servers in goroutines
	go func() {
		log.Info().Int("port", cfg.ServerPort).Msg("HTTP server started")
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatal().Err(err).Msg("HTTP server failed")
		}
	}()

	go func() {
		log.Info().Int("port", cfg.MetricsPort).Msg("Metrics server started")
		if err := metricsServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatal().Err(err).Msg("Metrics server failed")
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	sig := <-quit

	log.Info().Str("signal", sig.String()).Msg("Shutdown signal received")

	// Graceful shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	log.Info().Msg("Shutting down servers...")

	// Shutdown HTTP server
	if err := server.Shutdown(ctx); err != nil {
		log.Error().Err(err).Msg("HTTP server forced to shutdown")
	}

	// Shutdown metrics server
	if err := metricsServer.Shutdown(ctx); err != nil {
		log.Error().Err(err).Msg("Metrics server forced to shutdown")
	}

	// Close Kafka writer
	log.Info().Msg("Closing Kafka producer...")
	if err := kafkaWriter.Close(); err != nil {
		log.Error().Err(err).Msg("Error closing Kafka producer")
	}

	log.Info().Msg("Service stopped gracefully")
}
