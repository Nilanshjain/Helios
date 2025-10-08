package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"math/rand"
	"net/http"
	"sync"
	"sync/atomic"
	"time"
)

// Event represents a single event to be sent
type Event struct {
	Timestamp time.Time              `json:"timestamp"`
	Service   string                 `json:"service"`
	Level     string                 `json:"level"`
	Message   string                 `json:"message"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
	TraceID   string                 `json:"trace_id,omitempty"`
	SpanID    string                 `json:"span_id,omitempty"`
}

// Service configuration for realistic event generation
var services = []struct {
	name         string
	endpoints    []string
	errorRate    float64 // Percentage of error events
	latencyMean  float64 // Mean latency in ms
	latencyStdDev float64 // Standard deviation of latency
}{
	{
		name:         "api-gateway",
		endpoints:    []string{"/api/v1/users", "/api/v1/posts", "/api/v1/comments", "/health"},
		errorRate:    0.02, // 2% error rate
		latencyMean:  50,
		latencyStdDev: 20,
	},
	{
		name:         "auth-service",
		endpoints:    []string{"/login", "/logout", "/refresh", "/register", "/verify"},
		errorRate:    0.01, // 1% error rate
		latencyMean:  30,
		latencyStdDev: 10,
	},
	{
		name:         "payment-service",
		endpoints:    []string{"/checkout", "/refund", "/validate", "/balance"},
		errorRate:    0.03, // 3% error rate (higher for critical service)
		latencyMean:  120,
		latencyStdDev: 50,
	},
	{
		name:         "notification-service",
		endpoints:    []string{"/email", "/sms", "/push", "/webhook"},
		errorRate:    0.05, // 5% error rate
		latencyMean:  200,
		latencyStdDev: 80,
	},
	{
		name:         "user-service",
		endpoints:    []string{"/profile", "/settings", "/preferences", "/avatar"},
		errorRate:    0.015, // 1.5% error rate
		latencyMean:  40,
		latencyStdDev: 15,
	},
}

// Error messages for different scenarios
var errorMessages = map[string][]string{
	"api-gateway": {
		"Request timeout",
		"Upstream service unavailable",
		"Rate limit exceeded",
		"Invalid request payload",
	},
	"auth-service": {
		"Invalid credentials",
		"Token expired",
		"Session not found",
		"Account locked",
	},
	"payment-service": {
		"Database connection timeout",
		"Payment gateway error",
		"Insufficient funds",
		"Transaction declined",
		"Network error communicating with payment provider",
	},
	"notification-service": {
		"SMTP connection failed",
		"SMS gateway timeout",
		"Push notification service unavailable",
		"Template rendering error",
	},
	"user-service": {
		"User not found",
		"Database query timeout",
		"Cache miss",
		"Profile update failed",
	},
}

// Info messages
var infoMessages = []string{
	"Request processed successfully",
	"Operation completed",
	"Request handled",
	"Processing successful",
}

var (
	apiURL         string
	eventsPerSec   int
	duration       int
	injectAnomaly  bool
	anomalyAfter   int
	anomalyService string
	batchSize      int
	workers        int
)

func init() {
	flag.StringVar(&apiURL, "url", "http://localhost:8080/api/v1/events", "Ingestion API URL")
	flag.IntVar(&eventsPerSec, "rate", 1000, "Events per second")
	flag.IntVar(&duration, "duration", 60, "Duration in seconds (0 for infinite)")
	flag.BoolVar(&injectAnomaly, "inject-anomaly", false, "Inject anomaly for testing")
	flag.IntVar(&anomalyAfter, "anomaly-after", 30, "Inject anomaly after N seconds")
	flag.StringVar(&anomalyService, "anomaly-service", "payment-service", "Service to inject anomaly into")
	flag.IntVar(&batchSize, "batch", 10, "Batch size for sending events")
	flag.IntVar(&workers, "workers", 10, "Number of concurrent workers")
}

func main() {
	flag.Parse()

	fmt.Printf("🚀 Starting event generator\n")
	fmt.Printf("   API URL: %s\n", apiURL)
	fmt.Printf("   Target Rate: %d events/sec\n", eventsPerSec)
	fmt.Printf("   Duration: %d seconds\n", duration)
	fmt.Printf("   Batch Size: %d\n", batchSize)
	fmt.Printf("   Workers: %d\n", workers)
	if injectAnomaly {
		fmt.Printf("   Anomaly: Will inject into %s after %d seconds\n", anomalyService, anomalyAfter)
	}
	fmt.Println()

	var (
		totalSent   int64
		totalErrors int64
		startTime   = time.Now()
	)

	// Create event channel
	eventCh := make(chan Event, eventsPerSec*2)

	// Start worker pool
	var wg sync.WaitGroup
	for i := 0; i < workers; i++ {
		wg.Add(1)
		go worker(i, eventCh, &totalSent, &totalErrors, &wg)
	}

	// Start stats reporter
	stopStats := make(chan struct{})
	go statsReporter(startTime, &totalSent, &totalErrors, stopStats)

	// Generate events
	ticker := time.NewTicker(time.Second / time.Duration(eventsPerSec))
	defer ticker.Stop()

	endTime := time.Now().Add(time.Duration(duration) * time.Second)
	if duration == 0 {
		endTime = time.Now().Add(365 * 24 * time.Hour) // Run for a year (effectively infinite)
	}

	for time.Now().Before(endTime) {
		<-ticker.C

		// Check if we should inject anomaly
		if injectAnomaly && time.Since(startTime).Seconds() >= float64(anomalyAfter) {
			eventCh <- generateAnomalousEvent(anomalyService)
		} else {
			eventCh <- generateNormalEvent()
		}
	}

	// Cleanup
	close(eventCh)
	wg.Wait()
	close(stopStats)

	// Final stats
	elapsed := time.Since(startTime)
	fmt.Printf("\n✅ Generation complete!\n")
	fmt.Printf("   Total Events: %d\n", atomic.LoadInt64(&totalSent))
	fmt.Printf("   Total Errors: %d\n", atomic.LoadInt64(&totalErrors))
	fmt.Printf("   Duration: %.2f seconds\n", elapsed.Seconds())
	fmt.Printf("   Average Rate: %.2f events/sec\n", float64(totalSent)/elapsed.Seconds())
}

// worker sends events to the API
func worker(id int, eventCh <-chan Event, totalSent, totalErrors *int64, wg *sync.WaitGroup) {
	defer wg.Done()

	client := &http.Client{
		Timeout: 5 * time.Second,
	}

	batch := make([]Event, 0, batchSize)

	for event := range eventCh {
		batch = append(batch, event)

		if len(batch) >= batchSize {
			if err := sendBatch(client, batch); err != nil {
				atomic.AddInt64(totalErrors, int64(len(batch)))
			} else {
				atomic.AddInt64(totalSent, int64(len(batch)))
			}
			batch = make([]Event, 0, batchSize)
		}
	}

	// Send remaining events
	if len(batch) > 0 {
		if err := sendBatch(client, batch); err != nil {
			atomic.AddInt64(totalErrors, int64(len(batch)))
		} else {
			atomic.AddInt64(totalSent, int64(len(batch)))
		}
	}
}

// sendBatch sends a batch of events to the API
func sendBatch(client *http.Client, events []Event) error {
	payload := map[string]interface{}{
		"events": events,
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal events: %w", err)
	}

	// Use batch endpoint
	batchURL := apiURL
	if len(events) > 1 {
		batchURL = apiURL + "/batch"
	}

	req, err := http.NewRequest("POST", batchURL, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusAccepted {
		return fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	return nil
}

// generateNormalEvent generates a realistic event
func generateNormalEvent() Event {
	svc := services[rand.Intn(len(services))]
	endpoint := svc.endpoints[rand.Intn(len(svc.endpoints))]

	// Determine if this should be an error
	isError := rand.Float64() < svc.errorRate

	var level, message string
	if isError {
		level = "ERROR"
		errorMsgs := errorMessages[svc.name]
		message = errorMsgs[rand.Intn(len(errorMsgs))]
	} else {
		level = "INFO"
		message = infoMessages[rand.Intn(len(infoMessages))]
	}

	// Generate latency with normal distribution
	latency := svc.latencyMean + rand.NormFloat64()*svc.latencyStdDev
	if latency < 0 {
		latency = svc.latencyMean
	}

	return Event{
		Timestamp: time.Now(),
		Service:   svc.name,
		Level:     level,
		Message:   message,
		Metadata: map[string]interface{}{
			"endpoint":   endpoint,
			"latency_ms": latency,
			"request_id": generateRequestID(),
		},
		TraceID: generateTraceID(),
		SpanID:  generateSpanID(),
	}
}

// generateAnomalousEvent generates an anomalous event (high error rate, high latency)
func generateAnomalousEvent(serviceName string) Event {
	var svc *struct {
		name         string
		endpoints    []string
		errorRate    float64
		latencyMean  float64
		latencyStdDev float64
	}

	for i := range services {
		if services[i].name == serviceName {
			svc = &services[i]
			break
		}
	}

	if svc == nil {
		svc = &services[0]
	}

	endpoint := svc.endpoints[rand.Intn(len(svc.endpoints))]

	// Force high error rate and high latency
	level := "ERROR"
	errorMsgs := errorMessages[svc.name]
	message := errorMsgs[rand.Intn(len(errorMsgs))]

	// 10x normal latency
	latency := svc.latencyMean * 10

	return Event{
		Timestamp: time.Now(),
		Service:   svc.name,
		Level:     level,
		Message:   message,
		Metadata: map[string]interface{}{
			"endpoint":   endpoint,
			"latency_ms": latency,
			"request_id": generateRequestID(),
			"anomaly":    true,
		},
		TraceID: generateTraceID(),
		SpanID:  generateSpanID(),
	}
}

// statsReporter prints statistics periodically
func statsReporter(startTime time.Time, totalSent, totalErrors *int64, stop <-chan struct{}) {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			sent := atomic.LoadInt64(totalSent)
			errors := atomic.LoadInt64(totalErrors)
			elapsed := time.Since(startTime).Seconds()
			rate := float64(sent) / elapsed

			fmt.Printf("📊 Sent: %d | Errors: %d | Rate: %.2f events/sec | Elapsed: %.1fs\n",
				sent, errors, rate, elapsed)

		case <-stop:
			return
		}
	}
}

// Helper functions
func generateRequestID() string {
	return fmt.Sprintf("req_%d", rand.Int63())
}

func generateTraceID() string {
	return fmt.Sprintf("trace_%016x", rand.Int63())
}

func generateSpanID() string {
	return fmt.Sprintf("span_%08x", rand.Int31())
}
