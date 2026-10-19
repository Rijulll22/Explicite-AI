# Explicite AI Risk Scoring — Formula v1.0

**Status:** Provisional baseline — SRS note: "The exact formula, weights, thresholds and
calibration method remain subject to evaluation."  
**Model version:** `v1.0`  
**Implemented in:** `app/services/risk_scoring.py`

---

## Overview

Explicite AI calculates two risk scores that are **distinct from the engine severity**
(SRS FR-RISK-01, FR-AN-03):

| Score | Range | Stored on |
|---|---|---|
| Per-finding risk score | 0.0 – 10.0 | `findings.risk_score` |
| Project risk score | 0.0 – 100.0 | Computed at dashboard request time |

The model version is recorded on every finding (`findings.risk_score_version`) and on
every analysis job (`analysis_jobs.scoring_model_version`) so a reviewer can trace why
a score was assigned (SRS FR-RISK-07).

---

## Per-Finding Score (0.0 – 10.0)

### Formula

```
score = clamp(base + type_adj + cwe_bonus + owasp_bonus, 0.0, 10.0)
```

All four inputs are **independent** — no factor is counted twice (SRS FR-RISK-05).

### Inputs

| Input | Value |
|---|---|
| `base` (engine severity) | Critical = 10.0, High = 7.5, Medium = 5.0, Low = 2.5, Unknown = 2.5 |
| `type_adj` (issue type) | Vulnerability = +1.0, Security Hotspot = +0.5, Bug = 0.0, Code Smell = −0.5, Other = 0.0 |
| `cwe_bonus` | +0.5 if a CWE identifier is present, else 0.0 |
| `owasp_bonus` | +0.5 if an OWASP category is present, else 0.0 |

### Risk Level Thresholds

| Score range | Risk Level |
|---|---|
| ≥ 9.0 | Critical |
| ≥ 6.0 | High |
| ≥ 3.0 | Medium |
| < 3.0 | Low |

### Example

A High-severity SQL injection finding with CWE-89 and OWASP A03:2021 scores:
`7.5 (High base) + 1.0 (Vulnerability) + 0.5 (CWE) + 0.5 (OWASP) = 9.5` → **Critical**

---

## Project Risk Score (0.0 – 100.0)

Aggregates **unresolved findings** (status ≠ `Resolved`) from the latest completed
analysis job.  Resolved issues do not contribute to the current risk score.

```
raw = Σ weight[engine_severity]  for each unresolved finding
score = min(raw, 100.0)
```

| Severity | Weight |
|---|---|
| Critical | 10 |
| High | 5 |
| Medium | 2 |
| Low | 1 |
| Unknown | 1 |

**Interpretation:**

| Score | Label |
|---|---|
| 0 – 24.9 | Low Risk |
| 25 – 49.9 | Moderate Risk |
| 50 – 74.9 | High Risk |
| 75 – 100 | Critical Risk |

Returns `null` when no analysis has been run; returns `0.0` when all findings are
resolved or when the analysis produced no findings.

---

## Quality Gate (v1.0)

Implemented in `app/services/quality_gate.py`.

| Condition | Default threshold |
|---|---|
| Vulnerabilities (any severity) | 0 |
| Bugs | 0 |
| Coverage | Not enforced by default (opt-in via `enforce_coverage=True`) |

The gate **passes** only when all conditions are met.  
The stored `analysis_jobs.quality_gate_passed` is set at analysis time and must not
be mutated after write (it reflects the analysis-time result, not the current finding
status).

---

## Limitations

1. **Semgrep severities are limited to High / Medium / Low.** The Critical level exists
   in the schema for future engine support or manually-seeded findings, but Semgrep
   currently emits only ERROR → High, WARNING → Medium, INFO → Low.

2. **Project risk score is unbounded before clamping.** The linear sum means a project
   with 11+ Critical findings scores 100 regardless of whether it has 11 or 1 100.  A
   logarithmic or percentile-based normalisation is a recommended future improvement.

3. **Confidence and exploitability are not yet weighted.** SRS FR-RISK-02 mentions
   these factors; they require labelled training data or additional engine signals not
   yet available.

4. **Formula calibration is pending.** The SRS classifies the formula as "pending
   technical evaluation".  The weights and thresholds above are a transparent starting
   point, not a calibrated model.  Evaluation against labelled examples (SRS FR-RISK-06)
   is planned for a future batch.

5. **Coverage gate is not enforced by default.** Semgrep does not produce coverage data;
   the coverage fields in the schema are reserved for future engine integration.

---

## How Analysis History Is Selected

Both the dashboard (`GET /projects/{id}/dashboard`) and the issues list
(`GET /projects/{id}/issues`) use the **latest completed** analysis job — ordered by
`completed_at DESC` with `status = 'completed'`.  An in-progress or failed newer job
does not replace data from the most recent successful one.
