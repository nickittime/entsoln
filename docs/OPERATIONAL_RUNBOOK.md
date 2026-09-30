# ZERMP Enterprise Operational Runbook
**Entity:** Vridhi Financial Services Limited  
**System:** Zetheta Enterprise Risk Management Platform (ZERMP)  
**Classification:** NBFC-ND-SI Regulatory & Infrastructure Tier  
**Target Environment:** AWS Mumbai (`ap-south-1`) & Primary Datacenter (BKC, Mumbai)

---

## 1. System Topology & Port Allocations

| Service | Internal Host / Port | External Mapping | Purpose |
| :--- | :--- | :--- | :--- |
| `zermp-api` | `api:8000` | `8000:8000` | FastAPI Core Application & Metrics (`/metrics`) |
| `zermp-postgres` | `postgres:5432` | `5432:5432` | OLTP System of Record (Audit trail, Users, Overrides) |
| `zermp-clickhouse`| `clickhouse:8123` | `8123:8123` | High-Throughput Columnar OLAP for 2.3M Accounts |
| `zermp-redis` | `redis:6379` | `6379:6379` | Session State, Token Bucket & Distributed Mutex |
| `zermp-s3` | `s3:4566` | `4566:4566` | WORM Immutable Regulatory Archive (7-Year Hold) |
| `zermp-sftp-mock` | `sftp:22` | `2222:22` | FinnOne Core Banking Daily Batch Drop (DS-01) |

---

## 2. Standard Operating Procedures (SOPs)

### SOP-01: Daily FinnOne Core Banking Batch Ingestion (DS-01)
* **Schedule:** Twice daily at 06:00 IST and 18:00 IST.
* **Mechanism:** SFTP poller retrieves encrypted extracts from `/upload`, streams records into memory, evaluates credit risk scorecards, and loads analytical rows to ClickHouse `zermp_analytics.loan_portfolio`.
* **Failure Remediation:**
  1. Inspect SFTP connection: `docker exec zermp-api python -c "from src.ingestion.connectors.sftp_connector import sftp_connector; print(sftp_connector.list_pending_files())"`
  2. Check permissions on staging volume: Ensure `/home/finnone_etl/upload` has ownership `1001:1001` and mode `775`.
  3. Reprocess manually: `docker exec zermp-api python -c "from src.ingestion.pipelines.finnone_pipeline import finnone_pipeline; finnone_pipeline.process_and_load('<FILENAME>')"`

### SOP-02: Quarterly RBI Regulatory Reporting (NBS-7 & CRILC)
* **Schedule:** Quarterly by T+15 business days.
* **Execution:**
  1. Login as `cro_ananya` with MFA verification to generate JWT bearer token.
  2. Trigger generation: `POST /api/v1/regulatory/generate-nbs7?quarter=Q4-2026`.
  3. Confirm immutable object upload in S3: Check bucket `zermp-regulatory-reports` with metadata `immutable_retention_years=7`.
  4. Verify SHA-256 cryptographic digest against output logs.

---

## 3. Disaster Recovery & Failover Plan (DC BKC to AWS `ap-south-1`)

* **RTO (Recovery Time Objective):** $\le 30$ minutes.
* **RPO (Recovery Point Objective):** $\le 5$ minutes (continuous WAL shipping).
* **Failover Procedure:**
  1. **DNS Cutover:** Route53 updates public endpoint CNAME from `dc-ingress.vridhifin.com` to `aws-alb.vridhifin.com`.
  2. **Database Promotion:** Promote PostgreSQL standby replica in `ap-south-1` to primary read-write node.
  3. **ClickHouse Re-sync:** Trigger S3 backup restoration to secondary ClickHouse cluster via `BACKUP / RESTORE` tables.
  4. **Health Verification:** Execute `curl -i http://localhost:8000/readyz` to confirm all 4 database layers report `connected`.

---

## 4. Incident Response & Escalation Matrix

| Priority | Definition | Initial Response SLA | Escalation Target |
| :--- | :--- | :--- | :--- |
| **P1 - Critical** | Platform API unavailable, database outage, or failed RBI submission deadline | $< 15$ mins | CRO, CTO & Head of Infrastructure |
| **P2 - Major** | Ingestion pipeline delayed $> 2$ hours, ClickHouse latency $> 5$s | $< 30$ mins | Head of Credit Risk & Data Platform Lead |
| **P3 - Moderate** | Single KRI in Amber status, minor report format warning | $< 4$ hours | Branch Operations & Compliance Officers |
| **P4 - Minor** | UI layout discrepancy, non-blocking telemetry alert | $< 24$ hours | Development Operations Team |

---

## 5. Security & Secret Rotation Procedures

* **JWT Secret (`SECRET_KEY`):** Rotated every 90 days. Update `.env` and restart containers with zero downtime via blue-green deployment.
* **Database Passwords:** Rotated via AWS Secrets Manager with automatic connection pool re-authentication.
* **Segregation of Duties (SoD) Audit:** All self-approval attempts are logged under `SOD_VIOLATION` in JSON format with correlation IDs. Monthly audit exports delivered to `auditor_suresh` (External Auditor).
