"""Extract policy sections from the supplied PDF and persist their embeddings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import chromadb
from openai import OpenAI
from pypdf import PdfReader

COLLECTION_NAME = "store_policies"

POLICY_HEADINGS = [
    ("1", "Sobre a Empório da Música"),
    ("1.1", "Missão"),
    ("1.2", "Dados da Empresa"),
    ("2", "Horário de Funcionamento"),
    ("3", "Formas de Pagamento"),
    ("3.1", "Regras de Parcelamento"),
    ("4", "Política de Trocas e Devoluções"),
    ("4.1", "Direito de Arrependimento (Compras Online)"),
    ("4.2", "Trocas por Defeito"),
    ("4.3", "Trocas por Preferência"),
    ("4.4", "Itens Não Elegíveis para Troca"),
    ("5", "Política de Frete e Entregas"),
    ("5.1", "Entregas na Região Metropolitana de Campo Grande"),
    ("5.2", "Entregas para Outras Cidades"),
    ("5.3", "Código de Rastreamento"),
    ("6", "Promoções e Descontos"),
    ("6.1", "Tipos de Promoção"),
    ("6.2", "Regras de Promoções"),
    ("7", "Atendimento via WhatsApp"),
    ("7.1", "Diretrizes de Atendimento"),
    ("7.2", "Fluxo de Atendimento Padrão"),
    ("7.3", "Situações Especiais"),
    ("8", "Garantia"),
    ("8.1", "Garantia Legal"),
    ("8.2", "Garantia do Fabricante"),
    ("8.3", "O que Não Cobre a Garantia"),
    ("9", "Privacidade e Proteção de Dados"),
    ("10", "Disposições Finais"),
]


@dataclass(frozen=True)
class PolicyDocument:
    id: str
    section: str
    title: str
    content: str
    source: str
    pages: str

    @property
    def embedding_text(self) -> str:
        return f"Seção {self.section} — {self.title}\n{self.content}"


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding per input text."""


class OpenAIEmbedder:
    """Thin OpenAI embeddings adapter used by setup and retrieval."""

    def __init__(self, api_key: str, model: str) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]


def _clean_page_text(text: str, page_number: int) -> str:
    text = re.sub(
        r"Empório\s+da\s+Música\s+Manual\s+de\s+Políticas\s+e\s+Procedimentos",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(rf"Página\s+{page_number}\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(
        r"Empório\s+da\s+Música\s+—\s+Sua\s+música\s+começa\s+aqui\.\s+"
        r"Última\s+atualização:\s+Junho\s+de\s+2025\s+—\s+Versão\s+2\.1",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    return " ".join(text.split())


def extract_policy_documents(pdf_path: Path) -> list[PolicyDocument]:
    """Extract deterministic semantic chunks using the manual's known section structure."""

    if not pdf_path.exists():
        raise FileNotFoundError(f"Policy PDF not found: {pdf_path}")

    reader = PdfReader(pdf_path)
    page_texts = [
        _clean_page_text(page.extract_text() or "", page_number)
        for page_number, page in enumerate(reader.pages, start=1)
    ]

    combined_parts: list[str] = []
    page_spans: list[tuple[int, int, int]] = []
    cursor = 0
    for page_number, text in enumerate(page_texts, start=1):
        if combined_parts:
            combined_parts.append(" ")
            cursor += 1
        start = cursor
        combined_parts.append(text)
        cursor += len(text)
        page_spans.append((start, cursor, page_number))
    full_text = "".join(combined_parts)

    heading_positions: list[tuple[int, str, str, str]] = []
    search_from = 0
    for section, title in POLICY_HEADINGS:
        label = f"{section}. {title}" if "." not in section else f"{section} {title}"
        position = full_text.find(label, search_from)
        if position < 0:
            raise ValueError(f"Expected policy heading not found: {label}")
        heading_positions.append((position, section, title, label))
        search_from = position + len(label)

    documents: list[PolicyDocument] = []
    for index, (position, section, title, label) in enumerate(heading_positions):
        content_start = position + len(label)
        content_end = (
            heading_positions[index + 1][0]
            if index + 1 < len(heading_positions)
            else len(full_text)
        )
        content = full_text[content_start:content_end].strip(" .")
        if len(content) < 20:
            continue
        covered_pages = [
            page_number
            for start, end, page_number in page_spans
            if content_start < end and content_end > start
        ]
        pages = (
            str(covered_pages[0])
            if len(covered_pages) == 1
            else f"{covered_pages[0]}-{covered_pages[-1]}"
        )
        documents.append(
            PolicyDocument(
                id=f"policy-{section.replace('.', '-')}",
                section=section,
                title=title,
                content=content,
                source=pdf_path.name,
                pages=pages,
            )
        )
    return documents


def ingest_policy_documents(
    pdf_path: Path,
    chroma_path: Path,
    embedder: Embedder,
) -> int:
    """Upsert all extracted policy chunks and remove stale IDs from prior runs."""

    documents = extract_policy_documents(pdf_path)
    embeddings = embedder.embed([document.embedding_text for document in documents])
    if len(embeddings) != len(documents):
        raise ValueError("Embedding provider returned a different number of vectors than inputs.")

    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_or_create_collection(COLLECTION_NAME)
    new_ids = [document.id for document in documents]
    existing_ids = collection.get(include=[])["ids"]
    stale_ids = [document_id for document_id in existing_ids if document_id not in new_ids]
    if stale_ids:
        collection.delete(ids=stale_ids)
    collection.upsert(
        ids=new_ids,
        embeddings=embeddings,
        documents=[document.content for document in documents],
        metadatas=[
            {
                "section": document.section,
                "title": document.title,
                "source": document.source,
                "pages": document.pages,
            }
            for document in documents
        ],
    )
    return len(documents)
