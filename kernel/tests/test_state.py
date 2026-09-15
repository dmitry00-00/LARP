"""Local SQLite state tests."""

from datetime import UTC, datetime
from pathlib import Path

from kernel.state import State


def test_telegram_offset_roundtrip(tmp_path: Path) -> None:
    state = State(tmp_path / "s.sqlite")
    assert state.get_last_message_id("@x") == 0
    state.set_last_message_id("@x", 42)
    assert state.get_last_message_id("@x") == 42
    state.set_last_message_id("@x", 100)
    assert state.get_last_message_id("@x") == 100


def test_skill_run_lifecycle(tmp_path: Path) -> None:
    state = State(tmp_path / "s.sqlite")
    run_id = state.start_run("watch")
    assert run_id > 0
    state.finish_run(run_id, status="success", items_processed=7)


def test_llm_call_logged(tmp_path: Path) -> None:
    state = State(tmp_path / "s.sqlite")
    state.log_llm_call(
        skill_name="classify",
        model="gemini",
        tokens_in=100,
        tokens_out=20,
        duration_ms=350,
        success=True,
    )
