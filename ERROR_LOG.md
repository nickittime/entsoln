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
