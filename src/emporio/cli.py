"""Rich terminal chat interface with optional Markdown transcript export."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from pydantic_ai.messages import ModelMessage
from rich.console import Console
from rich.prompt import Prompt

from emporio.agent import AgentDependencies, ToolCallTrace, build_agent, run_turn
from emporio.config import MissingConfigurationError, get_settings
from emporio.ingest_policies import OpenAIEmbedder
from emporio.retrieval import PolicyRetriever

console = Console()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chat with the Empório da Música agent.")
    parser.add_argument(
        "--transcript",
        type=Path,
        help="Write the conversation and tool calls to a Markdown file on exit.",
    )
    return parser


def _write_transcript(path: Path, turns: list[dict[str, object]]) -> None:
    lines = ["# Empório da Música — Example Conversation", ""]
    for turn in turns:
        lines.extend(("## Cliente", "", str(turn["user"]), "", "## Assistente", ""))
        lines.extend((str(turn["assistant"]), ""))
        tool_calls = turn["tool_calls"]
        if tool_calls:
            lines.extend(("<details>", "<summary>Tool calls</summary>", "", "```json"))
            lines.append(json.dumps(tool_calls, ensure_ascii=False, indent=2))
            lines.extend(("```", "", "</details>", ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


async def _chat(transcript_path: Path | None) -> None:
    settings = get_settings()
    try:
        api_key = settings.require_openai_api_key()
    except MissingConfigurationError as error:
        console.print(f"[red]{error}[/red]")
        raise SystemExit(2) from error

    retriever = PolicyRetriever(
        settings.chroma_path,
        OpenAIEmbedder(api_key, settings.embedding_model),
    )
    agent = build_agent(settings, retriever)
    dependencies = AgentDependencies(settings, retriever)
    history: list[ModelMessage] = []
    transcript: list[dict[str, object]] = []

    console.print("[bold blue]Empório da Música[/bold blue] — Sua música começa aqui.")
    console.print("Digite [bold]/sair[/bold] para encerrar.\n")
    while True:
        prompt = Prompt.ask("[bold]Você[/bold]").strip()
        if prompt.lower() in {"/sair", "/exit", "exit", "quit"}:
            break
        if not prompt:
            continue

        console.print("[bold green]Assistente[/bold green]: ", end="")

        def on_text(delta: str) -> None:
            console.print(delta, end="", highlight=False, soft_wrap=True)

        def on_tool_call(trace: ToolCallTrace) -> None:
            console.print(f"\n[dim]🔧 {trace.name}: {trace.arguments}[/dim]")
            console.print("[bold green]Assistente[/bold green]: ", end="")

        result = await run_turn(
            agent,
            dependencies,
            prompt,
            history,
            on_text=on_text,
            on_tool_call=on_tool_call,
        )
        history = result.history
        console.print("\n")
        transcript.append(
            {
                "user": prompt,
                "assistant": result.output,
                "tool_calls": [
                    {"name": trace.name, "arguments": trace.arguments}
                    for trace in result.tool_calls
                ],
            }
        )

    if transcript_path:
        _write_transcript(transcript_path, transcript)
        console.print(f"[green]Transcript saved to {transcript_path}[/green]")


def main() -> None:
    arguments = _parser().parse_args()
    asyncio.run(_chat(arguments.transcript))


if __name__ == "__main__":
    main()
