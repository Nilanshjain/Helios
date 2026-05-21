# Sample reports — generated live by Helios

These four markdown files are **verbatim Gemini outputs**, structured through
the production `IncidentReport` Pydantic schema and rendered by
`services/reporting/app/generators/structured_output.py::to_markdown`. They
were captured from the live `reporting-consumer` after it processed real
anomalies that flowed through the Kafka pipeline.

Each file's frontmatter shows the actual run metadata: model, token count,
cost in USD, end-to-end latency, and timestamp.

## What to look for when reading these

These reports demonstrate three properties that the Phase 3 design promised:

1. **SHAP-grounded root cause.** Each `Root cause hypothesis` section names
   at least one feature from the SHAP attribution block by name (e.g.,
   `p99_latency_ms`, `latency_std`, `error_count`). The prompt constraint
   enforces this — the model is not free to drift into generic SRE prose.

2. **Tiered recommended actions.** Every report has one action for each of
   the `immediate`, `short_term`, and `long_term` timeframes, with a
   rationale tied to specific evidence (a SHAP feature value, a log line,
   or a metric).

3. **Service-specific monitoring follow-up.** Each report names 3-4
   actual metrics to graph after triage — e.g.,
   `payment_service_db_timeout_count`, `database_connection_pool_utilization`
   — rather than vague suggestions like "check the dashboard".

## Aggregate run statistics

| Stat | Value |
|---|---|
| Reports generated in this run | 11 |
| Model | `gemini-flash-lite-latest` (free-tier) |
| Average cost per report | $0.00030 |
| Average tokens per report | 1874 |
| Average end-to-end latency | ~5 seconds |
| Implied daily cost at free-tier max (1500 reports/day) | $0.45 |

## Files

| File | Severity | Why it's interesting |
|---|---|---|
| `payment-service-CRITICAL.md` | CRITICAL | Most dramatic — 50.5% error rate, p99=6430ms, infers connection-pool exhaustion |
| `auth-service-HIGH.md` | HIGH | Longest output; names all three top SHAP features in the hypothesis |
| `order-service-HIGH.md` | HIGH | Mid-incident snapshot of the pipeline |
| `inventory-service-HIGH.md` | HIGH | Clean concise example showcasing the schema |

Rendered PDF versions — the same reports as the reporting service produces them
with WeasyPrint — are in [`pdf/`](pdf/).
[`pdf/payment-service-CRITICAL-incident-report.pdf`](pdf/payment-service-CRITICAL-incident-report.pdf)
is the one to open first.

## Reproducing one of these

The reporting consumer's path is exercised by
`scripts/diagnose_reporting.py`, which calls the same `GeminiGenerator.generate()`
that the consumer calls:

```bash
docker cp scripts/diagnose_reporting.py helios-reporting-consumer:/tmp/
docker exec -e PYTHONPATH=/app helios-reporting-consumer python /tmp/diagnose_reporting.py
```

Expect one new entry in the `incident_reports` table and ~$0.0003 of Gemini
spend per run.
