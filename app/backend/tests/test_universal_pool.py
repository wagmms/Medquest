import json
import pytest

from api import universal_pool


@pytest.fixture(autouse=True)
def clear_provider_cooldowns():
    universal_pool._cooldowns.clear()
    yield
    universal_pool._cooldowns.clear()


def test_gemini_generation_success(monkeypatch):
    monkeypatch.setattr(universal_pool.gemini_pool, "_keys", [object()])
    monkeypatch.setattr(
        universal_pool.gemini_pool,
        "generate_content",
        lambda **_: {"text": "Resposta médica detalhada e aprofundada.", "model": "gemini-3.5-flash-lite"},
    )

    result = universal_pool.generate_content_with_fallback("Qual o diagnóstico?")

    assert result["source"] == "gemini"
    assert result["model"] == "gemini-3.5-flash-lite"
    assert "Resposta médica" in result["text"]


def test_short_gemini_answer_rejected_by_validator(monkeypatch):
    monkeypatch.setattr(universal_pool.gemini_pool, "_keys", [object()])
    monkeypatch.setattr(
        universal_pool.gemini_pool,
        "generate_content",
        lambda **_: {"text": "curto", "model": "gemini-test"},
    )

    with pytest.raises(RuntimeError) as exc_info:
        universal_pool.generate_content_with_fallback(
            "prompt", response_validator=lambda text: len(text) > 10
        )

    assert "Todos os provedores de IA falharam" in str(exc_info.value)


def test_gemini_failure_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(universal_pool.gemini_pool, "_keys", [object()])

    def fail_gemini(**_):
        raise RuntimeError("Google Gemini API indisponível")

    monkeypatch.setattr(universal_pool.gemini_pool, "generate_content", fail_gemini)

    with pytest.raises(RuntimeError) as exc_info:
        universal_pool.generate_content_with_fallback("prompt")

    assert "Todos os provedores de IA falharam (gemini)" in str(exc_info.value)


def test_no_keys_available_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(universal_pool.gemini_pool, "_keys", [])

    with pytest.raises(RuntimeError) as exc_info:
        universal_pool.generate_content_with_fallback("prompt")

    assert "nenhuma chave Gemini disponível" in str(exc_info.value)


def test_provider_order_only_gemini(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_ORDER", "groq,gemini,openrouter,ollama")
    order = universal_pool._provider_order()
    assert order == ["gemini"]


def test_provider_status_contains_gemini_and_no_secrets(monkeypatch):
    status = universal_pool.provider_status()
    serialized = json.dumps(status)

    assert "gemini" in status["providers"]
    assert "order" in status
    assert status["order"] == ["gemini"]
    # Garante que provedores excluídos não constam na saída operacional
    assert "groq" not in status["providers"]
    assert "openrouter" not in status["providers"]
    assert "ollama" not in status["providers"]
    # Garante que timeouts estão estruturados
    assert "global_budget_seconds" in status["timeouts"]
