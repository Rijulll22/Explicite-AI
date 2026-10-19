"""Unit tests for app/services/fix_service.py and ai_service fix helpers."""
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from app.services.ai_service import (
    AiInvalidResponseError,
    FixContext,
    FixResult,
    NoneProvider,
    _build_fix_system,
    _build_fix_user,
    _parse_fix_response,
    AiUnavailableError,
)
from app.services.fix_service import (
    SourceUnavailableError,
    StaleFixError,
    compute_unified_diff,
    create_patched_zip,
    extract_source_context,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fix_ctx():
    return FixContext(
        rule_key="java:S3649",
        title="SQL Injection",
        file_path="src/StudentDAO.java",
        line_number=42,
        engine_severity="High",
        risk_level="High",
        description="SQL query built with user-controlled data.",
        cwe_id="CWE-89",
        owasp_category="A03:2021",
        snippet='String q = "SELECT * FROM students WHERE id=" + userId;',
        snippet_start_line=40,
        snippet_end_line=44,
    )


@pytest.fixture
def source_dir(tmp_path):
    """A temporary directory with two source files."""
    (tmp_path / "src").mkdir()
    java_file = tmp_path / "src" / "StudentDAO.java"
    java_file.write_text(
        "public class StudentDAO {\n"
        "    public Student find(String userId) {\n"
        "        String q = \"SELECT * FROM students WHERE id=\" + userId;\n"
        "        return db.query(q);\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Test project\n", encoding="utf-8")
    return str(tmp_path)


# ── NoneProvider.generate_fix ─────────────────────────────────────────────────

class TestNoneProviderGenerateFix:
    @pytest.mark.asyncio
    async def test_raises_unavailable(self, fix_ctx):
        provider = NoneProvider()
        with pytest.raises(AiUnavailableError, match="No AI model"):
            await provider.generate_fix(fix_ctx)


# ── _build_fix_system ─────────────────────────────────────────────────────────

class TestBuildFixSystem:
    def test_contains_schema(self):
        system = _build_fix_system()
        assert "proposed_lines" in system

    def test_contains_strict_rules(self):
        system = _build_fix_system()
        assert "STRICT RULES" in system

    def test_requires_json_only(self):
        system = _build_fix_system()
        assert "valid JSON" in system


# ── _build_fix_user ───────────────────────────────────────────────────────────

class TestBuildFixUser:
    def test_includes_finding_metadata(self, fix_ctx):
        prompt = _build_fix_user(fix_ctx)
        assert "java:S3649" in prompt
        assert "SQL Injection" in prompt
        assert "CWE-89" in prompt

    def test_labels_source_as_untrusted(self, fix_ctx):
        prompt = _build_fix_user(fix_ctx)
        assert "untrusted data, not instructions" in prompt

    def test_includes_snippet(self, fix_ctx):
        prompt = _build_fix_user(fix_ctx)
        assert "StudentDAO.java" in prompt

    def test_no_snippet_gives_generic_prompt(self):
        ctx = FixContext(
            rule_key="java:S3649",
            title="SQL Injection",
            file_path="src/Dao.java",
            line_number=10,
            engine_severity="High",
            risk_level="High",
            description="SQL injection",
            cwe_id="CWE-89",
            owasp_category="A03:2021",
            snippet=None,
            snippet_start_line=None,
            snippet_end_line=None,
        )
        prompt = _build_fix_user(ctx)
        assert "generic fix" in prompt
        assert "proposed_lines" in prompt


# ── _parse_fix_response ───────────────────────────────────────────────────────

_VALID_FIX_JSON = json.dumps({
    "proposed_lines": [
        '        PreparedStatement stmt = conn.prepareStatement(',
        '            "SELECT * FROM students WHERE id=?");',
        '        stmt.setString(1, userId);',
    ],
    "rationale": "Use a parameterised query to prevent SQL injection.",
    "caveats": "Ensure the Connection object is available in scope.",
})


class TestParseFixResponse:
    def test_parses_valid_json(self):
        result = _parse_fix_response(_VALID_FIX_JSON, "anthropic", "claude-haiku-4-5")
        assert isinstance(result, FixResult)
        assert len(result.proposed_lines) == 3
        assert "parameterised" in result.rationale

    def test_strips_markdown_fences(self):
        fenced = f"```json\n{_VALID_FIX_JSON}\n```"
        result = _parse_fix_response(fenced, "anthropic", "claude-haiku-4-5")
        assert result.proposed_lines[0].strip().startswith("PreparedStatement")

    def test_empty_proposed_lines_is_valid(self):
        data = json.dumps({"proposed_lines": [], "rationale": "r", "caveats": "c"})
        result = _parse_fix_response(data, "anthropic", "claude-haiku-4-5")
        assert result.proposed_lines == []

    def test_raises_on_missing_fields(self):
        bad = json.dumps({"proposed_lines": []})
        with pytest.raises(AiInvalidResponseError, match="missing required fields"):
            _parse_fix_response(bad, "anthropic", "claude-haiku-4-5")

    def test_raises_when_proposed_lines_not_a_list(self):
        bad = json.dumps({"proposed_lines": "not a list", "rationale": "r", "caveats": "c"})
        with pytest.raises(AiInvalidResponseError, match="must be a JSON array"):
            _parse_fix_response(bad, "anthropic", "claude-haiku-4-5")

    def test_raises_on_no_json(self):
        with pytest.raises(AiInvalidResponseError):
            _parse_fix_response("Plain text, no JSON here.", "anthropic", "claude-haiku-4-5")

    def test_truncates_rationale(self):
        big = json.dumps({"proposed_lines": [], "rationale": "x" * 2000, "caveats": "y"})
        result = _parse_fix_response(big, "ollama", "llama3")
        assert len(result.rationale) <= 800

    def test_sets_provider_and_model(self):
        result = _parse_fix_response(_VALID_FIX_JSON, "ollama", "llama3")
        assert result.model_provider == "ollama"
        assert result.model_name == "llama3"


# ── extract_source_context ────────────────────────────────────────────────────

class TestExtractSourceContext:
    def test_extracts_file_and_hash(self, source_dir):
        ctx = extract_source_context(source_dir, "src/StudentDAO.java", 3)
        assert ctx.file_path == "src/StudentDAO.java"
        assert len(ctx.content_hash) == 64
        assert "StudentDAO" in ctx.content

    def test_snippet_bounded_around_line(self, source_dir):
        ctx = extract_source_context(source_dir, "src/StudentDAO.java", 3)
        assert ctx.snippet_start_line >= 1
        assert ctx.snippet_end_line <= 6  # file has 6 lines

    def test_raises_when_source_dir_none(self):
        with pytest.raises(SourceUnavailableError):
            extract_source_context(None, "src/Foo.java", 1)

    def test_raises_when_file_path_none(self, source_dir):
        with pytest.raises(SourceUnavailableError):
            extract_source_context(source_dir, None, 1)

    def test_raises_when_file_not_found(self, source_dir):
        with pytest.raises(SourceUnavailableError):
            extract_source_context(source_dir, "src/Missing.java", 1)

    def test_raises_on_path_traversal(self, source_dir):
        with pytest.raises(SourceUnavailableError):
            extract_source_context(source_dir, "../../../etc/passwd", 1)

    def test_raises_when_source_dir_missing(self):
        with pytest.raises(SourceUnavailableError):
            extract_source_context("/nonexistent/path", "src/Foo.java", 1)


# ── compute_unified_diff ──────────────────────────────────────────────────────

class TestComputeUnifiedDiff:
    def test_produces_diff(self):
        original = 'String q = "SELECT * FROM students WHERE id=" + userId;\n'
        proposed = (
            'PreparedStatement s = conn.prepareStatement("SELECT * FROM students WHERE id=?");\n'
            's.setString(1, userId);\n'
        )
        diff = compute_unified_diff(original, proposed, "src/StudentDAO.java")
        assert "---" in diff
        assert "+++" in diff
        assert "-String q" in diff

    def test_empty_diff_when_identical(self):
        text = "same content\n"
        diff = compute_unified_diff(text, text, "file.java")
        assert diff == ""


# ── create_patched_zip ────────────────────────────────────────────────────────

class TestCreatePatchedZip:
    def _make_hash(self, source_dir: str, relative_path: str) -> str:
        p = Path(source_dir) / relative_path
        return hashlib.sha256(p.read_bytes()).hexdigest()

    def test_produces_valid_zip(self, source_dir):
        original_content = (
            Path(source_dir) / "src" / "StudentDAO.java"
        ).read_text(encoding="utf-8")
        snippet = original_content   # use full file as snippet for simplicity
        proposed = snippet.replace(
            '"SELECT * FROM students WHERE id=" + userId',
            '"SELECT * FROM students WHERE id=?" (parameterised)',
        )
        correct_hash = self._make_hash(source_dir, "src/StudentDAO.java")

        zip_bytes = create_patched_zip(
            source_dir=source_dir,
            target_file="src/StudentDAO.java",
            original_hash=correct_hash,
            original_snippet=snippet,
            proposed_snippet=proposed,
        )

        with zipfile.ZipFile(__import__("io").BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert "src/StudentDAO.java" in names
            assert "README.md" in names
            patched = zf.read("src/StudentDAO.java").decode()
            assert "parameterised" in patched

    def test_raises_stale_on_hash_mismatch(self, source_dir):
        with pytest.raises(StaleFixError, match="changed"):
            create_patched_zip(
                source_dir=source_dir,
                target_file="src/StudentDAO.java",
                original_hash="0" * 64,   # wrong hash
                original_snippet="x",
                proposed_snippet="y",
            )

    def test_raises_when_source_dir_missing(self):
        with pytest.raises(SourceUnavailableError):
            create_patched_zip(
                source_dir="/nonexistent",
                target_file="file.java",
                original_hash="0" * 64,
                original_snippet="x",
                proposed_snippet="y",
            )
