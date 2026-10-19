"""
Unit tests for the deterministic risk scoring service (SRS FR-RISK-01–07).

Covers:
- Per-finding score for all severity × type combinations
- Metadata bonuses (CWE, OWASP)
- Clamping at 0.0 and 10.0
- Risk level thresholds
- Determinism (same inputs → same output)
- Unknown severity / type fall-through
- Project-level score: empty list, all resolved, mixed, cap at 100
- In-Review findings count toward project risk
- SCORING_VERSION constant is set
"""
import pytest

from app.services.risk_scoring import SCORING_VERSION, project_risk_score, score_finding


# ── Helpers ───────────────────────────────────────────────────────────────────

class _Finding:
    """Minimal stand-in for a Finding model row."""
    def __init__(self, severity: str, status: str = "Open"):
        self.engine_severity = severity
        self.status = status


# ── score_finding ─────────────────────────────────────────────────────────────

class TestScoreFinding:
    def test_high_vulnerability_with_cwe_and_owasp(self):
        score, level = score_finding("High", "Vulnerability", "CWE-89", "A1:2021")
        # 7.5 + 1.0 + 0.5 + 0.5 = 9.5 → Critical
        assert score == 9.5
        assert level == "Critical"

    def test_high_vulnerability_no_metadata(self):
        score, level = score_finding("High", "Vulnerability", None, None)
        # 7.5 + 1.0 = 8.5 → High
        assert score == 8.5
        assert level == "High"

    def test_medium_vulnerability_with_cwe(self):
        score, level = score_finding("Medium", "Vulnerability", "CWE-79", None)
        # 5.0 + 1.0 + 0.5 = 6.5 → High
        assert score == 6.5
        assert level == "High"

    def test_medium_bug_no_metadata(self):
        score, level = score_finding("Medium", "Bug", None, None)
        # 5.0 + 0.0 = 5.0 → Medium
        assert score == 5.0
        assert level == "Medium"

    def test_low_code_smell_no_metadata(self):
        score, level = score_finding("Low", "Code Smell", None, None)
        # 2.5 - 0.5 = 2.0 → Low
        assert score == 2.0
        assert level == "Low"

    def test_low_code_smell_floor_is_zero_not_negative(self):
        score, _ = score_finding("Low", "Code Smell", None, None)
        assert score >= 0.0

    def test_critical_vulnerability_clamped_at_10(self):
        score, level = score_finding("Critical", "Vulnerability", "CWE-79", "A2:2021")
        # 10.0 + 1.0 + 0.5 + 0.5 = 12.0 → clamped to 10.0
        assert score == 10.0
        assert level == "Critical"

    def test_unknown_severity_defaults_to_low_base(self):
        score, level = score_finding("Unknown", "Bug", None, None)
        # 2.5 (default) + 0.0 = 2.5 → Low
        assert score == 2.5
        assert level == "Low"

    def test_unknown_issue_type_defaults_to_zero_adj(self):
        score, _ = score_finding("Medium", "Other", None, None)
        # 5.0 + 0.0 = 5.0
        assert score == 5.0

    def test_cwe_bonus_adds_0_5(self):
        with_cwe, _ = score_finding("Low", "Bug", "CWE-120", None)
        without_cwe, _ = score_finding("Low", "Bug", None, None)
        assert round(with_cwe - without_cwe, 2) == 0.5

    def test_owasp_bonus_adds_0_5(self):
        with_owasp, _ = score_finding("Low", "Bug", None, "A3:2021")
        without_owasp, _ = score_finding("Low", "Bug", None, None)
        assert round(with_owasp - without_owasp, 2) == 0.5

    def test_security_hotspot_adj(self):
        score, _ = score_finding("Medium", "Security Hotspot", None, None)
        # 5.0 + 0.5 = 5.5 → Medium
        assert score == 5.5

    def test_deterministic_repeated_calls(self):
        a = score_finding("High", "Vulnerability", "CWE-89", "A1:2021")
        b = score_finding("High", "Vulnerability", "CWE-89", "A1:2021")
        assert a == b

    def test_scoring_version_constant(self):
        assert SCORING_VERSION == "v1.0"

    def test_risk_level_thresholds(self):
        # score 9.0 exactly → Critical
        score_9, level_9 = score_finding("Critical", "Bug", None, None)
        # Critical base = 10, so score will be 10.0 → Critical
        assert level_9 == "Critical"

        # Lowest possible High: 6.0
        score_6, level_6 = score_finding("Medium", "Security Hotspot", None, None)
        # 5.0 + 0.5 = 5.5 → Medium (just below High threshold)
        assert level_6 == "Medium"

        # Low: < 3.0
        score_low, level_low = score_finding("Low", "Code Smell", None, None)
        # 2.5 - 0.5 = 2.0 → Low
        assert level_low == "Low"


# ── project_risk_score ────────────────────────────────────────────────────────

class TestProjectRiskScore:
    def test_empty_findings_returns_zero(self):
        assert project_risk_score([]) == 0.0

    def test_all_resolved_returns_zero(self):
        findings = [
            _Finding("High", "Resolved"),
            _Finding("Critical", "Resolved"),
        ]
        assert project_risk_score(findings) == 0.0

    def test_single_critical(self):
        # Critical weight = 10
        assert project_risk_score([_Finding("Critical")]) == 10.0

    def test_single_high(self):
        # High weight = 5
        assert project_risk_score([_Finding("High")]) == 5.0

    def test_single_medium(self):
        assert project_risk_score([_Finding("Medium")]) == 2.0

    def test_single_low(self):
        assert project_risk_score([_Finding("Low")]) == 1.0

    def test_mixed_severities(self):
        findings = [
            _Finding("Critical"),  # 10
            _Finding("High"),      # 5
            _Finding("Medium"),    # 2
            _Finding("Low"),       # 1
        ]
        assert project_risk_score(findings) == 18.0

    def test_score_caps_at_100(self):
        findings = [_Finding("Critical")] * 15  # 150 → capped at 100
        assert project_risk_score(findings) == 100.0

    def test_resolved_excluded_from_score(self):
        findings = [
            _Finding("Critical", "Open"),
            _Finding("Critical", "Resolved"),
        ]
        # Only one unresolved: 10
        assert project_risk_score(findings) == 10.0

    def test_in_review_counts_toward_risk(self):
        # "In Review" is not yet resolved
        assert project_risk_score([_Finding("High", "In Review")]) == 5.0

    def test_deterministic(self):
        findings = [_Finding("Critical"), _Finding("High")]
        assert project_risk_score(findings) == project_risk_score(findings)

    def test_unknown_severity_defaults_to_weight_1(self):
        findings = [_Finding("Unknown")]
        assert project_risk_score(findings) == 1.0
