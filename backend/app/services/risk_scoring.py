"""
Deterministic risk scoring service — Explicite AI v1.0.

Implements SRS FR-RISK-01 through FR-RISK-07:
  - Score is separate from engine severity (FR-RISK-01, FR-AN-03).
  - Considers severity, evidence quality (CWE/OWASP), and issue type (FR-RISK-02).
  - Rules are deterministic and versioned (FR-RISK-03).
  - Model version is recorded per finding (FR-RISK-07).
  - Uncertainty is handled by a safe default; no double-counting across factors (FR-RISK-05).

Formula status: PROVISIONAL BASELINE (SRS note: "exact formula and calibration pending
evaluation"). This implementation uses transparent, independently auditable arithmetic.
"""

SCORING_VERSION = "v1.0"

_SEVERITY_BASE: dict[str, float] = {
    "Critical": 10.0,
    "High": 7.5,
    "Medium": 5.0,
    "Low": 2.5,
}

_TYPE_ADJ: dict[str, float] = {
    "Vulnerability": 1.0,
    "Security Hotspot": 0.5,
    "Bug": 0.0,
    "Code Smell": -0.5,
}

_PROJECT_SEVERITY_WEIGHTS: dict[str, int] = {
    "Critical": 10,
    "High": 5,
    "Medium": 2,
    "Low": 1,
}


def score_finding(
    engine_severity: str,
    issue_type: str,
    cwe_id: str | None,
    owasp_category: str | None,
) -> tuple[float, str]:
    """
    Per-finding risk score (0.0–10.0) and derived risk level.

    Formula v1.0 (all inputs are independent; no factor counted twice):
      base    = severity_base[engine_severity]    (default 2.5 if unknown)
      adj     = type_adj[issue_type]              (default 0.0 if unknown)
      cwe     = 0.5 if cwe_id present else 0.0
      owasp   = 0.5 if owasp_category present else 0.0
      score   = clamp(base + adj + cwe + owasp, 0.0, 10.0)

    Risk levels derived from score:
      >= 9.0  → Critical
      >= 6.0  → High
      >= 3.0  → Medium
      <  3.0  → Low
    """
    base = _SEVERITY_BASE.get(engine_severity, 2.5)
    adj = _TYPE_ADJ.get(issue_type, 0.0)
    cwe_bonus = 0.5 if cwe_id else 0.0
    owasp_bonus = 0.5 if owasp_category else 0.0

    raw = base + adj + cwe_bonus + owasp_bonus
    risk_score = round(min(max(raw, 0.0), 10.0), 2)

    if risk_score >= 9.0:
        risk_level = "Critical"
    elif risk_score >= 6.0:
        risk_level = "High"
    elif risk_score >= 3.0:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    return risk_score, risk_level


def project_risk_score(findings: list) -> float:
    """
    Project risk score (0.0–100.0).

    Aggregates per-severity weights over all unresolved findings
    (status != 'Resolved').  Resolved issues do not contribute to
    current risk.  Capped at 100.0.

    Returns 0.0 when the list is empty or all findings are resolved.
    """
    unresolved = [f for f in findings if f.status != "Resolved"]
    raw = sum(_PROJECT_SEVERITY_WEIGHTS.get(f.engine_severity, 1) for f in unresolved)
    return round(min(100.0, float(raw)), 1)
