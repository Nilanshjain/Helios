package config

import (
	"os"
	"strconv"
	"strings"

	"github.com/joho/godotenv"
)

// Config holds all configuration for the ingestion service
type Config struct {
	// Server configuration
	ServerPort  int
	MetricsPort int
	LogLevel    string

	// Kafka configuration
	KafkaBrokers []string
	KafkaTopic   string

	// Database configuration (for consumer)
	DBHost     string
	DBPort     int
	DBName     string
	DBUser     string
	DBPassword string

	// Rate limiting
	RateLimitPerSecond int
	RateLimitBurst     int
}

// Load loads configuration from environment variables
func Load() (*Config, error) {
	// Try to load .env file (ignore error if not found)
	_ = godotenv.Load()

	cfg := &Config{
		ServerPort:         getEnvAsInt("SERVER_PORT", 8080),
		MetricsPort:        getEnvAsInt("METRICS_PORT", 8081),
		LogLevel:           getEnv("LOG_LEVEL", "info"),
		KafkaBrokers:       getEnvAsSlice("KAFKA_BROKERS", []string{"localhost:9092"}),
		KafkaTopic:         getEnv("KAFKA_TOPIC", "events"),
		DBHost:             getEnv("DB_HOST", "localhost"),
		DBPort:             getEnvAsInt("DB_PORT", 5432),
		DBName:             getEnv("DB_NAME", "helios"),
		DBUser:             getEnv("DB_USER", "postgres"),
		DBPassword:         getEnv("DB_PASSWORD", "postgres"),
		RateLimitPerSecond: getEnvAsInt("RATE_LIMIT_PER_SECOND", 10000),
		RateLimitBurst:     getEnvAsInt("RATE_LIMIT_BURST", 20000),
	}

	return cfg, nil
}

// getEnv gets an environment variable with a fallback default value
func getEnv(key string, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// getEnvAsInt gets an environment variable as integer with a fallback default value
func getEnvAsInt(key string, defaultValue int) int {
	valueStr := getEnv(key, "")
	if valueStr == "" {
		return defaultValue
	}

	value, err := strconv.Atoi(valueStr)
	if err != nil {
		return defaultValue
	}

	return value
}

// getEnvAsSlice gets an environment variable as a slice with a fallback default value
func getEnvAsSlice(key string, defaultValue []string) []string {
	valueStr := getEnv(key, "")
	if valueStr == "" {
		return defaultValue
	}

	return strings.Split(valueStr, ",")
}
