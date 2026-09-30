"""Prometheus Telemetry and Operational Metrics for ZERMP.

Instruments application runtime performance, regulatory calculation throughput,
and infrastructure health indicators.
"""

from prometheus_client import Counter, Gauge, Histogram

# HTTP Traffic & Latency Metrics
REQUEST_COUNT = Counter(
    "zermp_http_requests_total",
    "Total HTTP requests handled by the platform",
    ["method", "endpoint", "http_status"],
)

REQUEST_LATENCY = Histogram(
    "zermp_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# Domain Risk Engine Metrics
CREDIT_ASSESSMENTS_TOTAL = Counter(
    "zermp_credit_assessments_total",
    "Cumulative loan accounts assessed by Credit Risk Engine",
    ["product_type", "asset_classification", "is_npa"],
)

NPA_PROVISIONS_INR_TOTAL = Counter(
    "zermp_npa_provisions_inr_total",
    "Cumulative regulatory provision amount calculated in INR",
    ["asset_classification"],
)

ACTIVE_SYSTEM_ALERTS = Gauge(
    "zermp_active_system_alerts",
    "Current count of active KRI or infrastructure alerts",
    ["severity"],
)
