# ZERMP Security Audit & Vulnerability Exception Ledger
**Entity:** Vridhi Financial Services Limited  
**Audit Date:** 2026-09-30  
**Tooling:** Bandit (SAST), pip-audit (CVE Analysis), Pytest Regression Suite

---

## 1. Vulnerability Scan Summary

| Phase | Vulnerability Count | Primary Root Causes | Status |
| :--- | :--- | :--- | :--- |
| **Initial Audit** | 37 Advisories (6 Packages) | `paramiko` B507, `python-jose`, `ecdsa`, `starlette`, `pytest`, `pip` | Remediated |
| **Intermediate** | 29 Advisories (4 Packages) | Upgraded `paramiko` to 3.5.0+, patched `pytest` | Remediated |
| **Final State** | 10 Advisories (1 Package) | `starlette` ASGI upstream multipart parser | Mitigated via Controls |

---

## 2. Risk Exception Register: Starlette 0.50.0

* **CVE IDs:** `PYSEC-2026-161`, `PYSEC-2026-248`, `PYSEC-2026-249`, `PYSEC-2026-2280`, `PYSEC-2026-2281`
* **Severity:** Medium
* **Component:** Upstream ASGI HTTP & Multipart Form Parser
* **Upstream Dependency:** Pinned by `fastapi>=0.115.0` (FastAPI core requires `starlette<1.0`)

### Compensating Controls & Production Defenses
1. **Zero Multipart Exposure:** ZERMP APIs do not accept `multipart/form-data`. All core risk operations (credit scoring, limit overrides, regulatory returns) strictly consume `application/json`.
2. **Reverse Proxy Buffering (Layer 7):** Production ingress via AWS ALB enforces strict request line limits (max 8 KB) and payload caps (max 10 MB), dropping malformed chunked transfer encoding before it reaches Uvicorn.
3. **Decoupled SFTP Batch Ingestion:** Large batch files are ingested out-of-band via SFTP (Port 22/2222) with memory-streamed decryption, bypassing the HTTP gateway entirely.
4. **Non-Root Container Isolation:** `zermp-api` executes under POSIX UID `1001` (`zermp:zermp`) with a read-only root filesystem and dropped capabilities.
