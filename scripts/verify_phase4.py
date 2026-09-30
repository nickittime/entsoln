"""Automated Quality Gate & CI Pipeline Verification Script for Phase 4.

Validates test suites, CI workflow structure, configuration parameters,
and executes regression tests.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_checks() -> bool:
    print("\n" + "=" * 80)
    print(" ZERMP PHASE 4: CI/CD PIPELINE & AUTOMATED QUALITY GATE VERIFICATION")
    print("=" * 80)
    all_passed = True

    # 1. CI Workflow Specification Check
    print("\n[1/4] Verifying GitHub Actions CI Workflow Definition...")
    ci_path = Path(".github/workflows/ci.yml")
    if ci_path.exists() and ci_path.stat().st_size > 500:
        content = ci_path.read_text(encoding="utf-8")
        assert "code-quality-and-lint" in content
        assert "security-sast-audit" in content
        assert "unit-and-integration-tests" in content
        assert "docker-build-verification" in content
        print("  [✓] CI Workflow: Multi-stage pipeline verified (.github/workflows/ci.yml).")
    else:
        print("  [✗] CI Workflow file missing or invalid.")
        all_passed = False

    # 2. Pytest Configuration & Test Suite Layout Check
    print("\n[2/4] Verifying Test Suite Artifacts & Pytest Configuration...")
    try:
        assert Path("pytest.ini").exists()
        assert Path("pyproject.toml").exists()
        test_files = list(Path("tests").glob("test_*.py"))
        assert len(test_files) >= 4, f"Found only {len(test_files)} test files"
        for tf in test_files:
            print(f"  [✓] Verified test module: {tf.name}")
    except Exception as exc:
        print(f"  [✗] Test suite check failed: {exc}")
        all_passed = False

    # 3. Execute Pytest Suite Inside Container
    print("\n[3/4] Running Pytest Suite via Container Quality Gate...")
    try:
        res = subprocess.run(
            ["docker", "exec", "zermp-api", "pytest", "tests/", "-v", "--tb=short"],
            capture_output=True,
            text=True,
        )
        print(res.stdout)
        if res.returncode != 0:
            print(res.stderr)
            raise RuntimeError(f"Pytest exited with status code {res.returncode}")
        print("  [✓] Pytest Suite: All unit and domain tests executed and passed.")
    except Exception as exc:
        print(f"  [✗] Pytest execution failed: {exc}")
        all_passed = False

    # 4. End-to-End Regression Check (Modules 1, 2, 3)
    print("\n[4/4] Executing Platform Regression Gate (Modules 1-3)...")
    try:
        for script in ["scripts/verify_module1.py", "scripts/verify_module2.py", "scripts/verify_module3.py"]:
            cmd = ["docker", "exec", "zermp-api", "python", script]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                print(r.stdout)
                print(r.stderr)
                raise RuntimeError(f"Gate check failed for {script}")
            print(f"  [✓] Regression Pass: {script}")
        print("  [✓] Platform Regression Gate: Complete end-to-end verification passed.")
    except Exception as exc:
        print(f"  [✗] Regression Gate failed: {exc}")
        all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print(" RESULT: ALL PHASE 4 QUALITY GATES & CI PIPELINES VERIFIED [PASS]")
        print("=" * 80 + "\n")
        return True
    else:
        print(" RESULT: ONE OR MORE QUALITY GATES FAILED [FAIL]")
        print("=" * 80 + "\n")
        return False


if __name__ == "__main__":
    success = run_checks()
    sys.exit(0 if success else 1)
