# Build stage
FROM golang:1.21-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git ca-certificates

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build both binaries
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o ingestion main.go
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o consumer consumer.go

# Runtime stage
FROM alpine:latest

RUN apk --no-cache add ca-certificates tzdata

WORKDIR /root/

# Copy both binaries from builder
COPY --from=builder /app/ingestion .
COPY --from=builder /app/consumer .

# Expose ports
EXPOSE 8080 8081

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

# Run as non-root user
RUN addgroup -g 1000 helios && \
    adduser -D -u 1000 -G helios helios && \
    chown -R helios:helios /root

USER helios

# Run the binary
CMD ["./ingestion"]
