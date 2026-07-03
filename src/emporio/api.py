"""FastAPI interface: one SSE chat endpoint over the shared agent core."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pydantic_ai.messages import ModelMessage

from emporio.agent import AgentDependencies, build_agent, run_turn
from emporio.config import MissingConfigurationError, get_settings
from emporio.ingest_policies import OpenAIEmbedder
from emporio.retrieval import PolicyIndexNotInitializedError, PolicyRetriever


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(min_length=1, max_length=128)


@dataclass
class ChatRuntime:
    """Lazily built agent shared by all sessions, plus per-session history."""

    agent: Any = None
    dependencies: AgentDependencies | None = None
    histories: dict[str, list[ModelMessage]] = field(default_factory=dict)
    locks: dict[str, asyncio.Lock] = field(default_factory=dict)

    def ensure_agent(self) -> None:
        if self.agent is not None:
            return
        settings = get_settings()
        api_key = settings.require_openai_api_key()
        retriever = PolicyRetriever(
            settings.chroma_path,
            OpenAIEmbedder(api_key, settings.embedding_model),
        )
        self.agent = build_agent(settings, retriever)
        self.dependencies = AgentDependencies(settings, retriever)

    def lock_for(self, session_id: str) -> asyncio.Lock:
        return self.locks.setdefault(session_id, asyncio.Lock())


runtime = ChatRuntime()
app = FastAPI(title="Empório da Música — Support Agent API")


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


async def _stream_turn(request: ChatRequest) -> AsyncIterator[str]:
    assert runtime.dependencies is not None
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async with runtime.lock_for(request.session_id):
        history = runtime.histories.get(request.session_id, [])
        task = asyncio.create_task(
            run_turn(
                runtime.agent,
                runtime.dependencies,
                request.message,
                history=history,
                on_text=lambda delta: queue.put_nowait({"type": "text", "delta": delta}),
                on_tool_call=lambda trace: queue.put_nowait(
                    {"type": "tool_call", "name": trace.name, "arguments": trace.arguments}
                ),
            )
        )
        try:
            while not (task.done() and queue.empty()):
                try:
                    yield _sse(await asyncio.wait_for(queue.get(), timeout=0.1))
                except TimeoutError:
                    continue
            result = task.result()
        except Exception as error:  # surface one structured error event, then stop
            task.cancel()
            yield _sse({"type": "error", "message": str(error)})
            return
        runtime.histories[request.session_id] = result.history
        yield _sse(
            {
                "type": "done",
                "output": result.output,
                "tool_calls": [
                    {"name": trace.name, "arguments": trace.arguments}
                    for trace in result.tool_calls
                ],
            }
        )


@app.post("/api/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    try:
        runtime.ensure_agent()
    except (MissingConfigurationError, PolicyIndexNotInitializedError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return StreamingResponse(_stream_turn(request), media_type="text/event-stream")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Empório da Música agent API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
