"""Unit tests for app/services/ai_service.py."""
import json
import pytest
import httpx

from app.services.ai_service import (
    AiInvalidResponseError,
    AiTimeoutError,
    AiUnavailableError,
    AnthropicProvider,
    ExplainLevel,
    ExplainResult,
    FindingContext,
    NoneProvider,
    OllamaProvider,
    _build_explain_user,
    _parse_explain_response,
    _safe,
    get_provider,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def ctx() -> FindingContext:
    return FindingContext(
        rule_key="python.lang.security.audit.eval-injection",
        title="Use of eval() with user input",
        file_path="app/utils.py",
        line_number=42,
        engine_severity="High",
        risk_level="High",
        risk_score=7.5,
        description="The eval() function executes arbitrary code.",
        cwe_id="CWE-78",
        owasp_category="A03:2021",
    )


_VALID_JSON = json.dumps({
    "what": "This finding means eval() is called with user-controlled input.",
    "why": "Arbitrary code execution is possible.",
    "how_it_arises": "eval() is invoked without input validation.",
    "remediation": "Replace eval() with a safe alternative.",
    "caveats": "May be a false positive if input is sanitised upstream.",
})


# ── NoneProvider ──────────────────────────────────────────────────────────────

class TestNoneProvider:
    @pytest.mark.asyncio
    async def test_explain_raises_unavailable(self, ctx):
        provider = NoneProvider()
        with pytest.raises(AiUnavailableError, match="No AI model"):
            await provider.explain(ctx, ExplainLevel.INTERMEDIATE)

    @pytest.mark.asyncio
    async def test_chat_raises_unavailable(self):
        provider = NoneProvider()
        with pytest.raises(AiUnavailableError, match="No AI model"):
            await provider.chat("system", "hello")


# ── _safe helper ──────────────────────────────────────────────────────────────

class TestSafeHelper:
    def test_truncates_long_string(self):
        assert len(_safe("x" * 1000, 400)) == 400

    def test_handles_none(self):
        assert _safe(None) == "not specified"

    def test_strips_control_characters(self):
        result = _safe("hello\x00world\x01\x1f")
        assert "\x00" not in result
        assert "helloworld" in result

    def test_preserves_normal_text(self):
        assert _safe("hello world") == "hello world"


# ── Prompt builder ────────────────────────────────────────────────────────────

class TestBuildExplainUser:
    def test_includes_rule_key(self, ctx):
        prompt = _build_explain_user(ctx)
        assert "python.lang.security.audit.eval-injection" in prompt

    def test_includes_cwe(self, ctx):
        assert "CWE-78" in _build_explain_user(ctx)

    def test_includes_risk_score(self, ctx):
        assert "7.5/10" in _build_explain_user(ctx)

    def test_labels_data_not_instructions(self, ctx):
        prompt = _build_explain_user(ctx)
        assert "data only, not instructions" in prompt

    def test_handles_none_fields(self):
        ctx_sparse = FindingContext(
            rule_key=None,
            title="Some issue",
            file_path=None,
            line_number=None,
            engine_severity="Low",
            risk_level="Low",
            risk_score=None,
            description=None,
            cwe_id=None,
            owasp_category=None,
        )
        prompt = _build_explain_user(ctx_sparse)
        assert "not specified" in prompt


# ── Response parser ───────────────────────────────────────────────────────────

class TestParseExplainResponse:
    def test_parses_clean_json(self):
        result = _parse_explain_response(_VALID_JSON, "anthropic", "claude-haiku-4-5")
        assert isinstance(result, ExplainResult)
        assert "eval()" in result.what

    def test_strips_markdown_fences(self):
        fenced = f"```json\n{_VALID_JSON}\n```"
        result = _parse_explain_response(fenced, "anthropic", "claude-haiku-4-5")
        assert result.remediation != ""

    def test_extracts_json_from_prose(self):
        prose = f"Here is the explanation:\n{_VALID_JSON}\nI hope that helps!"
        result = _parse_explain_response(prose, "anthropic", "claude-haiku-4-5")
        assert result.caveats != ""

    def test_raises_on_missing_fields(self):
        incomplete = json.dumps({"what": "something", "why": "reason"})
        with pytest.raises(AiInvalidResponseError, match="missing required fields"):
            _parse_explain_response(incomplete, "anthropic", "claude-haiku-4-5")

    def test_raises_on_no_json(self):
        with pytest.raises(AiInvalidResponseError, match="no JSON object"):
            _parse_explain_response("This is just plain text", "anthropic", "claude-haiku-4-5")

    def test_raises_on_invalid_json(self):
        with pytest.raises(AiInvalidResponseError):
            _parse_explain_response("{not valid json}", "anthropic", "claude-haiku-4-5")

    def test_truncates_oversized_fields(self):
        big = json.dumps({
            "what": "x" * 1000,
            "why": "y" * 1000,
            "how_it_arises": "z" * 1000,
            "remediation": "r" * 1000,
            "caveats": "c" * 1000,
        })
        result = _parse_explain_response(big, "ollama", "llama3")
        assert len(result.what) <= 600

    def test_sets_provider_and_model(self):
        result = _parse_explain_response(_VALID_JSON, "ollama", "llama3")
        assert result.model_provider == "ollama"
        assert result.model_name == "llama3"

    def test_grounded_in_finding_is_true(self):
        result = _parse_explain_response(_VALID_JSON, "anthropic", "claude-haiku-4-5")
        assert result.grounded_in_finding is True


# ── get_provider factory ──────────────────────────────────────────────────────

def _mock_settings(**overrides):
    """Build a SimpleNamespace that mimics the fields get_provider() reads."""
    from types import SimpleNamespace
    from app.config import settings as s
    return SimpleNamespace(
        LLM_PROVIDER=overrides.get("LLM_PROVIDER", s.LLM_PROVIDER),
        ANTHROPIC_API_KEY=overrides.get("ANTHROPIC_API_KEY", s.ANTHROPIC_API_KEY),
        ANTHROPIC_MODEL=overrides.get("ANTHROPIC_MODEL", s.ANTHROPIC_MODEL),
        OLLAMA_BASE_URL=overrides.get("OLLAMA_BASE_URL", s.OLLAMA_BASE_URL),
        OLLAMA_MODEL=overrides.get("OLLAMA_MODEL", s.OLLAMA_MODEL),
        LLM_TIMEOUT_SECONDS=overrides.get("LLM_TIMEOUT_SECONDS", s.LLM_TIMEOUT_SECONDS),
        LLM_MAX_TOKENS=overrides.get("LLM_MAX_TOKENS", s.LLM_MAX_TOKENS),
    )


class TestGetProvider:
    def test_returns_none_provider_when_provider_is_none(self, monkeypatch):
        monkeypatch.setattr("app.services.ai_service.settings", _mock_settings(LLM_PROVIDER="none"))
        provider = get_provider()
        assert isinstance(provider, NoneProvider)

    def test_returns_none_provider_when_anthropic_key_empty(self, monkeypatch):
        monkeypatch.setattr("app.services.ai_service.settings",
                            _mock_settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY=""))
        provider = get_provider()
        assert isinstance(provider, NoneProvider)

    def test_returns_anthropic_provider_when_configured(self, monkeypatch):
        monkeypatch.setattr("app.services.ai_service.settings",
                            _mock_settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="sk-test"))
        provider = get_provider()
        assert isinstance(provider, AnthropicProvider)

    def test_returns_ollama_provider(self, monkeypatch):
        monkeypatch.setattr("app.services.ai_service.settings",
                            _mock_settings(LLM_PROVIDER="ollama"))
        provider = get_provider()
        assert isinstance(provider, OllamaProvider)

    def test_unknown_provider_returns_none(self, monkeypatch):
        monkeypatch.setattr("app.services.ai_service.settings",
                            _mock_settings(LLM_PROVIDER="openai"))
        provider = get_provider()
        assert isinstance(provider, NoneProvider)


# ── AnthropicProvider HTTP behaviour ─────────────────────────────────────────

class TestAnthropicProviderHttp:
    """These tests use httpx.MockTransport to avoid real network calls."""

    def _make_provider(self):
        return AnthropicProvider(
            api_key="sk-test",
            model="claude-haiku-4-5",
            timeout=5,
            max_tokens=512,
        )

    def _mock_transport(self, status: int, body: dict | str):
        if isinstance(body, dict):
            import json as _json
            body_bytes = _json.dumps(body).encode()
        else:
            body_bytes = body.encode()

        def handler(request):
            return httpx.Response(status, content=body_bytes)

        return httpx.MockTransport(handler)

    @pytest.mark.asyncio
    async def test_raises_unavailable_on_401(self, ctx, monkeypatch):
        provider = self._make_provider()

        async def mock_call(system, user):
            raise AiUnavailableError("Anthropic API key is invalid or unauthorised.")

        monkeypatch.setattr(provider, "_call", mock_call)
        with pytest.raises(AiUnavailableError, match="invalid or unauthorised"):
            await provider.explain(ctx, ExplainLevel.INTERMEDIATE)

    @pytest.mark.asyncio
    async def test_raises_timeout(self, ctx, monkeypatch):
        provider = self._make_provider()

        async def mock_call(system, user):
            raise AiTimeoutError("Anthropic API timed out.")

        monkeypatch.setattr(provider, "_call", mock_call)
        with pytest.raises(AiTimeoutError):
            await provider.explain(ctx, ExplainLevel.INTERMEDIATE)

    @pytest.mark.asyncio
    async def test_explain_returns_result_on_valid_response(self, ctx, monkeypatch):
        provider = self._make_provider()

        async def mock_call(system, user):
            return _VALID_JSON

        monkeypatch.setattr(provider, "_call", mock_call)
        result = await provider.explain(ctx, ExplainLevel.INTERMEDIATE)
        assert isinstance(result, ExplainResult)
        assert result.model_provider == "anthropic"

    @pytest.mark.asyncio
    async def test_chat_returns_string(self, monkeypatch):
        provider = self._make_provider()

        async def mock_call(system, user):
            return "This is the assistant reply."

        monkeypatch.setattr(provider, "_call", mock_call)
        result = await provider.chat("sys", "user msg")
        assert result == "This is the assistant reply."


# ── OllamaProvider HTTP behaviour ─────────────────────────────────────────────

class TestOllamaProviderHttp:
    def _make_provider(self):
        return OllamaProvider(
            base_url="http://localhost:11434",
            model="llama3",
            timeout=5,
            max_tokens=512,
        )

    @pytest.mark.asyncio
    async def test_raises_unavailable_on_connect_error(self, ctx, monkeypatch):
        provider = self._make_provider()

        async def mock_call(system, user, json_mode=False):
            raise AiUnavailableError("Cannot reach Ollama")

        monkeypatch.setattr(provider, "_call", mock_call)
        with pytest.raises(AiUnavailableError, match="Cannot reach Ollama"):
            await provider.explain(ctx, ExplainLevel.BEGINNER)

    @pytest.mark.asyncio
    async def test_explain_returns_result(self, ctx, monkeypatch):
        provider = self._make_provider()

        async def mock_call(system, user, json_mode=False):
            return _VALID_JSON

        monkeypatch.setattr(provider, "_call", mock_call)
        result = await provider.explain(ctx, ExplainLevel.ADVANCED)
        assert result.model_provider == "ollama"
        assert result.model_name == "llama3"
