"""Provedor unificado de IA para o MedQuest com foco exclusivo no Google Gemini."""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable, Dict, Optional

from api.gemini_pool import gemini_pool

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER_ORDER = ("gemini",)
DEFAULT_GLOBAL_TIMEOUT_BUDGET = 30.0
DEFAULT_PROVIDER_TIMEOUT = 10.0

_cooldowns: dict[tuple[str, int, str], float] = {}
_cooldown_lock = threading.Lock()


class CircuitBreaker:
    """Circuit Breaker defensivo em memória para proteger workers contra degradação de IA externa."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"
        self.lock = threading.Lock()

    def can_execute(self) -> bool:
        now = time.time()
        with self.lock:
            if self.state == "OPEN":
                if now - self.last_failure_time >= self.recovery_timeout:
                    self.state = "HALF_OPEN"
                    return True
                return False
            return True

    def record_success(self):
        with self.lock:
            self.failure_count = 0
            self.state = "CLOSED"

    def record_failure(self):
        now = time.time()
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = now
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning(
                    "[CircuitBreaker] Circuito aberto por %.0fs após %d falhas consecutivas.",
                    self.recovery_timeout,
                    self.failure_count,
                )

    def reset(self):
        with self.lock:
            self.failure_count = 0
            self.last_failure_time = 0.0
            self.state = "CLOSED"


circuit_breaker = CircuitBreaker()


def _csv_env(name: str, fallback: tuple[str, ...] = ()) -> list[str]:
    values = [value.strip() for value in os.environ.get(name, "").split(",") if value.strip()]
    return values or [value for value in fallback if value]


def _provider_order() -> list[str]:
    requested = _csv_env("AI_PROVIDER_ORDER", DEFAULT_PROVIDER_ORDER)
    valid = []
    for provider in requested:
        normalized = provider.lower()
        if normalized in DEFAULT_PROVIDER_ORDER and normalized not in valid:
            valid.append(normalized)
    return valid or list(DEFAULT_PROVIDER_ORDER)


def _valid_text(text: Any, validator: Optional[Callable[[str], bool]]) -> bool:
    return isinstance(text, str) and bool(text.strip()) and (validator is None or validator(text.strip()))


def generate_content_with_fallback(
    prompt: str,
    system_instruction: Optional[str] = None,
    json_mode: bool = False,
    temperature: float = 0.2,
    timeout: Optional[int] = None,
    response_validator: Optional[Callable[[str], bool]] = None,
    provider_order: Optional[list[str] | tuple[str, ...]] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Gera conteúdo via Google Gemini Pool com controle de timeout, validação e Circuit Breaker."""
    order = provider_order if provider_order is not None else _provider_order()
    providers = [p for p in order if p in DEFAULT_PROVIDER_ORDER]
    if not providers or "gemini" not in providers:
        raise RuntimeError("Nenhum provedor válido configurado (esperado: gemini).")

    if gemini_pool.total_keys <= 0:
        raise RuntimeError("Todos os provedores de IA falharam (nenhuma chave Gemini disponível).")

    if not circuit_breaker.can_execute():
        logger.warning("[UniversalPool] Circuit breaker ativado (Fast-Fail). Rejeitando chamada de IA.")
        raise RuntimeError("Todos os provedores de IA falharam (circuito aberto - Fast-Fail).")

    configured_provider_timeout = max(
        1.0,
        float(os.environ.get("AI_PROVIDER_TIMEOUT", str(DEFAULT_PROVIDER_TIMEOUT))),
    )
    provider_timeout = float(timeout) if timeout is not None else configured_provider_timeout
    per_request_timeout = max(5, min(14, int(provider_timeout / 2)))
    max_budget = min(float(provider_timeout * 1.5), 20.0) if timeout is not None else 20.0
    max_total_seconds = max(provider_timeout, max_budget)

    try:
        response = gemini_pool.generate_content(
            prompt=prompt,
            system_instruction=system_instruction,
            json_mode=json_mode,
            model=model,
            temperature=temperature,
            timeout=per_request_timeout,
            max_total_seconds=max_total_seconds,
        )
        text = response.get("text", "")
        if _valid_text(text, response_validator):
            circuit_breaker.record_success()
            return {
                "text": text.strip(),
                "source": "gemini",
                "model": response.get("model", "gemini"),
            }
        logger.warning("[UniversalPool] Gemini retornou resposta vazia ou rejeitada pelo validador.")
        circuit_breaker.record_failure()
    except Exception as error:
        circuit_breaker.record_failure()
        logger.warning("[UniversalPool] Gemini falhou: %s", error)

    raise RuntimeError("Todos os provedores de IA falharam (gemini).")


def provider_status() -> Dict[str, Any]:
    """Retorna configuração operacional sem revelar chaves ou segredos."""
    now = time.time()
    with _cooldown_lock:
        cooldowns = [
            {
                "provider": provider,
                "key_index": index + 1,
                "model": model,
                "remaining_seconds": round(until - now),
            }
            for (provider, index, model), until in _cooldowns.items()
            if until > now
        ]

    return {
        "order": list(DEFAULT_PROVIDER_ORDER),
        "providers": {
            "gemini": {
                "configured": gemini_pool.total_keys > 0,
                "keys": gemini_pool.total_keys,
                "models": list(gemini_pool.models),
            },
        },
        "cooldowns": cooldowns,
        "timeouts": {
            "global_budget_seconds": max(
                1.0,
                float(os.environ.get("AI_GLOBAL_TIMEOUT_BUDGET", str(DEFAULT_GLOBAL_TIMEOUT_BUDGET))),
            ),
            "provider_timeout_seconds": max(
                1.0,
                float(os.environ.get("AI_PROVIDER_TIMEOUT", str(DEFAULT_PROVIDER_TIMEOUT))),
            ),
        },
    }
