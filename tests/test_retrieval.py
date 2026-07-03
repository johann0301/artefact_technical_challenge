from __future__ import annotations

from pathlib import Path

from emporio.config import DATA_DIR
from emporio.ingest_policies import (
    extract_policy_documents,
    ingest_policy_documents,
)
from emporio.normalization import normalize_search
from emporio.retrieval import PolicyRetriever


class KeywordEmbedder:
    vocabulary = ("endereco", "horario", "pagamento", "devolucao", "garantia", "privacidade")

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            normalized = normalize_search(text)
            vectors.append([float(term in normalized) for term in self.vocabulary])
        return vectors


def test_extract_policy_documents_preserves_sections_and_metadata() -> None:
    documents = extract_policy_documents(DATA_DIR / "políticas_da_loja.pdf")

    assert 20 <= len(documents) <= 28
    by_section = {document.section: document for document in documents}
    assert "Rua 14 de Maio" in by_section["1.2"].content
    assert "7 (sete) dias" in by_section["4.1"].content
    assert by_section["4.1"].pages == "4"
    assert all("Página " not in document.content for document in documents)


def test_ingest_and_search_policies_without_external_api(tmp_path: Path) -> None:
    embedder = KeywordEmbedder()
    chroma_path = tmp_path / "chroma"
    pdf_path = DATA_DIR / "políticas_da_loja.pdf"

    first_count = ingest_policy_documents(pdf_path, chroma_path, embedder)
    second_count = ingest_policy_documents(pdf_path, chroma_path, embedder)
    results = PolicyRetriever(chroma_path, embedder).search("Qual é o endereço?", limit=2)

    assert first_count == second_count
    assert results[0].section == "1.2"
    assert "Rua 14 de Maio" in results[0].content
