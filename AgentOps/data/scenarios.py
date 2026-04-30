"""
Hardcoded incident scenarios used by the AgentOps demo pipeline.

Each scenario provides:
  * a normalized signal envelope (Section 1 — Signal Ingestion schema)
  * pre-built context (logs, traces, deploys, runbooks, similar incidents)
  * a metrics dashboard for the UI
  * a multi-action remediation plan with concrete commands
  * an "expected reasoning" narrative used by the simulation fallback
  * before/after monitoring numbers for the post-action stage
  * scenario-specific tuning hints (irreversibility, blast radius, data gravity)
"""

from __future__ import annotations

from typing import Any


SCENARIOS: dict[str, dict[str, Any]] = {
    # ==================================================================
    # 1. DB connection pool exhausted
    # ==================================================================
    "db_pool_exhausted": {
        "id": "db_pool_exhausted",
        "label": "DB Connection Pool Exhausted",
        "category": "Database",
        "signal": {
            "signal_id": "SIG-a3f8c2d1",
            "alert_id": "ALT-20260425-0847",
            "source": "datadog",
            "signal_type": "alert",
            "severity": "critical",
            "timestamp": "2026-04-25T08:47:11Z",
            "service": "payments-service",
            "environment": "production",
            "raw_payload": {
                "alert_id": "ALT-20260425-0847",
                "source": "datadog",
                "severity": "CRITICAL",
                "service": "payments-service",
                "metric": "db.connections.active",
                "current_value": 500,
                "threshold": 500,
                "message": "DB connection pool exhausted",
            },
            "normalized_summary": "DB pool exhausted (500/500) — 34% error rate",
            "ingestion_latency_ms": 312,
        },
        "metrics_dashboard": [
            {"label": "Error Rate",      "value": "34%",        "color": "red",    "sub": "↑ from 0.1%"},
            {"label": "P99 Latency",     "value": "8.4s",       "color": "red",    "sub": "↑ from 180ms"},
            {"label": "DB Connections",  "value": "500/500",    "color": "red",    "sub": "Pool exhausted"},
            {"label": "Queue Depth",     "value": "14,230",     "color": "red",    "sub": "Growing"},
            {"label": "Active Requests", "value": "2,847",      "color": "yellow", "sub": "3x normal"},
            {"label": "CPU",             "value": "23%",        "color": "green",  "sub": "Normal"},
        ],
        "context": {
            "recent_logs": [
                "[08:47:11] ERROR HikariCP - Connection not available, request timed out after 30000ms",
                "[08:47:12] ERROR FATAL: connection pool exhausted (active=500, idle=0, waiting=234)",
                "[08:47:13] ERROR PaymentProcessor: SQLException - could not acquire connection",
                "[08:47:14] WARN  Circuit breaker OPEN for db-primary",
                "[08:47:15] ERROR 847 transactions failed in last 60s",
                "[08:47:16] ERROR Deadlock detected: PID 34521 waited for ShareLock on txn 8821043",
                "[08:47:17] WARN  Retry queue depth: 14,230 (growing)",
                "[08:47:18] INFO  Health check: UNHEALTHY - db connectivity failed",
            ],
            "active_traces": [
                {"trace_id": "abc123", "span": "POST /v1/charges",        "duration_ms": 30021, "status": "error"},
                {"trace_id": "abc124", "span": "db.query.SELECT_account", "duration_ms": 30000, "status": "timeout"},
            ],
            "system_health": {
                "service":     "payments-service (pod: payments-7d4b9c-x9p2k)",
                "replicas":    "5/5 running",
                "cpu":         "23% (normal)",
                "db_pool":     "500/500 EXHAUSTED",
                "last_deploy": "v3.4.1 @ 2026-04-25T06:12:00Z (2h 35m ago)",
                "on_call":     "@alex.chen",
            },
            "recent_deployments": [
                {"version": "v3.4.1", "deployed_at": "2026-04-25T06:12:00Z", "author": "alex@apexon",
                 "notes": "Enhanced retry logic in PaymentProcessor"},
            ],
            "retrieved_tsgs": [
                {"title": "DB Connection Pool Exhaustion Runbook", "relevance_score": 0.94,
                 "content": "Check long-running queries. Increase pool size temporarily. Kill idle connections. Check for connection leaks in recent deployments."},
                {"title": "HikariCP Tuning Guide", "relevance_score": 0.87,
                 "content": "maximumPoolSize default 10 — increase to 50-100 for high-traffic. connectionTimeout: 30s. Check keepAliveTime."},
                {"title": "Payment Service DB Failover Procedure", "relevance_score": 0.72,
                 "content": "If primary DB unavailable, promote read replica. Update connection string."},
            ],
            "similar_past_incidents": [
                {"id": "INC-2891", "date": "2026-01-08", "similarity": 0.94, "outcome": "success",
                 "summary": "Connection leak after new retry logic in PaymentProcessor — connections not returned on exception path.",
                 "resolution": "Fixed try-with-resources, deployed v2.8.5."},
            ],
            "oncall_info": {"name": "Alex Chen", "slack_handle": "@alex.chen"},
        },
        "expected_hypotheses": [
            {"hypothesis": "Connection leak from v3.4.1 deployment",
             "detail": "v3.4.1 deployed 2h35m ago. Exception paths in new retry logic may not return connections to pool.",
             "prior": 0.88},
            {"hypothesis": "Deadlock causing connection accumulation",
             "detail": "Deadlock detected in logs. Long-running transactions holding connections without releasing.",
             "prior": 0.71},
            {"hypothesis": "Traffic spike exceeding pool capacity",
             "detail": "Active requests 3x normal. Pool size may be insufficient for current load.",
             "prior": 0.42},
        ],
        "expected_reasoning_narrative": """\
Step 1 — Timeline correlation:
  Deploy v3.4.1 @ 06:12 UTC → degradation began ~08:30 UTC (2h18m gap)
  Gradual accumulation pattern → connection leak, not immediate regression.

Step 2 — Log pattern:
  "pool exhausted active=500 idle=0" → all 500 connections held, none returned
  Classic connection leak signature.

Step 3 — Historical match:
  INC-2891: identical — connection leak in retry logic, fixed with try-with-resources
  v3.4.1 changelog: "enhanced retry logic in PaymentProcessor" → HIGH CORRELATION

Step 4 — Ruling out traffic spike:
  CPU 23%, memory 67% → normal. Traffic spike would show elevated CPU.

CONCLUSION: Connection leak in v3.4.1 PaymentProcessor retry logic.
ACTION: Kill idle connections + increase pool temporarily + rollback v3.4.1.""",
        "expected_actions": [
            {"title": "Increase DB pool size temporarily",
             "description": "Emergency increase pool max 500→750 to restore capacity.",
             "command": "kubectl set env deployment/payments-service HIKARI_MAX_POOL_SIZE=750 -n production",
             "decision": "auto", "risk": "low", "confidence": 0.92},
            {"title": "Kill orphaned idle connections",
             "description": "Terminate connections idle >60s not properly released.",
             "command": "psql -h db-primary -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state='idle' AND query_start < now()-interval '60s';\"",
             "decision": "auto", "risk": "low", "confidence": 0.89},
            {"title": "Roll back to v3.4.0",
             "description": "Roll back deployment that introduced the connection leak.",
             "command": "kubectl rollout undo deployment/payments-service -n production",
             "decision": "human", "risk": "medium", "confidence": 0.84},
        ],
        "before_after_metrics": [
            {"label": "Error Rate",     "before": "34%",     "after": "0.2%"},
            {"label": "DB Connections", "before": "500/500", "after": "127/750"},
            {"label": "P99 Latency",    "before": "8.4s",    "after": "210ms"},
            {"label": "Queue Depth",    "before": "14,230",  "after": "0"},
        ],
        "tuning": {
            "expected_winning_hypothesis": "Connection leak from v3.4.1 deployment",
            "irreversibility": "semi_reversible",
            "blast_radius_services": ["order-service", "checkout-service"],
            "data_gravity": {"pii": False, "phi": False, "pci": True},
            "expected_dec": "human",
        },
    },

    # ==================================================================
    # 2. OOM crash loop
    # ==================================================================
    "oom_crash_loop": {
        "id": "oom_crash_loop",
        "label": "Memory Leak → OOM Crash Loop",
        "category": "Memory",
        "signal": {
            "signal_id": "SIG-b9e1f4a2",
            "alert_id": "ALT-20260425-1022",
            "source": "kubernetes",
            "signal_type": "pod_event",
            "severity": "critical",
            "timestamp": "2026-04-25T10:22:11Z",
            "service": "recommendation-engine",
            "environment": "production",
            "raw_payload": {
                "alert_id": "ALT-20260425-1022",
                "source": "kubernetes",
                "signal_type": "pod_event",
                "severity": "CRITICAL",
                "service": "recommendation-engine",
                "reason": "OOMKilled",
                "message": "Container exceeded memory limit 2Gi",
                "restart_count": 7,
            },
            "normalized_summary": "Crash loop (7 restarts) — OOMKilled, 2Gi limit exceeded",
            "ingestion_latency_ms": 198,
        },
        "metrics_dashboard": [
            {"label": "Pod Restarts", "value": "7",     "color": "red",    "sub": "Last 30 min"},
            {"label": "Memory",       "value": "98%",   "color": "red",    "sub": "OOMKilled"},
            {"label": "Error Rate",   "value": "61%",   "color": "red",    "sub": "↑ from 0.3%"},
            {"label": "Cache Hit",    "value": "8%",    "color": "red",    "sub": "↓ from 89%"},
            {"label": "Replicas",     "value": "1/4",   "color": "red",    "sub": "3 OOMKilled"},
            {"label": "CPU",          "value": "41%",   "color": "yellow", "sub": "Elevated (GC)"},
        ],
        "context": {
            "recent_logs": [
                "[10:18:42] WARN  Memory usage 85% - approaching limit (1.7Gi/2Gi)",
                "[10:19:11] WARN  ML model cache growing: 847MB (unbounded)",
                "[10:19:44] ERROR GC overhead limit exceeded - full GC taking >80% CPU time",
                "[10:20:02] ERROR java.lang.OutOfMemoryError: Java heap space",
                "[10:20:03] ERROR Container killed by OOM killer (exit code 137)",
                "[10:21:30] INFO  Container restarted (restart #6)",
                "[10:21:45] WARN  Cache warming started - loading 1.2M model embeddings",
                "[10:22:11] ERROR OOMKilled again on restart #7",
            ],
            "active_traces": [
                {"trace_id": "rec001", "span": "GET /v1/recommend/user/<id>", "duration_ms": 4500, "status": "killed"},
            ],
            "system_health": {
                "service":     "recommendation-engine",
                "replicas":    "1/4 (3 OOMKilled)",
                "memory":      "1.98Gi/2Gi (99%)",
                "cpu":         "41% (GC overhead)",
                "cache":       "unbounded ML model cache detected",
                "last_deploy": "v2.1.0 @ 2026-04-25T09:45:00Z (37m ago)",
                "jvm_flags":   "-Xmx1800m",
                "on_call":     "@priya.sharma",
            },
            "recent_deployments": [
                {"version": "v2.1.0", "deployed_at": "2026-04-25T09:45:00Z", "author": "priya@apexon",
                 "notes": "Added ONNX model serving + new ML embedding cache"},
            ],
            "retrieved_tsgs": [
                {"title": "JVM OOM Crash Loop Recovery", "relevance_score": 0.96,
                 "content": "Increase memory limits. Add heap dump on OOM. Check for unbounded caches."},
                {"title": "ML Model Cache Eviction Policy", "relevance_score": 0.91,
                 "content": "CACHE_MAX_SIZE_MB must be set explicitly — default is unlimited. Set via env var."},
                {"title": "Kubernetes OOMKill Remediation", "relevance_score": 0.83,
                 "content": "Increase pod memory limit or reduce consumption. Scale up replicas to restore capacity."},
            ],
            "similar_past_incidents": [
                {"id": "INC-3087", "date": "2026-02-20", "similarity": 0.96, "outcome": "success",
                 "summary": "OOM on recommendation-engine due to unbounded Guava cache loading all user embeddings.",
                 "resolution": "Set CACHE_MAX_SIZE_MB=512, deployed fix in v1.9.2."},
            ],
            "oncall_info": {"name": "Priya Sharma", "slack_handle": "@priya.sharma"},
        },
        "expected_hypotheses": [
            {"hypothesis": "Unbounded ML cache after v2.1.0 deploy",
             "detail": "v2.1.0 deployed 37m ago. Logs show cache growing without bound. TSG: CACHE_MAX_SIZE_MB must be set — missing in new deployment.",
             "prior": 0.93},
            {"hypothesis": "JVM heap too small for workload",
             "detail": "-Xmx1800m leaves 200MB for native. Combined with large cache, heap exhausted.",
             "prior": 0.67},
            {"hypothesis": "Memory leak in new model serving code",
             "detail": "v2.1.0 introduced ONNX model serving. Possible native memory leak.",
             "prior": 0.38},
        ],
        "expected_reasoning_narrative": """\
Step 1 — Crash pattern:
  7 restarts in 30 min. Each: cache warming → OOM → killed → repeat.
  "Loading 1.2M model embeddings" on EVERY restart is the death cycle.

Step 2 — Root cause fingerprint:
  "ML model cache growing: 847MB (unbounded)"
  TSG: "CACHE_MAX_SIZE_MB must be set explicitly, default is unlimited"
  Deploy v2.1.0 37m ago — high temporal correlation.
  INC-3087 identical pattern confirmed.

Step 3 — Confirmation:
  kubectl get deploy reco-engine → CACHE_MAX_SIZE_MB NOT SET in env
  Missing env var = unbounded cache = root cause confirmed.

Step 4 — Break the loop:
  Set CACHE_MAX_SIZE_MB=512 → caps cache → no more OOM
  Increase memory limit to 3Gi → headroom during warmup
  Scale replicas to restore capacity

CONCLUSION: Missing CACHE_MAX_SIZE_MB in v2.1.0 → unbounded cache → OOM.
All 3 fixes are low-risk, auto-executable.""",
        "expected_actions": [
            {"title": "Set cache size limit (break crash loop)",
             "description": "Set CACHE_MAX_SIZE_MB=512 to cap ML model cache immediately.",
             "command": "kubectl set env deployment/recommendation-engine CACHE_MAX_SIZE_MB=512 -n production",
             "decision": "auto", "risk": "low", "confidence": 0.93},
            {"title": "Increase memory limit to 3Gi",
             "description": "Give pod headroom during cache warmup while fix takes effect.",
             "command": "kubectl patch deployment recommendation-engine -n production -p '{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"recommendation-engine\",\"resources\":{\"limits\":{\"memory\":\"3Gi\"}}}]}}}}'",
             "decision": "auto", "risk": "low", "confidence": 0.88},
            {"title": "Scale up replicas to restore capacity",
             "description": "Only 1/4 replicas running — scale to 6 to handle current traffic.",
             "command": "kubectl scale deployment recommendation-engine --replicas=6 -n production",
             "decision": "auto", "risk": "low", "confidence": 0.85},
        ],
        "before_after_metrics": [
            {"label": "Pod Restarts",   "before": "7",    "after": "0"},
            {"label": "Memory Usage",   "before": "98%",  "after": "54%"},
            {"label": "Error Rate",     "before": "61%",  "after": "0.4%"},
            {"label": "Replicas Up",    "before": "1/4",  "after": "6/6"},
        ],
        "tuning": {
            "expected_winning_hypothesis": "Unbounded ML cache after v2.1.0 deploy",
            "irreversibility": "reversible",
            "blast_radius_services": ["product-search"],
            "data_gravity": {"pii": False, "phi": False, "pci": False},
            "expected_dec": "auto",
        },
    },

    # ==================================================================
    # 3. API gateway P99 latency spike
    # ==================================================================
    "api_p99_latency_spike": {
        "id": "api_p99_latency_spike",
        "label": "API Gateway P99 Latency Spike",
        "category": "Latency",
        "signal": {
            "signal_id": "SIG-c7d2e5b3",
            "alert_id": "ALT-20260425-1435",
            "source": "cloudwatch",
            "signal_type": "alert",
            "severity": "high",
            "timestamp": "2026-04-25T14:35:07Z",
            "service": "api-gateway",
            "environment": "production",
            "raw_payload": {
                "alert_id": "ALT-20260425-1435",
                "source": "cloudwatch",
                "severity": "HIGH",
                "service": "api-gateway",
                "metric": "TargetResponseTime.p99",
                "threshold": 2.0,
                "current_value": 12.3,
                "message": "P99 latency 12.3s exceeds 2s threshold",
            },
            "normalized_summary": "P99 spike to 12.3s — 18% timeout rate, 504 errors",
            "ingestion_latency_ms": 445,
        },
        "metrics_dashboard": [
            {"label": "P99 Latency",   "value": "12.3s",     "color": "red",    "sub": "↑ from 250ms"},
            {"label": "Timeout Rate",  "value": "18%",       "color": "red",    "sub": "↑ from 0.01%"},
            {"label": "504 Errors",    "value": "2,100/min", "color": "red",    "sub": "Gateway Timeout"},
            {"label": "P50 Latency",   "value": "340ms",     "color": "yellow", "sub": "Slightly elevated"},
            {"label": "Upstream Errs", "value": "18%",       "color": "red",    "sub": "user-profile-svc"},
            {"label": "Throughput",    "value": "4,200 rps", "color": "green",  "sub": "Normal"},
        ],
        "context": {
            "recent_logs": [
                "[14:32:01] WARN  upstream timeout: user-profile-service /api/v2/profile (10s exceeded)",
                "[14:32:15] ERROR 504 Gateway Timeout → GET /api/v2/recommendations (upstream: user-profile-svc)",
                "[14:33:00] WARN  connection pool to user-profile-svc: 45/50 busy",
                "[14:34:30] INFO  slow query: SELECT * FROM user_preferences JOIN feature_flags... (took 11.2s)",
                "[14:35:00] ERROR missing index on user_preferences.user_id after migration 0042",
                "[14:35:07] WARN  circuit breaker threshold approaching: 18% errors on user-profile-svc",
            ],
            "active_traces": [
                {"trace_id": "gw9001", "span": "GET /api/v2/profile", "duration_ms": 11200, "status": "timeout"},
                {"trace_id": "gw9002", "span": "user-profile-svc.SELECT user_preferences", "duration_ms": 11200, "status": "ok"},
            ],
            "system_health": {
                "service":        "api-gateway (nginx + lua)",
                "replicas":       "8/8 running (healthy)",
                "cpu":            "18% (normal)",
                "upstream_bad":   "user-profile-svc → 18% errors, 11s avg latency",
                "upstream_good":  "all other services → <0.1% errors",
                "last_migration": "0042_add_feature_flags (2026-04-25T13:55:00Z, 40m ago)",
                "on_call":        "@dmitri.volkov",
            },
            "recent_deployments": [
                {"version": "migration-0042", "deployed_at": "2026-04-25T13:55:00Z", "author": "dmitri@apexon",
                 "notes": "0042_add_feature_flags — added feature_flags table and joined query"},
            ],
            "retrieved_tsgs": [
                {"title": "API Gateway Upstream Timeout Runbook", "relevance_score": 0.91,
                 "content": "Isolate slow upstream via access logs. Enable circuit breaker if error rate >10%. Check for slow queries after DB migrations."},
                {"title": "PostgreSQL Missing Index Recovery", "relevance_score": 0.89,
                 "content": "Run EXPLAIN ANALYZE on slow query. Add index CONCURRENTLY (non-blocking). Monitor post-index."},
                {"title": "Circuit Breaker Configuration", "relevance_score": 0.76,
                 "content": "Enable on user-profile-svc. Set threshold 20%. Provide fallback (cached profile)."},
            ],
            "similar_past_incidents": [
                {"id": "INC-3199", "date": "2026-03-28", "similarity": 0.88, "outcome": "success",
                 "summary": "Missing index after migration on orders-service, P99 spiked to 9s.",
                 "resolution": "Added index CONCURRENTLY, restored in 4 minutes."},
            ],
            "oncall_info": {"name": "Dmitri Volkov", "slack_handle": "@dmitri.volkov"},
        },
        "expected_hypotheses": [
            {"hypothesis": "Missing DB index after migration 0042",
             "detail": "Migration 0042 ran 40m ago. Logs: \"missing index on user_preferences.user_id\". Slow query 11.2s matches P99. Classic post-migration pattern.",
             "prior": 0.95},
            {"hypothesis": "user-profile-svc performance regression",
             "detail": "Isolated to one upstream — all others healthy. Code regression possible but migration timing more compelling.",
             "prior": 0.41},
            {"hypothesis": "DB host resource contention",
             "detail": "Less likely — specific index error rather than general load.",
             "prior": 0.22},
        ],
        "expected_reasoning_narrative": """\
Step 1 — Isolate slow upstream:
  P50=340ms (OK), P99=12.3s → tail latency, not systemic load
  All 504s trace to user-profile-svc → isolate to one service.

Step 2 — Timeline:
  migration 0042 @ 13:55 UTC (40m before alert)
  "missing index on user_preferences.user_id after migration 0042" → smoking gun

Step 3 — Confirm slow query:
  "SELECT * FROM user_preferences JOIN feature_flags... (took 11.2s)"
  user_preferences has ~50M rows → seq scan = 10-12s → matches P99 exactly.

Step 4 — Remediation:
  CREATE INDEX CONCURRENTLY (non-blocking, safe in prod) → 2-4 min build
  Enable circuit breaker NOW to stop 504 cascade
  After index built → latency returns to normal automatically.

CONCLUSION: migration 0042 dropped user_id index → full table scan → 11s queries → 504s.
SAFEST FIX: circuit breaker + CREATE INDEX CONCURRENTLY (no rollback needed).""",
        "expected_actions": [
            {"title": "Enable circuit breaker on user-profile-svc",
             "description": "Stop 504 cascade immediately. Return cached/empty profile as fallback.",
             "command": "kubectl set env deployment/api-gateway USER_PROFILE_CIRCUIT_BREAKER=true -n production",
             "decision": "auto", "risk": "low", "confidence": 0.91},
            {"title": "Create missing index CONCURRENTLY",
             "description": "Non-blocking index creation safe in production. Will resolve query latency.",
             "command": "psql -h db-primary -d userdb -c 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_prefs_user_id ON user_preferences(user_id);'",
             "decision": "auto", "risk": "low", "confidence": 0.95},
            {"title": "Disable circuit breaker post-recovery",
             "description": "After index built (monitor pg_stat_progress_create_index), restore full routing.",
             "command": "kubectl set env deployment/api-gateway USER_PROFILE_CIRCUIT_BREAKER=false -n production",
             "decision": "human", "risk": "low", "confidence": 0.88},
        ],
        "before_after_metrics": [
            {"label": "P99 Latency",     "before": "12.3s",  "after": "235ms"},
            {"label": "Timeout Rate",    "before": "18%",    "after": "0.01%"},
            {"label": "504 Errors/min",  "before": "2,100",  "after": "0"},
            {"label": "Upstream Errors", "before": "18%",    "after": "0.08%"},
        ],
        "tuning": {
            "expected_winning_hypothesis": "Missing DB index after migration 0042",
            "irreversibility": "reversible",
            "blast_radius_services": ["all-customer-traffic"],
            "data_gravity": {"pii": False, "phi": False, "pci": False},
            "expected_dec": "auto",
        },
    },

    # ==================================================================
    # 4. TLS cert expiring (escalate)
    # ==================================================================
    "tls_cert_expiring": {
        "id": "tls_cert_expiring",
        "label": "TLS Certificate Expiring in 47h",
        "category": "Security",
        "signal": {
            "signal_id": "SIG-d4a8b1c9",
            "alert_id": "ALT-20260425-0600",
            "source": "cert-manager",
            "signal_type": "certificate_expiry",
            "severity": "high",
            "timestamp": "2026-04-25T06:00:01Z",
            "service": "api.company.com",
            "environment": "production",
            "raw_payload": {
                "alert_id": "ALT-20260425-0600",
                "source": "cert-manager",
                "signal_type": "certificate_expiry",
                "severity": "HIGH",
                "certificate": "wildcard-company-com",
                "expiry": "2026-04-27T06:00:00Z",
                "hours_remaining": 47,
                "auto_renewal_status": "FAILED",
                "failure_reason": "ACME DNS-01: Route53 AccessDenied",
            },
            "normalized_summary": "TLS wildcard cert expiring in 47h — renewal failed (IAM permission denied)",
            "ingestion_latency_ms": 89,
        },
        "metrics_dashboard": [
            {"label": "Cert Expires",      "value": "47h",       "color": "red",    "sub": "Action required!"},
            {"label": "Services Affected", "value": "12",        "color": "red",    "sub": "*.company.com"},
            {"label": "Auto-Renewal",      "value": "FAILED",    "color": "red",    "sub": "cert-manager"},
            {"label": "ACME Challenges",   "value": "3 FAILED",  "color": "red",    "sub": "DNS validation"},
            {"label": "Last Renewal",      "value": "89d ago",   "color": "yellow", "sub": "Previously OK"},
            {"label": "Traffic",           "value": "28,400rps", "color": "green",  "sub": "Normal"},
        ],
        "context": {
            "recent_logs": [
                "[06:00:01] WARN  Certificate wildcard-company-com expires in 48h",
                "[06:00:05] ERROR ACME DNS-01 challenge failed: Route53 ChangeResourceRecordSets AccessDenied",
                "[06:00:05] ERROR IAM role cert-manager-prod: missing route53:ChangeResourceRecordSets permission",
                "[06:00:06] ERROR Retry 1/3 failed: same IAM error",
                "[06:00:08] ERROR Retry 3/3 failed: CertificateRequest will not retry automatically",
                "[06:00:10] WARN  All 12 Ingress resources will fail TLS when cert expires 2026-04-27T06:00:00Z",
            ],
            "active_traces": [],
            "system_health": {
                "certificate":  "wildcard-company-com (*.company.com)",
                "issuer":       "letsencrypt-production (ACME DNS-01)",
                "expiry":       "2026-04-27T06:00:00Z (47h remaining)",
                "services":     "12 ingress resources using this cert",
                "renewal":      "FAILED — IAM permission denied",
                "iam_change":   "policy updated 2026-04-20 (security audit)",
                "on_call":      "@security-team, @platform-team",
            },
            "recent_deployments": [
                {"version": "iam-audit-2026-04-20", "deployed_at": "2026-04-20T12:00:00Z", "author": "secops@apexon",
                 "notes": "Tightened IAM policies as part of quarterly security audit"},
            ],
            "retrieved_tsgs": [
                {"title": "cert-manager ACME DNS-01 Failure Runbook", "relevance_score": 0.97,
                 "content": "Check IAM role permissions for Route53. Required: route53:ChangeResourceRecordSets, route53:GetChange, route53:ListHostedZonesByName."},
                {"title": "Emergency Certificate Renewal Procedure", "relevance_score": 0.93,
                 "content": "Fix IAM issue. Delete failed CertificateRequest. Trigger manual renewal via kubectl annotate."},
                {"title": "IAM Permission Rollback Guide", "relevance_score": 0.81,
                 "content": "Revert to previous IAM policy version via AWS Console > IAM > Policies > Policy versions."},
            ],
            "similar_past_incidents": [
                {"id": "INC-2801", "date": "2025-12-15", "similarity": 0.92, "outcome": "success",
                 "summary": "cert-manager DNS-01 failure due to Route53 hosted zone ARN change not updated in IAM.",
                 "resolution": "Updated IAM policy to wildcard ARN arn:aws:route53:::hostedzone/*"},
            ],
            "oncall_info": {"name": "Security Team", "slack_handle": "@security-team"},
        },
        "expected_hypotheses": [
            {"hypothesis": "IAM policy change removed Route53 permission",
             "detail": "IAM policy updated 5 days ago (security audit). Logs: AccessDenied for route53:ChangeResourceRecordSets on cert-manager-prod role.",
             "prior": 0.97},
            {"hypothesis": "Route53 hosted zone ARN changed",
             "detail": "If hosted zone was recreated, IAM policy may reference old ARN.",
             "prior": 0.31},
            {"hypothesis": "AWS service outage affecting Route53",
             "detail": "Unlikely — specific IAM error rather than service unavailable.",
             "prior": 0.04},
        ],
        "expected_reasoning_narrative": """\
Step 1 — Root cause:
  Error: "IAM role cert-manager-prod: missing route53:ChangeResourceRecordSets"
  IAM policy last updated: 2026-04-20 (security audit tightened permissions)
  CONCLUSION: Security audit removed the Route53 permission from cert-manager role.

Step 2 — Urgency assessment:
  47 hours → must act within 24h for safety buffer
  12 services affected → total HTTPS outage if cert expires
  This is a P0 risk that becomes P0 incident in 47h.

Step 3 — Fix:
  Restore route53:ChangeResourceRecordSets to cert-manager-prod IAM role
  → Trigger fresh certificate renewal
  → Monitor cert-manager logs for success

Step 4 — Authorization:
  IAM permission changes require security team approval per policy.
  Auto-execution NOT appropriate.
  Pre-drafted minimal policy change ready for review.

CONCLUSION: Security audit removed Route53 permission.
ESCALATE: Page @security-team for emergency IAM approval.""",
        "expected_actions": [
            {"title": "Page security team for emergency IAM review",
             "description": "Alert @security-team via PagerDuty. 47h deadline. Include pre-drafted IAM change.",
             "command": "[PagerDuty API] POST /incidents {\"title\":\"Emergency IAM change — TLS cert 47h deadline\",\"urgency\":\"high\",\"service\":\"security-team\"}",
             "decision": "auto", "risk": "low", "confidence": 0.99},
            {"title": "Restore route53:ChangeResourceRecordSets to IAM",
             "description": "Minimal IAM change to restore auto-renewal. Requires security team approval.",
             "command": "aws iam put-role-policy --role-name cert-manager-prod --policy-name CertManagerRoute53 --policy-document file://route53-policy.json",
             "decision": "human", "risk": "medium", "confidence": 0.97},
            {"title": "Trigger manual cert renewal after IAM fix",
             "description": "Delete failed CertificateRequest and trigger fresh ACME challenge.",
             "command": "kubectl delete certificaterequest -l cert-manager.io/certificate-name=wildcard-company-com -n cert-manager && kubectl annotate certificate wildcard-company-com cert-manager.io/issue-temporary-certificate=true -n cert-manager",
             "decision": "human", "risk": "low", "confidence": 0.92},
        ],
        "before_after_metrics": [
            {"label": "Cert Expires",     "before": "47h",      "after": "89 days"},
            {"label": "Auto-Renewal",     "before": "FAILED",   "after": "SUCCESS"},
            {"label": "ACME Challenges",  "before": "3 FAILED", "after": "1 OK"},
            {"label": "Services TLS",     "before": "AT RISK",  "after": "SECURE"},
        ],
        "tuning": {
            "expected_winning_hypothesis": "IAM policy change removed Route53 permission",
            "irreversibility": "irreversible",
            "blast_radius_services": ["all-public-apis"],
            "data_gravity": {"pii": False, "phi": False, "pci": False},
            "expected_dec": "escalate",
        },
    },
}


def scenario_labels() -> list[tuple[str, str]]:
    """Return (id, label) pairs for UI dropdowns."""
    return [(s["id"], s["label"]) for s in SCENARIOS.values()]


def get_scenario(scenario_id: str) -> dict[str, Any]:
    if scenario_id not in SCENARIOS:
        raise KeyError(f"Unknown scenario: {scenario_id}")
    return SCENARIOS[scenario_id]
