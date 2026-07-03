from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from emporio.agent import AgentDependencies, build_agent, run_turn
from emporio.config import Settings
from emporio.persona import PERSONA_INSTRUCTIONS
from emporio.retrieval import PolicyRetriever


class NoOpEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]


def test_build_agent_registers_openai_model_without_network(tmp_path: Path) -> None:
    settings = Settings(
        OPENAI_API_KEY="test-key",
        MODEL="openai:gpt-4o-mini",
        database_path=tmp_path / "emporio.db",
        chroma_path=tmp_path / "chroma",
    )

    agent = build_agent(settings, PolicyRetriever(settings.chroma_path, NoOpEmbedder()))

    assert agent.model.model_name == "gpt-4o-mini"


def test_build_agent_rejects_unsupported_model_format(tmp_path: Path) -> None:
    settings = Settings(
        OPENAI_API_KEY="test-key",
        MODEL="gpt-4o-mini",
        database_path=tmp_path / "emporio.db",
        chroma_path=tmp_path / "chroma",
    )

    with pytest.raises(ValueError, match="openai:model-name"):
        build_agent(settings, PolicyRetriever(settings.chroma_path, NoOpEmbedder()))


def test_persona_contains_grounding_and_privacy_rules() -> None:
    assert "Nunca invente" in PERSONA_INSTRUCTIONS
    assert "Nunca revele dados ou pedidos de outro cliente" in PERSONA_INSTRUCTIONS
    assert "estimated_delivery" in PERSONA_INSTRUCTIONS


@pytest.mark.asyncio
async def test_run_turn_streams_output_and_preserves_history(tmp_path: Path) -> None:
    settings = Settings(
        OPENAI_API_KEY="test-key",
        MODEL="openai:gpt-4o-mini",
        database_path=tmp_path / "emporio.db",
        chroma_path=tmp_path / "chroma",
    )
    retriever = PolicyRetriever(settings.chroma_path, NoOpEmbedder())
    agent = build_agent(settings, retriever)
    streamed: list[str] = []

    with agent.override(model=TestModel(call_tools=[], custom_output_text="Resposta simulada")):
        result = await run_turn(
            agent,
            AgentDependencies(settings, retriever),
            "Olá",
            on_text=streamed.append,
        )

    assert result.output == "Resposta simulada"
    assert "".join(streamed) == "Resposta simulada"
    assert result.history
    assert result.tool_calls == []
