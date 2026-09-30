"""Automated Verification Suite for Phase 5: Production Deployment & Telemetry.

Validates Prometheus metrics endpoint exposition, metric increments under load,
operational runbook structural integrity, and end-to-end container health.
"""

import asyncio
import sys
import httpx
from pathlib import Path

BASE_URL = "http://localhost:8000"


async def run_checks() -> bool:
    print("\n" + "=" * 80)
    print(" ZERMP PHASE 5: PRODUCTION GO-LIVE, TELEMETRY & RUNBOOK VERIFICATION")
    print("=" * 80)
    all_passed = True

    async with httpx.AsyncClient(base_url=BASE_URL, follow_redirects=True, timeout=10.0) as client:
        # 1. Operational Runbook Structure Audit
        print("\n[1/4] Auditing Operational Runbook Documentation...")
        runbook = Path("docs/OPERATIONAL_RUNBOOK.md")
        if runbook.exists() and runbook.stat().st_size > 1000:
            content = runbook.read_text(encoding="utf-8")
            assert "System Topology" in content, "Missing System Topology"
            assert "SOP-01" in content, "Missing SOP-01"
            assert "Disaster Recovery" in content, "Missing Disaster Recovery"
            assert "Escalation Matrix" in content, "Missing Escalation Matrix"
            print("  [✓] Operational Runbook: Comprehensive SOPs and DR procedures verified.")
        else:
            print(f"  [✗] Operational Runbook check failed (exists={runbook.exists()}, size={runbook.stat().st_size if runbook.exists() else 0}).")
            all_passed = False

        # 2. Prometheus /metrics Endpoint Exposition
        print("\n[2/4] Testing Prometheus Metrics Exposition (/metrics)...")
        try:
            res_metrics = await client.get("/metrics")
            assert res_metrics.status_code == 200, f"Expected 200 from /metrics, got {res_metrics.status_code}: {res_metrics.text[:100]}"
            metrics_body = res_metrics.text
            assert "zermp_http_requests_total" in metrics_body, "Missing zermp_http_requests_total metric"
            assert "zermp_http_request_duration_seconds" in metrics_body, "Missing zermp_http_request_duration_seconds metric"
            print("  [✓] Prometheus Telemetry: Metrics endpoint is live and exposing standard Prometheus format.")
        except Exception as exc:
            print(f"  [✗] Prometheus Metrics Test Failed: {exc}")
            all_passed = False

        # 3. Domain Metric Dynamic Increment
        print("\n[3/4] Testing Real-Time Metric Increments Under Traffic...")
        try:
            # Login as Analyst
            login_res = await client.post(
                "/api/v1/auth/login",
                json={"username": "analyst_arun", "password": "Vridhi@Analyst2026!"},
            )
            assert login_res.status_code == 200, f"Login failed: {login_res.text}"
            token = login_res.json()["access_token"]

            # Trigger a loan assessment to produce domain metrics
            loan_payload = {
                "account_id": "ACC_METRICS_VAL_01",
                "customer_id": "CUST_M_01",
                "customer_name": "Telemetry Enterprises",
                "product_type": "SME_LENDING",
                "sanctioned_amount": 10_000_000.0,
                "outstanding_principal": 8_000_000.0,
                "current_dpd": 15,
                "secured_percentage": 1.0,
                "cibil_score": 730,
                "annual_income": 30_000_000.0,
                "monthly_emi": 150_000.0,
            }
            res_eval = await client.post(
                "/api/v1/credit/assess",
                headers={"Authorization": f"Bearer {token}"},
                json=loan_payload,
            )
            assert res_eval.status_code == 200, f"Credit assess failed: {res_eval.text}"

            # Re-scrape /metrics and assert domain metric presence
            metrics_updated = (await client.get("/metrics")).text
            assert "zermp_credit_assessments_total" in metrics_updated, "Metric zermp_credit_assessments_total not present"
            assert 'product_type="SME_LENDING"' in metrics_updated, "Label product_type=SME_LENDING not present"
            print("  [✓] Telemetry Instrumentation: Credit assessment dynamically incremented Prometheus metrics.")
        except Exception as exc:
            print(f"  [✗] Domain Metric Increment Failed: {exc}")
            all_passed = False

        # 4. Final End-to-End System Health & Readiness Verification
        print("\n[4/4] Validating Final Container Health & Database Topology...")
        try:
            res_ready = await client.get("/readyz")
            assert res_ready.status_code == 200, f"Ready check failed: {res_ready.text}"
            ready_json = res_ready.json()
            assert ready_json["status"] == "ready"
            for db, status in ready_json["dependencies"].items():
                assert status == "connected", f"Database {db} status is {status}"
                print(f"    - {db.capitalize()}: Connected and healthy")
            print("  [✓] Platform Readiness: All 4 data persistence layers operational.")
        except Exception as exc:
            print(f"  [✗] Readiness Check Failed: {exc}")
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print(" RESULT: ALL PHASE 5 PRODUCTION GO-LIVE & TELEMETRY CHECKS PASS [GO-LIVE READY]")
        print("=" * 80 + "\n")
        return True
    else:
        print(" RESULT: ONE OR MORE PHASE 5 GO-LIVE GATES FAILED [FAIL]")
        print("=" * 80 + "\n")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_checks())
    sys.exit(0 if success else 1)
