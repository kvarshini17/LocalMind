"""
pdf_chat.py
===========
Retrieval-Augmented Generation over uploaded PDFs.

Pipeline:
    upload -> extract text (PyPDF) -> split into chunks (LangChain) ->
    embed (Sentence Transformers) -> store (ChromaDB) -> retrieve on query ->
    build context -> send to Ollama -> return answer + sources.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

# Must stay above the langchain imports: it turns on Hugging Face offline mode.
from utils.constants import (
    CHUNK_SIZE, CHUNK_OVERLAP, EMBEDDING_MODEL, VECTORSTORE_DIR,
    UPLOADS_DIR, TOP_K_RESULTS, NO_ANSWER_MESSAGE, MAX_PDF_SIZE_MB,
)

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from core.ollama_client import OllamaClient, OllamaConnectionError


class PDFProcessingError(Exception):
    """Raised for any failure while ingesting or reading a PDF."""


@dataclass
class RetrievedChunk:
    """A single retrieved chunk of context, with its source metadata."""

    content: str
    document_name: str
    page_number: int


class PDFChatEngine:
    """Manages the vector store and RAG workflow for uploaded PDFs."""

    def __init__(self) -> None:
        self._embeddings = None  # lazy-loaded (expensive to initialize)
        self._vectorstore: Chroma | None = None

    # ------------------------------------------------------------------
    # Lazy-loaded embedding model (avoids slow app startup)
    # ------------------------------------------------------------------
    @property
    def embeddings(self) -> HuggingFaceEmbeddings:
        if self._embeddings is None:
            try:
                self._embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
            except Exception as exc:
                raise PDFProcessingError(
                    f"The embedding model '{EMBEDDING_MODEL}' is not installed on "
                    "this computer, so PDFs can't be processed. Connect to the "
                    "internet once and run: python download_model.py"
                ) from exc
        return self._embeddings

    @property
    def vectorstore(self) -> Chroma:
        if self._vectorstore is None:
            self._vectorstore = Chroma(
                collection_name="pdf_documents",
                embedding_function=self.embeddings,
                persist_directory=str(VECTORSTORE_DIR),
            )
        return self._vectorstore

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    def validate_pdf(self, file_path: Path) -> None:
        """Validate file size and that the PDF isn't corrupted before ingesting."""
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_PDF_SIZE_MB:
            raise PDFProcessingError(
                f"'{file_path.name}' is {size_mb:.1f} MB, which exceeds the "
                f"{MAX_PDF_SIZE_MB} MB limit."
            )
        try:
            reader = PdfReader(str(file_path))
            if len(reader.pages) == 0:
                raise PDFProcessingError(f"'{file_path.name}' has no readable pages.")
        except PdfReadError as exc:
            raise PDFProcessingError(
                f"'{file_path.name}' appears to be corrupted or is not a valid PDF."
            ) from exc

    def ingest_pdf(self, file_path: Path) -> int:
        """
        Extract text from a PDF, chunk it, embed it, and store it in the
        vector store.

        Returns:
            The number of chunks stored.

        Raises:
            PDFProcessingError: on any extraction/validation failure.
        """
        self.validate_pdf(file_path)
        vectorstore = self.vectorstore  # a missing model should report as itself

        try:
            reader = PdfReader(str(file_path))
            pages_text = [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
        except Exception as exc:  # noqa: BLE001 - surface any pypdf failure cleanly
            raise PDFProcessingError(
                f"Failed to extract text from '{file_path.name}': {exc}"
            ) from exc

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )

        documents: list[Document] = []
        for page_num, text in pages_text:
            if not text.strip():
                continue
            for chunk in splitter.split_text(text):
                documents.append(
                    Document(
                        page_content=chunk,
                        metadata={
                            "document_name": file_path.name,
                            "page_number": page_num,
                            "chunk_hash": hashlib.md5(chunk.encode()).hexdigest(),
                        },
                    )
                )

        if not documents:
            raise PDFProcessingError(
                f"'{file_path.name}' contains no extractable text "
                "(it may be a scanned/image-only PDF)."
            )

        # Avoid duplicate embeddings: skip chunks we've already stored.
        existing = self._existing_chunk_hashes(file_path.name)
        new_docs = [
            d for d in documents if d.metadata["chunk_hash"] not in existing
        ]
        if new_docs:
            try:
                vectorstore.add_documents(new_docs)
                vectorstore.persist()
            except Exception as exc:
                raise PDFProcessingError(
                    f"Failed to store extracted text in the database: {exc}"
                ) from exc

        return len(new_docs)

    def _existing_chunk_hashes(self, document_name: str) -> set[str]:
        """Return the chunk hashes already stored for a document, to dedupe re-uploads."""
        try:
            data = self.vectorstore.get(where={"document_name": document_name}, include=["metadatas"])
            return {m.get("chunk_hash", "") for m in data.get("metadatas", [])}
        except Exception:  # noqa: BLE001 - empty/uninitialized store
            return set()

    def indexed_documents(self) -> set[str]:
        """Names of all documents that have chunks in the vector store."""
        data = self.vectorstore.get(include=["metadatas"])
        return {m.get("document_name", "") for m in data.get("metadatas", [])}

    def sync_with_folder(self, folder: Path) -> None:
        """Make the vector store match the PDFs in `folder`: drop chunks of
        files that were deleted, and index files that never got indexed."""
        on_disk = {p.name: p for p in folder.glob("*.pdf")}
        indexed = self.indexed_documents()
        for name in indexed - on_disk.keys():
            self.remove_document(name)
        for name in on_disk.keys() - indexed:
            try:
                self.ingest_pdf(on_disk[name])
            except PDFProcessingError as exc:
                print(f"Could not index {name}: {exc}")

    def remove_document(self, document_name: str) -> None:
        """Delete all chunks belonging to a given document from the store."""
        vectorstore = self.vectorstore
        try:
            vectorstore.delete(where={"document_name": document_name})
            vectorstore.persist()
        except Exception as exc:  # noqa: BLE001
            raise PDFProcessingError(
                f"Could not remove '{document_name}' from the vector store: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Retrieval + generation
    # ------------------------------------------------------------------
    def retrieve(
        self, query: str, k: int = TOP_K_RESULTS, document_names: list[str] | None = None
    ) -> list[RetrievedChunk]:
        """Retrieve the top-k most relevant chunks for a query, optionally
        only from the named documents."""
        search_filter = {"document_name": {"$in": document_names}} if document_names else None
        vectorstore = self.vectorstore
        try:
            results = vectorstore.similarity_search(query, k=k, filter=search_filter)
        except Exception as exc:  # noqa: BLE001 - e.g. empty collection
            print(f"Retrieval error: {exc}")
            return []
        return [self._to_chunk(doc.page_content, doc.metadata) for doc in results]

    def _opening_chunks(self, document_name: str, count: int = 2) -> list[RetrievedChunk]:
        """Return a document's first chunks. Requests like "summarize this"
        share no words with the text, so similarity search alone can miss them."""
        try:
            data = self.vectorstore.get(where={"document_name": document_name}, limit=count)
        except Exception as exc:  # noqa: BLE001
            print(f"Retrieval error: {exc}")
            return []
        return [self._to_chunk(c, m) for c, m in zip(data["documents"], data["metadatas"])]

    @staticmethod
    def _to_chunk(content: str, metadata: dict) -> RetrievedChunk:
        return RetrievedChunk(
            content=content,
            document_name=metadata.get("document_name", "unknown"),
            page_number=metadata.get("page_number", 0),
        )

    def answer_question(
        self,
        query: str,
        model: str,
        client: OllamaClient,
        temperature: float = 0.3,
        top_p: float = 0.9,
        max_tokens: int = 1024,
        history_messages: list[dict[str, str]] | None = None,
        document_names: list[str] | None = None,
    ) -> tuple[Generator[str, None, None], list[RetrievedChunk]]:
        """
        Search the vectorstore for `query`, build a RAG prompt (including conversation history if provided),
        and yield the assistant's streamed response. `document_names` limits the
        search to those documents; otherwise every uploaded PDF is searched.
        """
        chunks = self.retrieve(query, document_names=document_names)
        for name in document_names or []:
            chunks += [c for c in self._opening_chunks(name) if c not in chunks]
        if not chunks:
            def _no_answer() -> Generator[str, None, None]:
                yield NO_ANSWER_MESSAGE
            return _no_answer(), []

        context = "\n\n".join(
            f"[Source: {c.document_name}, page {c.page_number}]\n{c.content}"
            for c in chunks
        )
        system_prompt = (
            "You are a helpful assistant that answers questions about the user's "
            "PDF documents using ONLY the excerpts in the Context. Requests like "
            "'summarize this', 'explain this' or 'what is this about' refer to those "
            "documents, so answer them from the excerpts. Only if the excerpts have "
            f"nothing to do with the question, respond exactly with: \"{NO_ANSWER_MESSAGE}\". "
            "Cite the document name and page number when relevant."
        )
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        if history_messages:
            messages.extend(
                {"role": m["role"], "content": m["content"]} for m in history_messages[-6:]
                if m["content"] != NO_ANSWER_MESSAGE  # an old refusal invites another
            )
        messages.append(
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
        )

        generator = client.stream_chat(
            model=model, messages=messages, temperature=temperature,
            top_p=top_p, max_tokens=max_tokens,
        )
        return generator, chunks
