"""One-command setup for structured data and the policy index."""

from __future__ import annotations

from rich.console import Console

from emporio.config import DATA_DIR, MissingConfigurationError, get_settings
from emporio.etl import build_database
from emporio.ingest_policies import OpenAIEmbedder, ingest_policy_documents

console = Console()


def main() -> None:
    settings = get_settings()
    console.print("[bold]Building SQLite database...[/bold]")
    counts = build_database(settings.database_path)
    console.print(
        "[green]SQLite ready:[/green] "
        + ", ".join(f"{name}={count}" for name, count in counts.items())
    )

    try:
        api_key = settings.require_openai_api_key()
    except MissingConfigurationError as error:
        console.print(f"[red]{error}[/red]")
        raise SystemExit(2) from error

    console.print("[bold]Embedding store policies...[/bold]")
    embedder = OpenAIEmbedder(api_key, settings.embedding_model)
    count = ingest_policy_documents(
        DATA_DIR / "políticas_da_loja.pdf",
        settings.chroma_path,
        embedder,
    )
    console.print(f"[green]Policy index ready:[/green] {count} sections")


if __name__ == "__main__":
    main()
