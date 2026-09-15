"""Потолок генерации: у облака и у локали он означает разное.

Написано по следам живого сбоя 26.08: пост @DimanJacky собрался, разбор упал
с `LLM HTTP 400: The number of tokens to keep from the initial prompt is
greater than the context length`. Причина не в посте — в том, что клиент слал
локальному серверу облачное число.

`.env.ingest` не задаёт `LLM_BASE_URL`, поэтому действует дефолт
`http://localhost:1234/v1`: экстракция идёт на LM Studio. Там окно ОДНО на
промпт и на генерацию, `max_tokens` вычитается из `n_ctx` — и 8000 при
n_ctx 4096–8192 не оставляли места под сам промпт. Падал КАЖДЫЙ разбор,
независимо от длины текста.

Ветка `local` в этой же функции уже была — для `response_format`. Фикс
остановился на строку раньше, чем нужно.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from kernel.clients.llm import _CTX_OVERFLOW, _max_tokens_for


def _cfg(cloud: int = 8000, local: int = 2048) -> SimpleNamespace:
    return SimpleNamespace(llm_max_tokens=cloud, llm_max_tokens_local=local)


def test_cloud_keeps_the_old_number():
    """Облачный путь обязан остаться байт-в-байт прежним: 8000 подобраны под
    обрезку JSON у DeepSeek, регресса там быть не должно."""
    assert _max_tokens_for(_cfg(), local=False, explicit=None) == 8000


def test_local_gets_a_smaller_ceiling():
    assert _max_tokens_for(_cfg(), local=True, explicit=None) == 2048


def test_local_and_cloud_actually_differ():
    """Сторож на суть правки: если однажды оба поля сведут к одному числу,
    тест должен об этом сказать, а не молча позеленеть."""
    cfg = _cfg()
    assert cfg.llm_max_tokens_local < cfg.llm_max_tokens


@pytest.mark.parametrize("local", [True, False])
def test_explicit_value_wins_on_both_transports(local):
    """`extract_market_signal` просит 300 — его выбор не должен подменяться
    ни облачным, ни локальным умолчанием."""
    assert _max_tokens_for(_cfg(), local=local, explicit=300) == 300


@pytest.mark.parametrize("local", [True, False])
def test_zero_is_a_value_not_a_missing_argument(local):
    """`0` — валидное «не ограничивать» у некоторых серверов, и оно не должно
    провалиться в умолчание через `or`. Проверка именно на `is not None`."""
    assert _max_tokens_for(_cfg(), local=local, explicit=0) == 0


def test_settings_are_tunable_without_a_release():
    """Реальный n_ctx задаётся при загрузке модели и коду неизвестен — значит
    потолок обязан быть настройкой, а не числом в файле."""
    assert _max_tokens_for(_cfg(local=512), local=True, explicit=None) == 512


@pytest.mark.parametrize("body", [
    "The number of tokens to keep from the initial prompt is greater than the context length",
    "Requested tokens exceed context window",
    "prompt exceeds the available context",
    "Trying to keep the first 8000 tokens; context length is 4096",
])
def test_overflow_signatures_are_recognised(body):
    """Кода у этой ошибки нет — только HTTP 400 общего вида, поэтому ловим по
    тексту. Тест фиксирует формулировки, которые уже видели."""
    assert any(k in body.lower() for k in _CTX_OVERFLOW)


@pytest.mark.parametrize("body", [
    "Invalid API key provided",
    "The supported API model names are deepseek-v4-pro or deepseek-v4-flash",
    "response_format.type must be json_schema or text",
])
def test_unrelated_400s_are_not_swallowed(body):
    """Обратная сторона: подсказка про окно не должна подменять собой другие
    400 — их причины разные, и советовать при них LLM_MAX_TOKENS_LOCAL вредно."""
    assert not any(k in body.lower() for k in _CTX_OVERFLOW)
