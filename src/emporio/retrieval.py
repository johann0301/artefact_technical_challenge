"""Policy retrieval over the locally persisted Chroma collection."""

from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.errors import NotFoundError

from emporio.ingest_policies import COLLECTION_NAME, Embedder
from emporio.models import PolicyChunk


class PolicyIndexNotInitializedError(RuntimeError):
    """Raised when policy search runs before the setup command."""


class PolicyRetriever:
    def __init__(self, chroma_path: Path, embedder: Embedder) -> None:
        self.chroma_path = chroma_path
        self.embedder = embedder

    def search(self, question: str, limit: int = 3) -> list[PolicyChunk]:
        if not self.chroma_path.exists():
            raise PolicyIndexNotInitializedError(
                f"Policy index not found at {self.chroma_path}. Run `uv run emporio-setup` first."
            )
        client = chromadb.PersistentClient(path=self.chroma_path)
        try:
            collection = client.get_collection(COLLECTION_NAME)
        except NotFoundError as error:
            raise PolicyIndexNotInitializedError(
                "Policy collection is missing. Run `uv run emporio-setup` first."
            ) from error
        if collection.count() == 0:
            return []

        query_embedding = self.embedder.embed([question])[0]
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(limit, collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        documents = result["documents"][0] if result["documents"] else []
        metadatas = result["metadatas"][0] if result["metadatas"] else []
        distances = result["distances"][0] if result["distances"] else []
        return [
            PolicyChunk(
                section=str(metadata["section"]),
                title=str(metadata["title"]),
                content=document,
                source=str(metadata["source"]),
                pages=str(metadata["pages"]),
                distance=distance,
            )
            for document, metadata, distance in zip(documents, metadatas, distances, strict=True)
        ]
