"""OpenAI-compatible chat-completions client (DeepSeek / OpenRouter / etc.).

Same shape as ``apps/backend/app/services/llm.py`` — kept in two places
on purpose so the harvester remains deployable in isolation.
"""

import json
import re
import time
from typing import Any

import httpx

from kernel.config import settings


class LLMError(RuntimeError):
    pass


class LLMNotConfiguredError(LLMError):
    pass


# ── DeepSeek pricing (USD per 1M tokens, as of 2025-05) ──────────────────────
# Source: platform.deepseek.com/docs/pricing
_PRICE: dict[str, dict[str, float]] = {
    # Актуальное поколение (25.07.2026): старые имена deepseek-chat /
    # deepseek-reasoner API больше НЕ принимает — отвечает 400 «The supported
    # API model names are deepseek-v4-pro or deepseek-v4-flash». Имя модели
    # здесь же служит ключом цены, поэтому новые имена обязаны быть в таблице,
    # иначе стоимость молча считается по _DEFAULT_PRICE.
    # ⚠ Цены ниже — перенесены со старого поколения (flash≈chat, pro≈reasoner);
    # сверить с platform.deepseek.com/docs/pricing и поправить при расхождении.
    "deepseek-v4-flash": {
        "input":        0.27,   # cache miss
        "input_cached": 0.07,   # cache hit (prompt_tokens_details.cached_tokens)
        "output":       1.10,
    },
    "deepseek-v4-pro": {
        "input":        0.55,
        "input_cached": 0.14,
        "output":       2.19,
    },
    # Легаси-имена: оставлены ради корректного пересчёта ИСТОРИИ трат в SQLite
    # (старые записи ссылаются на них). Для новых вызовов они уже невалидны.
    "deepseek-chat": {
        "input":        0.27,   # cache miss
        "input_cached": 0.07,   # cache hit (prompt_tokens_details.cached_tokens)
        "output":       1.10,
    },
    "deepseek-reasoner": {
        "input":        0.55,
        "input_cached": 0.14,
        "output":       2.19,
    },
}
_DEFAULT_PRICE = {"input": 0.27, "input_cached": 0.07, "output": 1.10}


def _is_local(base_url: str) -> bool:
    """Локальный эндпоинт (LM Studio/Ollama) — токены бесплатны."""
    return any(h in base_url for h in ("localhost", "127.0.0.1", "0.0.0.0", "::1"))


def _loads_tolerant(text: str) -> Any:
    """``json.loads``, устойчивый к ```-ограждению и прозе вокруг JSON.

    LM Studio с недавних версий НЕ принимает ``response_format=json_object``
    (HTTP 400: must be 'json_schema' or 'text'), поэтому на локальном эндпоинте
    просим ``text`` и достаём JSON сами. DeepSeek остаётся на ``json_object`` и
    приходит уже чистым — для него это обычный ``json.loads`` на первой же ветке.
    """
    s = (text or "").strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
    # Модель обрамила JSON прозой — вырезать внешний объект/массив.
    starts = [i for i in (s.find("{"), s.find("[")) if i != -1]
    end = max(s.rfind("}"), s.rfind("]"))
    if starts and end > min(starts):
        return json.loads(s[min(starts):end + 1])
    raise json.JSONDecodeError("no JSON in model output", s, 0)


def _calc_cost(model: str, tokens_in: int, tokens_out: int, cached: int,
               *, local: bool = False) -> float:
    """Return cost in USD. ``cached`` is the subset of tokens_in served from cache.

    Локальная модель бесплатна: считать её по прайсу DeepSeek (`_DEFAULT_PRICE`)
    значило бы врать в отчёте о тратах — ровно круглое число из ниоткуда,
    против которого AGENT_RULES §4.
    """
    if local:
        return 0.0
    p = _PRICE.get(model, _DEFAULT_PRICE)
    non_cached = max(tokens_in - cached, 0)
    return (
        non_cached * p["input"] / 1_000_000
        + cached   * p["input_cached"] / 1_000_000
        + tokens_out * p["output"] / 1_000_000
    )


# Автоопределение модели для LM Studio: его OpenAI-эндпоинт хочет реальный id,
# а держать имя загруженной модели в `.env` — лишняя ручная синхронизация.
# Сентинел `local-model` → GET /models → первая chat-модель. Кэшируется на
# процесс. Тот же приём, что у ассистента бэкенда (`assistant._resolve_model`).
_RESOLVED_MODEL: str | None = None


async def _resolve_model(client: httpx.AsyncClient, base: str, configured: str,
                         api_key: str) -> str:
    global _RESOLVED_MODEL
    if configured != "local-model":
        return configured
    if _RESOLVED_MODEL:
        return _RESOLVED_MODEL
    try:
        r = await client.get(f"{base}/models",
                             headers={"Authorization": f"Bearer {api_key}"})
        r.raise_for_status()
        ids = [m.get("id") for m in (r.json().get("data") or []) if m.get("id")]
        # Пропускаем эмбеддер, если рядом загружены обе модели.
        chat_ids = [i for i in ids if "embed" not in i.lower()]
        _RESOLVED_MODEL = (chat_ids or ids or [configured])[0]
    except Exception:  # noqa: BLE001
        # Не падаем: пусть сервер сам решит, что делать с `local-model`.
        _RESOLVED_MODEL = configured
    return _RESOLVED_MODEL


def _max_tokens_for(cfg, local: bool, explicit: int | None) -> int:
    """Явное значение вызывающего > настройка для этого транспорта.

    Разделение по транспорту, а не одно число на всех: у облака `max_tokens` —
    это защита от обрезанного JSON, у локали — вычет из общего окна. Одно и то
    же число означает в двух местах разное, и это уже стоило прогонов.
    """
    if explicit is not None:
        return explicit
    return cfg.llm_max_tokens_local if local else cfg.llm_max_tokens


# Подпись llama.cpp/LM Studio, когда `max_tokens` съел всё окно. Ловим по
# тексту, потому что кода у этой ошибки нет — только HTTP 400 общего вида.
_CTX_OVERFLOW = ("tokens to keep", "context length", "context window",
                 "exceeds the available context")


async def chat_json(
    *,
    system: str,
    user: str,
    model: str | None = None,
    temperature: float = 0.0,
    state=None,
    skill_name: str = "unknown",
    max_tokens: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Call chat-completions, parse JSON, log usage + cost.

    Returns ``(parsed_json, usage_meta)``. ``usage_meta`` carries
    tokens_in/tokens_out/cached_tokens/cost_usd/duration_ms.
    """
    cfg = settings()
    if not cfg.llm_api_key:
        raise LLMNotConfiguredError(
            "LLM_API_KEY is not configured — fill .env.ingest",
        )

    base = cfg.llm_base_url.rstrip("/")
    local = _is_local(base)
    headers = {
        "Authorization": f"Bearer {cfg.llm_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://hmb-market.local",
        "X-Title": "HMB-Market ingest",
    }
    url = base + "/chat/completions"

    started = time.perf_counter()
    success = False
    tokens_in: int = 0
    tokens_out: int = 0
    cached_tokens: int = 0
    cost_usd: float | None = None
    effective_model = model or cfg.llm_model
    try:
        async with httpx.AsyncClient(timeout=cfg.llm_timeout_sec) as client:
            # `local-model` → реальный id загруженной модели (GET /models).
            effective_model = await _resolve_model(
                client, base, effective_model, cfg.llm_api_key,
            )
            body = {
                "model": effective_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
                # LM Studio (локальный) отвечает HTTP 400 на json_object
                # ('must be json_schema or text') — ему шлём text и парсим сами
                # (_loads_tolerant). DeepSeek остаётся на json_object: он его
                # гарантирует, регресса на удалённом пути нет.
                "response_format": ({"type": "text"} if local
                                    else {"type": "json_object"}),
                # Потолок генерации. Раньше здесь стояло 8000 безусловно —
                # число, посчитанное для DeepSeek (окно 64k+, резерв под ответ
                # ничего не стоит). У локального сервера окно ОДНО на промпт и
                # на генерацию, поэтому те же 8000 при n_ctx 4096–8192 не
                # оставляли места под сам промпт, и llama.cpp отвечал HTTP 400
                # «tokens to keep from the initial prompt > context length» —
                # на КАЖДОМ разборе, независимо от длины поста.
                #
                # Ветка та же, что строкой выше у `response_format`: клиент уже
                # знал, что говорит с локалью, и всё равно слал облачное число.
                "max_tokens": _max_tokens_for(cfg, local, max_tokens),
            }
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage") or {}
        tokens_in  = usage.get("prompt_tokens") or 0
        tokens_out = usage.get("completion_tokens") or 0
        # DeepSeek returns cache stats in prompt_tokens_details
        details = usage.get("prompt_tokens_details") or {}
        cached_tokens = details.get("cached_tokens") or 0
        cost_usd = _calc_cost(effective_model, tokens_in, tokens_out, cached_tokens,
                              local=local)
        text = data["choices"][0]["message"]["content"]
        parsed = _loads_tolerant(text)
        success = True
        return parsed, {
            "tokens_in":     tokens_in,
            "tokens_out":    tokens_out,
            "cached_tokens": cached_tokens,
            "cost_usd":      cost_usd,
            "duration_ms":   int((time.perf_counter() - started) * 1000),
        }
    except httpx.HTTPStatusError as exc:
        # Тело ответа несёт ПРИЧИНУ (модель не найдена / превышен контекст /
        # невалидный параметр). Без него в error_text висит только «400 Bad
        # Request», и разбор слеп — ровно та тихая слепота, что мы и ловим.
        body_txt = ""
        try:
            body_txt = (exc.response.text or "")[:400]
        except Exception:
            body_txt = ""
        code = exc.response.status_code if exc.response is not None else "?"
        low = body_txt.lower()
        if code == 400 and any(k in low for k in _CTX_OVERFLOW):
            # Сырой текст llama.cpp не говорит, что делать, а делать надо одно
            # из двух — и оба варианта здесь названы. Без этого в `error_text`
            # оседает строка, по которой оператор ищет причину заново
            # (AGENT_RULES §2: в вывод класть то, на чём сработало).
            raise LLMError(
                f"LLM HTTP 400 — запрос не помещается в окно локальной модели. "
                f"Сейчас max_tokens={_max_tokens_for(cfg, local, max_tokens)} "
                f"вычитается из n_ctx, заданного при загрузке модели в LM Studio. "
                f"Либо опусти LLM_MAX_TOKENS_LOCAL в .env.ingest, либо загрузи "
                f"модель с бóльшим контекстом. Ответ сервера: {body_txt}"
            ) from exc
        raise LLMError(f"LLM HTTP {code}: {body_txt or exc}") from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"LLM HTTP error: {exc}") from exc
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise LLMError(f"LLM bad response: {exc}") from exc
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        if state is not None:
            state.log_llm_call(
                skill_name=skill_name,
                model=effective_model,
                tokens_in=tokens_in or None,
                tokens_out=tokens_out or None,
                cached_tokens=cached_tokens or None,
                cost_usd=cost_usd,
                duration_ms=duration_ms,
                success=success,
            )
