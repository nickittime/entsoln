"""End-to-End Verification Suite for Module 3.

Tests authentication, MFA enforcement, RBAC authorization boundaries,
Segregation of Duties (SoD 4-eyes enforcement), credit limit override workflows,
and production REST API route responses.
"""

import asyncio
import sys
import httpx

BASE_URL = "http://localhost:8000"


async def run_tests() -> bool:
    print("\n" + "=" * 80)
    print(" ZERMP MODULE 3: SECURITY, RBAC, SOD & API GATEWAY VERIFICATION")
    print("=" * 80)
    all_passed = True

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Authentication & MFA Enforcement (CFG-UM-001)
        print("\n[1/5] Testing Authentication & Mandatory MFA Enforcement...")
        try:
            # Attempt login without MFA for CRO (Elevated Role) -> Expect Failure (401)
            res_no_mfa = await client.post(
                "/api/v1/auth/login",
                json={"username": "cro_ananya", "password": "Vridhi@Cro2026!"},
            )
            assert res_no_mfa.status_code == 401, f"Expected 401, got {res_no_mfa.status_code}: {res_no_mfa.text}"
            assert "MFA" in res_no_mfa.json().get("detail", ""), f"MFA not in response: {res_no_mfa.text}"

            # Login with valid MFA code (123456) -> Expect Success (200)
            res_cro = await client.post(
                "/api/v1/auth/login",
                json={"username": "cro_ananya", "password": "Vridhi@Cro2026!", "mfa_code": "123456"},
            )
            assert res_cro.status_code == 200, f"CRO login failed: {res_cro.text}"
            cro_token = res_cro.json()["access_token"]

            # Login Analyst (Standard Role, No MFA Required)
            res_analyst = await client.post(
                "/api/v1/auth/login",
                json={"username": "analyst_arun", "password": "Vridhi@Analyst2026!"},
            )
            assert res_analyst.status_code == 200, f"Analyst login failed: {res_analyst.text}"
            analyst_token = res_analyst.json()["access_token"]

            # Login Branch Credit Manager
            res_bcm = await client.post(
                "/api/v1/auth/login",
                json={"username": "branch_mgr_neha", "password": "Vridhi@Branch2026!"},
            )
            assert res_bcm.status_code == 200, f"BCM login failed: {res_bcm.text}"
            bcm_token = res_bcm.json()["access_token"]

            print("  [✓] Authentication: MFA gated on elevated roles; JWT issued successfully.")
        except Exception as exc:
            print(f"  [✗] Authentication Test Failed: {exc}")
            all_passed = False
            return False

        # 2. RBAC Route Guarding (Unauthorized Role Rejection)
        print("\n[2/5] Testing RBAC Route Authorization Boundaries...")
        try:
            # Analyst attempts to trigger RBI NBS-7 regulatory return generation -> Expect 403 Forbidden
            res_unauth = await client.post(
                "/api/v1/regulatory/generate-nbs7",
                headers={"Authorization": f"Bearer {analyst_token}"},
            )
            assert res_unauth.status_code == 403, f"Expected 403, got {res_unauth.status_code}: {res_unauth.text}"
            assert "Access denied" in res_unauth.json().get("detail", "")

            # CRO triggers RBI NBS-7 regulatory return generation -> Expect 200 OK
            res_auth = await client.post(
                "/api/v1/regulatory/generate-nbs7",
                headers={"Authorization": f"Bearer {cro_token}"},
            )
            assert res_auth.status_code == 200, f"Expected 200, got {res_auth.status_code}: {res_auth.text}"
            assert "report_summary" in res_auth.json()
            print("  [✓] RBAC Guarding: Unauthorized roles blocked (403); authorized roles admitted (200).")
        except Exception as exc:
            print(f"  [✗] RBAC Guarding Test Failed: {exc}")
            all_passed = False

        # 3. Segregation of Duties (SoD) & 4-Eyes Principle Enforcement
        print("\n[3/5] Testing Segregation of Duties (Anti-Self Approval)...")
        try:
            # Branch Manager submits an override request
            ovr_payload = {
                "account_id": "ACC_SOD_TEST_01",
                "exposure_amount": 25_000_000.0,  # 2.5 Crore
                "current_cibil_score": 625,
                "requested_limit": 30_000_000.0,
                "justification": "Strong seasonal cash flow from SME grain trade",
            }
            res_submit = await client.post(
                "/api/v1/credit/override/request",
                headers={"Authorization": f"Bearer {bcm_token}"},
                json=ovr_payload,
            )
            assert res_submit.status_code == 200, f"Submit override failed: {res_submit.text}"
            ovr_id = res_submit.json()["override_id"]

            # Branch Manager attempts to self-approve their own request -> Expect 403 Forbidden SoD Violation
            res_self = await client.post(
                f"/api/v1/credit/override/{ovr_id}/decide",
                headers={"Authorization": f"Bearer {bcm_token}"},
                json={"action": "APPROVE", "comments": "Self-approved override"},
            )
            assert res_self.status_code == 403, f"Expected 403 SoD violation, got {res_self.status_code}: {res_self.text}"
            assert "Segregation of Duties" in res_self.json().get("detail", "")

            # CRO (independent 4-eyes) approves the override -> Expect 200 OK
            res_cro_approve = await client.post(
                f"/api/v1/credit/override/{ovr_id}/decide",
                headers={"Authorization": f"Bearer {cro_token}"},
                json={"action": "APPROVE", "comments": "Independent 4-eyes review approved by CRO."},
            )
            assert res_cro_approve.status_code == 200, f"CRO approval failed: {res_cro_approve.text}"
            assert res_cro_approve.json()["status"] == "APPROVED"
            print("  [✓] Segregation of Duties: Self-approval rejected; independent 4-eyes approval executed.")
        except Exception as exc:
            print(f"  [✗] Segregation of Duties Test Failed: {exc}")
            all_passed = False

        # 4. Multi-Level Credit Escalation Ladder (> INR 5 Crore Threshold)
        print("\n[4/5] Testing Multi-Tier Escalation Ladder (> INR 5 Crore Threshold)...")
        try:
            # Submit large exposure override: INR 8 Crore
            large_ovr_payload = {
                "account_id": "ACC_LARGE_EXP_02",
                "exposure_amount": 80_000_000.0,  # 8 Crore
                "current_cibil_score": 640,
                "requested_limit": 100_000_000.0,
                "justification": "Institutional working capital for infrastructure contractor",
            }
            res_large = await client.post(
                "/api/v1/credit/override/request",
                headers={"Authorization": f"Bearer {analyst_token}"},
                json=large_ovr_payload,
            )
            assert res_large.status_code == 200, f"Submit large override failed: {res_large.text}"
            large_id = res_large.json()["override_id"]
            assert res_large.json()["status"] == "PENDING_HEAD_CREDIT"

            # Branch Manager attempts to approve > 5 Crore -> Expect 400 Bad Request
            res_bcm_deny = await client.post(
                f"/api/v1/credit/override/{large_id}/decide",
                headers={"Authorization": f"Bearer {bcm_token}"},
                json={"action": "APPROVE", "comments": "Branch mgr attempting approval"},
            )
            assert res_bcm_deny.status_code == 400, f"Expected 400 for escalation required, got {res_bcm_deny.status_code}"
            assert "exceeding INR 5 Crore" in res_bcm_deny.json().get("detail", "")

            # CRO approves large exposure override -> Expect 200 OK
            res_cro_approve = await client.post(
                f"/api/v1/credit/override/{large_id}/decide",
                headers={"Authorization": f"Bearer {cro_token}"},
                json={"action": "APPROVE", "comments": "Approved post-Board credit committee review."},
            )
            assert res_cro_approve.status_code == 200, f"CRO approval failed: {res_cro_approve.text}"
            assert res_cro_approve.json()["status"] == "APPROVED"
            print("  [✓] Escalation Ladder: > 5 Crore exposures enforced escalation to CRO/Head of Credit.")
        except Exception as exc:
            print(f"  [✗] Escalation Ladder Test Failed: {exc}")
            all_passed = False

        # 5. Core Credit Assessment REST API
        print("\n[5/5] Testing Live Credit Risk Assessment API Route...")
        try:
            loan_payload = {
                "account_id": "ACC_LIVE_API_01",
                "customer_id": "CUST_API_01",
                "customer_name": "Apex Manufacturing Ltd",
                "product_type": "SME_LENDING",
                "sanctioned_amount": 15_000_000.0,
                "outstanding_principal": 12_000_000.0,
                "current_dpd": 45,
                "secured_percentage": 0.8,
                "cibil_score": 710,
                "annual_income": 30_000_000.0,
                "monthly_emi": 150_000.0,
            }
            res_eval = await client.post(
                "/api/v1/credit/assess",
                headers={"Authorization": f"Bearer {analyst_token}"},
                json=loan_payload,
            )
            assert res_eval.status_code == 200, f"Credit assess failed: {res_eval.text}"
            data = res_eval.json()
            assert data["asset_classification"] == "SMA_1"
            assert data["is_npa"] is False
            assert data["required_provision_amount"] == 48_000.0  # 12M * 0.40%
            print(f"  [✓] Credit Assessment Route: Returned {data['asset_classification']} with INR {data['required_provision_amount']:,.2f} provisioning.")
        except Exception as exc:
            print(f"  [✗] Credit Assessment Route Failed: {exc}")
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print(" RESULT: ALL 5 MODULE 3 SECURITY & API SPECIFICATIONS OPERATIONAL [PASS]")
        print("=" * 80 + "\n")
        return True
    else:
        print(" RESULT: ONE OR MORE MODULE 3 COMPONENTS FAILED VERIFICATION [FAIL]")
        print("=" * 80 + "\n")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
