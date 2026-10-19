"""
Tests for CVSS v3.1 scoring — accuracy, invalid vectors, version detection.
"""
import pytest
from app.services.cvss_scoring import score_cvss_vector, extract_cvss_from_metadata, _roundup


# ── Roundup ───────────────────────────────────────────────────────────────────

def test_roundup_exact_tenths():
    assert _roundup(4.0) == 4.0
    assert _roundup(7.0) == 7.0

def test_roundup_rounds_up():
    assert _roundup(4.02) == 4.1
    assert _roundup(6.91) == 7.0

def test_roundup_does_not_round_down():
    assert _roundup(3.99) == 4.0


# ── Known CVSS v3.1 vectors from FIRST spec examples ──────────────────────────

@pytest.mark.parametrize("vector,expected_score,expected_severity", [
    # FIRST specification worked examples
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 9.8, "Critical"),
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H", 10.0, "Critical"),
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H", 8.8, "High"),
    ("CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H", 5.5, "Medium"),
    ("CVSS:3.1/AV:P/AC:H/PR:H/UI:R/S:U/C:N/I:N/A:L", 1.6, "Low"),
    # Zero impact → score 0
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N", 0.0, "None"),
    # Scope-changed, lower exploitability due to PR:L
    ("CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H", 9.1, "Critical"),
])
def test_known_cvss31_scores(vector, expected_score, expected_severity):
    result = score_cvss_vector(vector)
    assert result.score == pytest.approx(expected_score, abs=0.05), f"Score for {vector}: got {result.score}"
    assert result.version == "3.1"
    assert result.severity == expected_severity
    assert result.error is None


# ── v3.0 treated as v3.1 ──────────────────────────────────────────────────────

def test_v30_vector_scored_and_preserves_version():
    result = score_cvss_vector("CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
    assert result.score == pytest.approx(9.8, abs=0.05)
    assert result.version == "3.0"   # detected version preserved, formula same as v3.1


# ── v4.0 detected but not scored ─────────────────────────────────────────────

def test_v40_vector_not_scored():
    result = score_cvss_vector("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N")
    assert result.score is None
    assert result.version == "4.0"
    assert result.severity is None
    assert result.error is None   # not an error; just unsupported scoring


# ── v2.0 rejected ────────────────────────────────────────────────────────────

def test_v20_vector_rejected():
    result = score_cvss_vector("CVSS:2.0/AV:N/AC:L/Au:N/C:C/I:C/A:C")
    assert result.score is None
    assert result.version == "2.0"
    assert result.error is not None


# ── Invalid inputs ────────────────────────────────────────────────────────────

def test_none_input():
    result = score_cvss_vector(None)
    assert result.score is None
    assert result.version is None
    assert result.error is None


def test_empty_string():
    result = score_cvss_vector("")
    assert result.score is None


def test_unrecognised_prefix():
    result = score_cvss_vector("CVSS:99.9/AV:N/AC:L")
    assert result.score is None
    assert result.error is not None


def test_missing_metric():
    # Missing AV
    result = score_cvss_vector("CVSS:3.1/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
    assert result.score is None
    assert result.error is not None
    assert "AV" in result.error


def test_invalid_metric_value():
    result = score_cvss_vector("CVSS:3.1/AV:X/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
    assert result.score is None
    assert result.error is not None


def test_malformed_vector_no_colon():
    result = score_cvss_vector("CVSS:3.1/AVLACL")
    assert result.score is None
    assert result.error is not None


# ── extract_cvss_from_metadata ────────────────────────────────────────────────

def test_extract_string_vector():
    meta = {"cvss": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}
    v, ver = extract_cvss_from_metadata(meta)
    assert v == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    assert ver == "3.1"


def test_extract_list_vector():
    meta = {"cvss": ["CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"]}
    v, ver = extract_cvss_from_metadata(meta)
    assert v is not None
    assert ver == "3.1"


def test_extract_dict_vector():
    meta = {"cvss": {"vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}}
    v, ver = extract_cvss_from_metadata(meta)
    assert v is not None


def test_extract_missing_key():
    v, ver = extract_cvss_from_metadata({})
    assert v is None
    assert ver is None


def test_extract_empty_string():
    v, ver = extract_cvss_from_metadata({"cvss": ""})
    assert v is None
