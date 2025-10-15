#!/bin/bash

# Helios Load Test Runner
# Validates throughput, latency, and reliability claims

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default configuration
HOST="${HOST:-localhost}"
PORT="${PORT:-8080}"
THREADS="${THREADS:-100}"
DURATION="${DURATION:-600}"  # 10 minutes
RAMPUP="${RAMPUP:-60}"       # 1 minute ramp-up
THROUGHPUT="${THROUGHPUT:-50000}"  # 50K events/sec target

# Create results directory
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="results/${TIMESTAMP}"
mkdir -p "${RESULTS_DIR}"

echo -e "${GREEN}======================================"
echo "Helios Ingestion Load Test"
echo "======================================${NC}"
echo ""
echo "Configuration:"
echo "  Target: http://${HOST}:${PORT}"
echo "  Threads: ${THREADS}"
echo "  Duration: ${DURATION}s ($(($DURATION/60)) minutes)"
echo "  Ramp-up: ${RAMPUP}s"
echo "  Target Throughput: ${THROUGHPUT} events/sec"
echo ""
echo "Results will be saved to: ${RESULTS_DIR}"
echo ""

# Check if JMeter is installed
if ! command -v jmeter &> /dev/null; then
    echo -e "${RED}ERROR: JMeter is not installed or not in PATH${NC}"
    echo "Please install JMeter: https://jmeter.apache.org/download_jmeter.cgi"
    exit 1
fi

# Check if ingestion service is running
echo -e "${YELLOW}Checking if ingestion service is running...${NC}"
if ! curl -s -f "http://${HOST}:${PORT}/health" > /dev/null 2>&1; then
    echo -e "${RED}WARNING: Ingestion service health check failed${NC}"
    echo "Make sure the service is running: docker-compose up -d ingestion"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✓ Ingestion service is healthy${NC}"
fi

echo ""
echo -e "${GREEN}Starting load test...${NC}"
echo ""

# Run JMeter in non-GUI mode
jmeter -n \
  -t ingestion_load_test.jmx \
  -Jhost=${HOST} \
  -Jport=${PORT} \
  -Jthreads=${THREADS} \
  -Jduration=${DURATION} \
  -Jrampup=${RAMPUP} \
  -Jthroughput=${THROUGHPUT} \
  -l "${RESULTS_DIR}/results.jtl" \
  -j "${RESULTS_DIR}/jmeter.log" \
  -e -o "${RESULTS_DIR}/html-report"

echo ""
echo -e "${GREEN}======================================"
echo "Load Test Complete!"
echo "======================================${NC}"
echo ""
echo "Results:"
echo "  JTL File: ${RESULTS_DIR}/results.jtl"
echo "  HTML Report: ${RESULTS_DIR}/html-report/index.html"
echo "  Log File: ${RESULTS_DIR}/jmeter.log"
echo ""

# Parse results if awk is available
if command -v awk &> /dev/null && [ -f "${RESULTS_DIR}/results.jtl" ]; then
    echo -e "${GREEN}Quick Summary:${NC}"
    echo ""

    # Calculate statistics
    TOTAL=$(tail -n +2 "${RESULTS_DIR}/results.jtl" | wc -l)
    SUCCESS=$(tail -n +2 "${RESULTS_DIR}/results.jtl" | awk -F',' '$8=="true"' | wc -l)
    ERRORS=$(tail -n +2 "${RESULTS_DIR}/results.jtl" | awk -F',' '$8=="false"' | wc -l)

    if [ $TOTAL -gt 0 ]; then
        SUCCESS_RATE=$(awk "BEGIN {printf \"%.2f\", ($SUCCESS/$TOTAL)*100}")
        ERROR_RATE=$(awk "BEGIN {printf \"%.2f\", ($ERRORS/$TOTAL)*100}")
        THROUGHPUT_ACTUAL=$(awk "BEGIN {printf \"%.0f\", $TOTAL/$DURATION}")

        echo "  Total Requests: $TOTAL"
        echo "  Successful: $SUCCESS ($SUCCESS_RATE%)"
        echo "  Errors: $ERRORS ($ERROR_RATE%)"
        echo "  Actual Throughput: $THROUGHPUT_ACTUAL events/sec"
        echo ""

        # Calculate latency percentiles
        echo "  Calculating percentiles..."
        tail -n +2 "${RESULTS_DIR}/results.jtl" | awk -F',' '{print $2}' | sort -n > "${RESULTS_DIR}/latencies.txt"

        P50_LINE=$(awk "BEGIN {printf \"%.0f\", $TOTAL*0.50}")
        P95_LINE=$(awk "BEGIN {printf \"%.0f\", $TOTAL*0.95}")
        P99_LINE=$(awk "BEGIN {printf \"%.0f\", $TOTAL*0.99}")

        P50=$(sed -n "${P50_LINE}p" "${RESULTS_DIR}/latencies.txt")
        P95=$(sed -n "${P95_LINE}p" "${RESULTS_DIR}/latencies.txt")
        P99=$(sed -n "${P99_LINE}p" "${RESULTS_DIR}/latencies.txt")

        echo "  P50 Latency: ${P50}ms"
        echo "  P95 Latency: ${P95}ms"
        echo "  P99 Latency: ${P99}ms"
        echo ""

        # Check if targets met
        echo -e "${GREEN}Target Validation:${NC}"

        if (( $(echo "$SUCCESS_RATE >= 99.9" | bc -l) )); then
            echo -e "  ${GREEN}✓${NC} Success Rate: $SUCCESS_RATE% (target: ≥99.9%)"
        else
            echo -e "  ${RED}✗${NC} Success Rate: $SUCCESS_RATE% (target: ≥99.9%)"
        fi

        if [ $THROUGHPUT_ACTUAL -ge 50000 ]; then
            echo -e "  ${GREEN}✓${NC} Throughput: $THROUGHPUT_ACTUAL events/sec (target: ≥50000/sec)"
        else
            echo -e "  ${YELLOW}⚠${NC} Throughput: $THROUGHPUT_ACTUAL events/sec (target: ≥50000/sec)"
        fi

        if [ ! -z "$P99" ] && [ $P99 -lt 150 ]; then
            echo -e "  ${GREEN}✓${NC} P99 Latency: ${P99}ms (target: <150ms)"
        else
            echo -e "  ${YELLOW}⚠${NC} P99 Latency: ${P99}ms (target: <150ms)"
        fi
    fi
fi

echo ""
echo -e "${YELLOW}Open HTML report: file://$(pwd)/${RESULTS_DIR}/html-report/index.html${NC}"
echo ""
