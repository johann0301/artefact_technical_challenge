import json

import pytest
from fastapi.testclient import TestClient

from emporio import api
from emporio.agent import ToolCallTrace, TurnResult


@pytest.fixture(autouse=True)
def reset_runtime() -> None:
    api.runtime.agent = None
    api.runtime.dependencies = None
    api.runtime.histories.clear()
    api.runtime.locks.clear()


def _events(body: str) -> list[dict[str, object]]:
    return [
        json.loads(line[len("data: ") :]) for line in body.splitlines() if line.startswith("data: ")
    ]


def test_health_endpoint() -> None:
    response = TestClient(api.app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_returns_actionable_error_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # A whitespace-only key overrides any developer .env and is treated as missing.
    monkeypatch.setenv("OPENAI_API_KEY", " ")

    response = TestClient(api.app).post("/api/chat", json={"message": "oi", "session_id": "s1"})

    assert response.status_code == 503
    assert "OPENAI_API_KEY is required" in response.json()["detail"]


def test_chat_rejects_blank_message() -> None:
    response = TestClient(api.app).post("/api/chat", json={"message": "", "session_id": "s1"})

    assert response.status_code == 422


def test_chat_streams_tool_calls_text_deltas_and_done(monkeypatch: pytest.MonkeyPatch) -> None:
    trace = ToolCallTrace("search_products", {"query": "violão"})

    async def fake_run_turn(
        agent, dependencies, prompt, history=None, on_text=None, on_tool_call=None
    ):
        on_tool_call(trace)
        on_text("Olá")
        on_text(" mundo")
        return TurnResult(output="Olá mundo", history=["turn-1"], tool_calls=[trace])

    api.runtime.agent = object()
    api.runtime.dependencies = object()
    monkeypatch.setattr(api, "run_turn", fake_run_turn)

    response = TestClient(api.app).post(
        "/api/chat", json={"message": "quero um violão", "session_id": "s1"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response.text)
    assert events[0] == {
        "type": "tool_call",
        "name": "search_products",
        "arguments": {"query": "violão"},
    }
    assert {"type": "text", "delta": "Olá"} in events
    assert events[-1]["type"] == "done"
    assert events[-1]["output"] == "Olá mundo"
    assert events[-1]["tool_calls"] == [
        {"name": "search_products", "arguments": {"query": "violão"}}
    ]
    assert api.runtime.histories["s1"] == ["turn-1"]


def test_chat_emits_error_event_when_turn_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_run_turn(*args, **kwargs):
        raise RuntimeError("model unavailable")

    api.runtime.agent = object()
    api.runtime.dependencies = object()
    monkeypatch.setattr(api, "run_turn", failing_run_turn)

    response = TestClient(api.app).post("/api/chat", json={"message": "oi", "session_id": "s1"})

    events = _events(response.text)
    assert events == [{"type": "error", "message": "model unavailable"}]
    assert "s1" not in api.runtime.histories
