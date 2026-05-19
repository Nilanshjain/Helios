-- Helios Demo Data Population Script
-- Generates realistic demo data for dashboard showcase

\set QUIET on
\set ON_ERROR_STOP on

\echo '============================================'
\echo 'Helios Demo Data Generator (SQL)'
\echo '============================================'
\echo ''

-- Generate diverse events across 14 microservices
\echo 'Generating events...'

DO $$
DECLARE
    services TEXT[] := ARRAY['api-gateway', 'auth-service', 'user-service', 'order-service',
                             'inventory-service', 'payment-service', 'notification-service',
                             'analytics-service', 'search-service', 'recommendation-engine',
                             'data-pipeline', 'cache-service', 'email-worker', 'image-processor'];
    levels TEXT[] := ARRAY['DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL'];
    messages TEXT[];
    i INTEGER;
    service TEXT;
    level TEXT;
    msg TEXT;
    ts TIMESTAMP;
BEGIN
    messages := ARRAY[
        'Request processed successfully',
        'Database query completed',
        'Cache hit for key',
        'User authenticated',
        'Payment processed',
        'Email sent successfully',
        'API rate limit approaching',
        'Slow query detected',
        'Connection pool near capacity',
        'Failed to connect to database',
        'Payment gateway timeout',
        'Authentication failed',
        'Circuit breaker opened',
        'Out of memory warning',
        'Disk space critical'
    ];

    FOR i IN 1..10000 LOOP
        service := services[1 + floor(random() * array_length(services, 1))::int];
        level := CASE
            WHEN random() < 0.60 THEN 'INFO'
            WHEN random() < 0.75 THEN 'DEBUG'
            WHEN random() < 0.90 THEN 'WARN'
            WHEN random() < 0.98 THEN 'ERROR'
            ELSE 'CRITICAL'
        END;
        msg := messages[1 + floor(random() * array_length(messages, 1))::int];
        ts := NOW() - (random() * interval '7 days');

        INSERT INTO events (time, service, level, message, metadata, host, ingested_at)
        VALUES (
            ts,
            service,
            level,
            msg || ' [' || i || ']',
            jsonb_build_object(
                'environment', 'production',
                'version', 'v' || (1 + floor(random() * 5))::text || '.' || floor(random() * 20)::text,
                'region', CASE floor(random() * 3)::int
                    WHEN 0 THEN 'us-east-1'
                    WHEN 1 THEN 'us-west-2'
                    ELSE 'eu-west-1'
                END
            ),
            service || '-pod-' || (1 + floor(random() * 5))::int,
            ts + (random() * interval '50 milliseconds')
        );

        IF i % 2000 = 0 THEN
            RAISE NOTICE '  Generated % events...', i;
        END IF;
    END LOOP;

    RAISE NOTICE '√ Successfully inserted 10000 events';
END $$;

-- Generate diverse anomalies
\echo ''
\echo 'Generating anomalies...'

DO $$
DECLARE
    services TEXT[] := ARRAY['api-gateway', 'auth-service', 'user-service', 'order-service',
                             'payment-service', 'notification-service', 'analytics-service'];
    severities TEXT[] := ARRAY['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'];
    i INTEGER;
    service TEXT;
    severity TEXT;
    ts TIMESTAMP;
    features JSONB;
    score FLOAT;
    confidence FLOAT;
BEGIN
    FOR i IN 1..20 LOOP
        service := services[1 + floor(random() * array_length(services, 1))::int];
        severity := CASE floor(random() * 4)::int
            WHEN 0 THEN 'CRITICAL'
            WHEN 1 THEN 'HIGH'
            WHEN 2 THEN 'MEDIUM'
            ELSE 'LOW'
        END;
        ts := NOW() - (random() * interval '7 days');

        -- Generate realistic features based on severity
        IF severity IN ('CRITICAL', 'HIGH') THEN
            features := jsonb_build_object(
                'cpu_usage', 0.85 + random() * 0.14,
                'memory_usage', 0.80 + random() * 0.15,
                'error_rate', 0.30 + random() * 0.40,
                'latency_ms', 2000 + random() * 6000,
                'request_rate', 500 + random() * 1500
            );
            score := -0.95 + random() * 0.20;
            confidence := 0.85 + random() * 0.13;
        ELSIF severity = 'MEDIUM' THEN
            features := jsonb_build_object(
                'cpu_usage', 0.65 + random() * 0.20,
                'memory_usage', 0.60 + random() * 0.20,
                'error_rate', 0.15 + random() * 0.15,
                'latency_ms', 1000 + random() * 1000,
                'request_rate', 300 + random() * 200
            );
            score := -0.75 + random() * 0.15;
            confidence := 0.70 + random() * 0.15;
        ELSE
            features := jsonb_build_object(
                'cpu_usage', 0.50 + random() * 0.15,
                'memory_usage', 0.45 + random() * 0.15,
                'error_rate', 0.05 + random() * 0.10,
                'latency_ms', 500 + random() * 500,
                'request_rate', 100 + random() * 200
            );
            score := -0.60 + random() * 0.10;
            confidence := 0.60 + random() * 0.15;
        END IF;

        INSERT INTO anomalies (anomaly_id, time, service, score, threshold, severity, features, confidence, is_resolved, resolved_at)
        VALUES (
            'anomaly_' || service || '_' || i || '_' || extract(epoch from ts)::bigint,
            ts,
            service,
            score,
            -0.7,
            severity,
            features,
            confidence,
            random() > 0.4,  -- 60% resolved
            CASE WHEN random() > 0.4 THEN ts + (random() * interval '24 hours') ELSE NULL END
        );
    END LOOP;

    RAISE NOTICE '√ Successfully inserted 20 anomalies';
END $$;

-- Generate AI reports
\echo ''
\echo 'Generating incident reports...'

DO $$
DECLARE
    anomaly RECORD;
    report_id TEXT;
    ts TIMESTAMP;
    tokens INT;
    cost FLOAT;
    content TEXT;
    markdown_path TEXT;
    pdf_path TEXT;
BEGIN
    FOR anomaly IN
        SELECT a.anomaly_id, a.service, a.severity, a.time
        FROM anomalies a
        WHERE NOT EXISTS (SELECT 1 FROM incident_reports WHERE incident_reports.anomaly_id = a.anomaly_id)
        LIMIT 20
    LOOP
        ts := anomaly.time + (random() * interval '2 hours');
        report_id := 'report_' || anomaly.anomaly_id;
        tokens := 1500 + floor(random() * 2500)::int;
        cost := tokens * 0.000003;  -- $3 per 1M tokens

        content := '# Incident Report: ' || anomaly.anomaly_id || E'\n\n' ||
                   '## Executive Summary' || E'\n' ||
                   'Anomaly detected in ' || anomaly.service || ' with ' || anomaly.severity || ' severity.' || E'\n\n' ||
                   '## Technical Analysis' || E'\n' ||
                   '- Service: ' || anomaly.service || E'\n' ||
                   '- Severity: ' || anomaly.severity || E'\n' ||
                   '- Detection Time: ' || anomaly.time::text || E'\n\n' ||
                   '## Recommendations' || E'\n' ||
                   '1. Investigate resource usage patterns' || E'\n' ||
                   '2. Review recent deployments' || E'\n' ||
                   '3. Monitor for similar patterns' || E'\n\n' ||
                   '---' || E'\n' ||
                   'Generated by Claude AI';

        markdown_path := to_char(ts, 'YYYY/MM/DD/') || report_id || '.markdown';
        pdf_path := to_char(ts, 'YYYY/MM/DD/') || report_id || '.pdf';

        INSERT INTO incident_reports (
            report_id, anomaly_id, service, severity, filepath, pdf_path,
            content, tokens_used, cost_usd, generation_time_ms, model, generated_at
        )
        VALUES (
            report_id,
            anomaly.anomaly_id,
            anomaly.service,
            anomaly.severity,
            markdown_path,
            pdf_path,
            content,
            tokens,
            cost,
            3000 + floor(random() * 5000)::int,
            'claude-3-5-sonnet-20241022',
            ts
        )
        ;
    END LOOP;

    RAISE NOTICE '√ Successfully inserted reports';
END $$;

-- Show statistics
\echo ''
\echo '============================================'
\echo 'Database Statistics:'
\echo '============================================'

SELECT
    'Total Events:      ' || COUNT(*)::text AS statistic
FROM events
UNION ALL
SELECT
    'Total Anomalies:   ' || COUNT(*)::text
FROM anomalies
UNION ALL
SELECT
    'Total Reports:     ' || COUNT(*)::text
FROM incident_reports
UNION ALL
SELECT
    'Active Services:   ' || COUNT(DISTINCT service)::text
FROM events;

\echo '============================================'
\echo ''
\echo '√ Demo data generation complete!'
\echo ''
