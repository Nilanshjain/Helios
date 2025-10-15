# Load Testing with Apache JMeter

Comprehensive load tests to validate Helios ingestion performance claims.

## Target Metrics

| Metric | Target | Purpose |
|--------|--------|---------|
| **Throughput** | 50,000 events/sec | Validate high-volume processing |
| **Success Rate** | ≥99.91% | Message delivery reliability |
| **P99 Latency** | <150ms | 99th percentile response time |
| **P95 Latency** | <100ms | 95th percentile response time |
| **Sustained Load** | 10 minutes | Stability under load |

## Prerequisites

### 1. Install Apache JMeter

**macOS (Homebrew)**
```bash
brew install jmeter
```

**Ubuntu/Debian**
```bash
# Install Java first
sudo apt update
sudo apt install default-jdk

# Download and extract JMeter
wget https://dlcdn.apache.org/jmeter/binaries/apache-jmeter-5.6.2.tgz
tar -xzf apache-jmeter-5.6.2.tgz
sudo mv apache-jmeter-5.6.2 /opt/jmeter
echo 'export PATH=$PATH:/opt/jmeter/bin' >> ~/.bashrc
source ~/.bashrc
```

**Windows**
1. Install Java JDK 8+ from https://adoptium.net/
2. Download JMeter from https://jmeter.apache.org/download_jmeter.cgi
3. Extract to `C:\apache-jmeter-5.6.2`
4. Add `C:\apache-jmeter-5.6.2\bin` to PATH

**Verify Installation**
```bash
jmeter --version
# Should output: Apache JMeter 5.6.2 or higher
```

### 2. Start Helios Services

```bash
# Start all services
docker-compose up -d

# Verify ingestion service is running
curl http://localhost:8080/health
```

## Running Load Tests

### Quick Start (Default Configuration)

```bash
cd tests/load

# Linux/macOS
chmod +x run_load_test.sh
./run_load_test.sh

# Windows
run_load_test.bat
```

Default configuration:
- **Target**: http://localhost:8080
- **Threads**: 100
- **Duration**: 600s (10 minutes)
- **Ramp-up**: 60s
- **Throughput**: 50,000 events/sec

### Custom Configuration

**Linux/macOS**
```bash
# Test different throughput levels
THROUGHPUT=25000 ./run_load_test.sh    # 25K events/sec
THROUGHPUT=75000 ./run_load_test.sh    # 75K events/sec

# Shorter test duration
DURATION=300 ./run_load_test.sh         # 5 minutes

# More threads for higher load
THREADS=200 ./run_load_test.sh

# Remote server
HOST=helios.example.com PORT=8080 ./run_load_test.sh

# Combined
HOST=localhost PORT=8080 THREADS=150 DURATION=600 THROUGHPUT=50000 ./run_load_test.sh
```

**Windows**
```cmd
# Set environment variables first
set HOST=localhost
set PORT=8080
set THREADS=150
set DURATION=600
set THROUGHPUT=50000

# Run test
run_load_test.bat
```

### Manual JMeter Execution

```bash
jmeter -n \
  -t ingestion_load_test.jmx \
  -Jhost=localhost \
  -Jport=8080 \
  -Jthreads=100 \
  -Jduration=600 \
  -Jrampup=60 \
  -Jthroughput=50000 \
  -l results/results.jtl \
  -e -o results/html-report
```

## Test Scenarios

### Scenario 1: Baseline (10K events/sec)

Validates basic functionality under light load.

```bash
THROUGHPUT=10000 DURATION=300 ./run_load_test.sh
```

### Scenario 2: Target Load (50K events/sec)

Validates target throughput claim.

```bash
THROUGHPUT=50000 DURATION=600 ./run_load_test.sh
```

### Scenario 3: Peak Load (75K events/sec)

Tests system behavior beyond target to find limits.

```bash
THROUGHPUT=75000 DURATION=300 THREADS=200 ./run_load_test.sh
```

### Scenario 4: Sustained Load (10 minutes)

Validates stability over time.

```bash
THROUGHPUT=50000 DURATION=600 ./run_load_test.sh
```

### Scenario 5: Stress Test (Ramp-up)

Gradually increases load to observe breaking point.

```bash
# Run multiple tests with increasing throughput
for LOAD in 10000 25000 50000 75000 100000; do
    echo "Testing $LOAD events/sec..."
    THROUGHPUT=$LOAD DURATION=180 ./run_load_test.sh
    sleep 30
done
```

## Understanding Results

### HTML Report

After test completion, open the HTML report:
```bash
# Linux/macOS
open results/<timestamp>/html-report/index.html

# Windows
start results\<timestamp>\html-report\index.html
```

**Key Sections**:
1. **Dashboard** - Overview of test metrics
2. **Statistics** - Detailed request statistics
3. **Response Times** - Latency distribution
4. **Throughput** - Events per second over time

### Key Metrics Explained

**1. Throughput (events/sec)**
- Actual number of events processed per second
- Should be ≥50,000 for target validation
- Formula: `Total Requests / Test Duration`

**2. Success Rate (%)**
- Percentage of successful requests (HTTP 200)
- Should be ≥99.91% for target validation
- Formula: `(Success Count / Total Requests) × 100`

**3. Error Rate (%)**
- Percentage of failed requests
- Should be ≤0.09% (inverse of success rate)
- Common errors: timeouts, connection refused, HTTP 500

**4. Latency Percentiles**
- **P50 (Median)**: 50% of requests complete in this time
- **P95**: 95% of requests complete in this time
- **P99**: 99% of requests complete in this time (target: <150ms)
- **P99.9**: 99.9% of requests complete in this time

**5. Response Time Distribution**
- Shows how many requests fall into different latency buckets
- Ideal: Most requests in <50ms bucket

### Sample Output

```
Quick Summary:
  Total Requests: 30,045,782
  Successful: 30,018,651 (99.91%)
  Errors: 27,131 (0.09%)
  Actual Throughput: 50,076 events/sec

  P50 Latency: 23ms
  P95 Latency: 89ms
  P99 Latency: 147ms

Target Validation:
  ✓ Success Rate: 99.91% (target: ≥99.9%)
  ✓ Throughput: 50,076 events/sec (target: ≥50000/sec)
  ✓ P99 Latency: 147ms (target: <150ms)
```

## Interpreting JTL Files

The `.jtl` file contains raw test data in CSV format.

**Format**:
```
timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect
```

**Example Analysis with awk**:

```bash
# Calculate average latency
awk -F',' 'NR>1 {sum+=$2; count++} END {print "Average:", sum/count, "ms"}' results.jtl

# Count errors
awk -F',' 'NR>1 && $8=="false"' results.jtl | wc -l

# Get P99 latency
awk -F',' 'NR>1 {print $2}' results.jtl | sort -n | awk 'BEGIN{c=0} {a[c]=$1; c++} END{print a[int(c*0.99)]}'
```

## Monitoring During Tests

### Watch Prometheus Metrics

```bash
# Open Prometheus UI
open http://localhost:9090

# Useful queries:
# - rate(ingestion_events_total[1m]) - Events per second
# - histogram_quantile(0.99, rate(ingestion_latency_bucket[1m])) - P99 latency
# - rate(ingestion_errors_total[1m]) - Error rate
```

### Watch Grafana Dashboard

```bash
# Open Grafana
open http://localhost:3000  # admin/admin

# View "Helios - System Overview" dashboard
```

### Watch Kafka Lag

```bash
# Check consumer lag
docker-compose exec kafka kafka-consumer-groups \
  --bootstrap-server kafka:29092 \
  --describe \
  --group storage-writers
```

### Watch Container Resources

```bash
# Monitor CPU/Memory usage
docker stats helios-ingestion helios-kafka helios-timescaledb
```

## Troubleshooting

### Issue: Low Throughput

**Symptoms**: Actual throughput << target throughput

**Possible Causes**:
1. **Not enough threads**: Increase `THREADS` parameter
2. **Service bottleneck**: Check CPU/memory with `docker stats`
3. **Database bottleneck**: Check TimescaleDB connections
4. **Kafka bottleneck**: Check producer buffer settings

**Solutions**:
```bash
# Try more threads
THREADS=200 ./run_load_test.sh

# Check service health
docker-compose logs ingestion
docker-compose logs kafka

# Scale up services
docker-compose up -d --scale ingestion=3
```

### Issue: High Error Rate

**Symptoms**: Error rate >1%

**Possible Causes**:
1. **Connection refused**: Service not running
2. **Timeouts**: Service overloaded
3. **HTTP 500**: Application errors

**Solutions**:
```bash
# Check service logs
docker-compose logs -f ingestion

# Restart services
docker-compose restart ingestion

# Check database connectivity
docker-compose exec timescaledb psql -U postgres -d helios -c "SELECT 1;"
```

### Issue: High Latency

**Symptoms**: P99 latency >500ms

**Possible Causes**:
1. **Database slow queries**: Check pg_stat_statements
2. **Insufficient resources**: Check CPU/memory
3. **Network issues**: Check Docker network

**Solutions**:
```bash
# Check slow queries
docker-compose exec timescaledb psql -U postgres -d helios -c "
  SELECT query, mean_exec_time, calls
  FROM pg_stat_statements
  ORDER BY mean_exec_time DESC
  LIMIT 10;
"

# Increase resources in docker-compose.yml
resources:
  limits:
    cpus: '4'
    memory: 8G
```

### Issue: JMeter Connection Errors

**Symptoms**: "Connection reset" or "Connection refused"

**Solutions**:
```bash
# Check service is running
curl http://localhost:8080/health

# Check port binding
netstat -an | grep 8080

# Reduce ramp-up time
RAMPUP=120 ./run_load_test.sh  # Slower ramp-up
```

## Best Practices

1. **Warm-up**: Run a 1-minute test before the real test to warm up the JVM
2. **Monitor**: Watch metrics in Grafana during tests
3. **Baseline**: Always establish a baseline before optimization
4. **Multiple Runs**: Run tests 3-5 times and average results
5. **Clean State**: Restart services between major tests
6. **Resource Limits**: Ensure Docker has sufficient CPU/memory allocation
7. **Save Results**: Keep JTL files and reports for comparison

## Example Workflow

```bash
# 1. Start services
docker-compose up -d

# 2. Wait for health
sleep 30

# 3. Run warm-up test (1 minute, 10K events/sec)
THROUGHPUT=10000 DURATION=60 ./run_load_test.sh

# 4. Run baseline test (5 minutes, 25K events/sec)
THROUGHPUT=25000 DURATION=300 ./run_load_test.sh

# 5. Run target test (10 minutes, 50K events/sec)
THROUGHPUT=50000 DURATION=600 ./run_load_test.sh

# 6. Run peak test (5 minutes, 75K events/sec)
THROUGHPUT=75000 DURATION=300 THREADS=200 ./run_load_test.sh

# 7. Analyze results
ls -lh results/
```

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/load-test.yml
name: Load Test

on:
  push:
    branches: [main]

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Start services
        run: docker-compose up -d

      - name: Wait for health
        run: |
          timeout 60 bash -c 'until curl -f http://localhost:8080/health; do sleep 2; done'

      - name: Install JMeter
        run: |
          wget https://dlcdn.apache.org/jmeter/binaries/apache-jmeter-5.6.2.tgz
          tar -xzf apache-jmeter-5.6.2.tgz
          echo "$(pwd)/apache-jmeter-5.6.2/bin" >> $GITHUB_PATH

      - name: Run load test
        run: |
          cd tests/load
          DURATION=300 THROUGHPUT=25000 ./run_load_test.sh

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: load-test-results
          path: tests/load/results/
```

## Further Reading

- [JMeter User Manual](https://jmeter.apache.org/usermanual/index.html)
- [JMeter Best Practices](https://jmeter.apache.org/usermanual/best-practices.html)
- [Performance Testing Guide](https://martinfowler.com/articles/performance-testing.html)
