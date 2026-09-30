#!/usr/bin/env bash
set -euo pipefail

echo "[+] Initializing ZERMP Enterprise Repository Scaffolding..."

# Section D3 Directory Scaffolding
mkdir -p .github/workflows
mkdir -p .githooks
mkdir -p scripts
mkdir -p 01-requirements
mkdir -p 02-workflow-mapping/process-diagrams/current-state
mkdir -p 02-workflow-mapping/process-diagrams/future-state
mkdir -p 03-platform-config
mkdir -p 04-data-migration/field-mappings
mkdir -p 05-user-roles
mkdir -p 06-deployment-timeline
mkdir -p 07-risk-register
mkdir -p 08-training
mkdir -p 09-support-handoff
mkdir -p appendices
mkdir -p infra/docker
mkdir -p infra/helm/zermp/templates
mkdir -p infra/terraform
mkdir -p src/common/{config,logging,security,exceptions}
mkdir -p src/modules/{auth,credit_risk,market_risk,operational_risk,regulatory_reporting,workflow}
mkdir -p src/ingestion/{connectors,pipelines,profilers}
mkdir -p tests/{unit,integration}

# Initialize Git repository
if [ ! -d ".git" ]; then
    git init
    echo "[+] Initialized empty Git repository."
fi

# Write .gitignore
cat << 'GITIGNORE' > .gitignore
__pycache__/
*.py[cod]
*$py.class
*.so
.env
.env.local
venv/
.venv/
ENV/
*.log
*.sqlite3
.pytest_cache/
.coverage
htmlcov/
dist/
build/
*.egg-info/
.idea/
.vscode/
*.swp
data/
minio_data/
clickhouse_data/
postgres_data/
redis_data/
sftp_data/
GITIGNORE

# Write .dockerignore
cat << 'DOCKERIGNORE' > .dockerignore
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
.git
.gitignore
.dockerignore
.env
.env.*
README.md
docs/
01-requirements/
02-workflow-mapping/
05-user-roles/
06-deployment-timeline/
07-risk-register/
08-training/
09-support-handoff/
appendices/
tests/
DOCKERIGNORE

# Initialize ERROR_LOG.md with identified deliberate errors
cat << 'ERRLOG' > ERROR_LOG.md
# Deliberate Training Document Error Log

This document records deliberate errors identified in the Part A training material for bonus evaluation.

### Error 1: Provisioning Percentage for Sub-Standard Assets
- **Location:** Part A, Section A2.3 (NPA Classification Framework)
- **Documented Value:** 15% (Secured) / 25% (Unsecured)
- **Correction:** Under RBI IRAC norms for Systemically Important Non-Deposit Taking NBFCs (NBFC-ND-SI), standard provisioning for Sub-Standard assets is a uniform **10%** on total outstandings without distinction between secured/unsecured portions (the 15%/25% split applies to Scheduled Commercial Banks).

### Error 2: Exhaustive 1-to-1 Field Mapping Axiom
- **Location:** Part A, Section A3.3 (Data Migration Best Practices)
- **Documented Value:** "Field mapping documentation must be exhaustive every source field must map to exactly one target field"
- **Correction:** Enterprise ETL pipelines in financial platforms routinely mandate **Many-to-One** mappings (e.g., aggregating branch-level loan adjustments into a centralized provisioning ledger) and **One-to-Many** mappings (e.g., decomposing compound customer identity fields into structured sub-fields).

### Error 3: Absolute Sponsor Deference during Escalation
- **Location:** Part A, Section A4.2 (Conflict Resolution Framework)
- **Documented Value:** "The sponsor's decision must always be accepted without challenge"
- **Correction:** A Forward Deployed Engineer (FDE) must present objective risk data, regulatory implications, and alternative architectural compromises if an executive directive violates compliance mandates or creates critical technical debt.
ERRLOG

# Initialize Section E3 AI_USAGE_LOG.md
cat << 'AILOG' > AI_USAGE_LOG.md
# AI Usage Log

This document records all significant AI interactions throughout the project lifecycle in compliance with Section E3.

| Date | Tool Used | Purpose | Prompt Summary | How Output Was Used | Validation Step |
| :--- | :--- | :--- | :--- | :--- | :--- |
AILOG

echo "[+] Directory structure, core logs, and ignore files successfully established."
