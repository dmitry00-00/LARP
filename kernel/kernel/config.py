"""Pydantic-Settings — env-driven config for the ingest kernel.

Урезанная копия `openclaw/config.py` из recruit (15.09.2026): оставлены ТОЛЬКО
ключи, которые читают перенесённые модули (`clients/llm`; клиент Telegram
убран 28.09.2026 — Telegram читает шлюз основы). Всё про recruit-бэкенд, GitHub-корпус и
расписания скиллов осталось там.

Дефолты LLM — локальный LM Studio, не облако. Причина из recruit (замер
14.08): девять ошибок разбора из десяти были мёртвым платным провайдером, а не
кодом. Клиент OpenAI-совместим, смена провайдера — три строки в `.env.ingest`:
    LLM_BASE_URL=https://api.deepseek.com/v1
    LLM_API_KEY=<ключ>   · LLM_MODEL=<модель>

Потолки генерации у облака и локали означают разное: в llama.cpp/LM Studio
окно ОДНО на промпт и ответ, и `max_tokens` вычитается из `n_ctx`. Поэтому
`llm_max_tokens_local` консервативен — см. `clients/llm.py`.

Плюс тонкие ручки обхода, которые модули читают из окружения напрямую
(`WATCH_*`, `TG_ACCOUNTS`, `ATTACHMENT_ROOT`) — их список в README.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.ingest",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Local state ───────────────────────────────────────────────
    openclaw_home: Path = Field(default=Path("/var/lib/hmb-ingest"))
    openclaw_sqlite_path: Path = Field(default=Path("/var/lib/hmb-ingest/state.sqlite"))

    # ── LLM (OpenAI-compatible) ──────────────────────────────────
    llm_base_url: str = Field(default="http://localhost:1234/v1")
    llm_api_key: str = Field(default="lm-studio")
    llm_model: str = Field(default="local-model")
    llm_timeout_sec: float = Field(default=180.0)
    llm_max_tokens: int = Field(default=8000)
    llm_max_tokens_local: int = Field(default=2048)

    # Telegram MTProto здесь больше нет (28.09.2026): Telegram читает общий шлюз основы
    # (~/core/services/tg-gateway), приём берёт посты у него — apps/ingest/hmb/importers/tg_gateway.py.

    # ── Cadence ───────────────────────────────────────────────────
    max_batch_size: int = Field(default=50)


_settings: Settings | None = None


def settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_for_tests() -> None:
    """Allow tests to mutate env then re-read settings."""
    global _settings
    _settings = None
