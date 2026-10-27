from __future__ import annotations

import math
import sqlite3
import struct
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol, Sequence

from langchain_core.embeddings import Embeddings
from langchain_core.tools import BaseTool
from langchain_openai import OpenAIEmbeddings

from application.db.sqlite_paths import SQLITE_DIR
from src.prompts.tool_selector_tools_prompt import TOOL_SELECTOR_DESCRIPTIONS


TOOL_SELECTOR_STATE_KEY = "tool_selector_tools"
DEFAULT_TOOL_SEARCH_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_TOOL_SEARCH_COLLECTION = "eureca_tool_search"
DEFAULT_TOOL_SEARCH_DATABASE_PATH = SQLITE_DIR / "tool_search.sqlite3"


@dataclass(frozen=True)
class ToolSearchResult:
    name: str
    score: float


@dataclass(frozen=True)
class _ToolEmbeddingDocument:
    name: str
    content: str
    content_hash: str


class ToolSearchIndex(Protocol):
    async def search(
        self,
        query: str,
        *,
        allowed_tool_names: set[str],
        k: int | None,
    ) -> list[ToolSearchResult]: ...


class SQLiteToolSearchIndex:
    """Índice vetorial persistente e exato para o pequeno catálogo de tools."""

    def __init__(
        self,
        tools: Sequence[BaseTool],
    ) -> None:
        self.tools = list(tools)
        self.embedding_model = DEFAULT_TOOL_SEARCH_EMBEDDING_MODEL
        self.collection_name = DEFAULT_TOOL_SEARCH_COLLECTION
        self.database_path = str(Path(DEFAULT_TOOL_SEARCH_DATABASE_PATH).resolve())
        self.embeddings: Embeddings = OpenAIEmbeddings(model=self.embedding_model)

        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()
        self.ensure_index()

    def ensure_index(self) -> None:
        """Cria apenas embeddings ausentes ou invalidados por alguma mudança."""
        current_documents = {
            tool.name: self._tool_document(tool) for tool in self.tools
        }
        with self._connection() as connection:
            stored_hashes = {
                row[0]: row[1]
                for row in connection.execute(
                    """
                    SELECT tool_name, content_hash
                    FROM tool_embeddings
                    WHERE collection_name = ?
                    """,
                    (self.collection_name,),
                )
            }

            stale_names = sorted(set(stored_hashes) - set(current_documents))
            if stale_names:
                placeholders = ", ".join("?" for _ in stale_names)
                connection.execute(
                    f"""
                    DELETE FROM tool_embeddings
                    WHERE collection_name = ?
                    AND tool_name IN ({placeholders})
                    """,
                    (self.collection_name, *stale_names),
                )

            changed_documents = [
                document
                for document in current_documents.values()
                if stored_hashes.get(document.name) != document.content_hash
            ]
            if not changed_documents:
                return

            vectors = self.embeddings.embed_documents(
                [document.content for document in changed_documents]
            )
            if len(vectors) != len(changed_documents):
                raise ValueError(
                    "O provedor de embeddings retornou uma quantidade inesperada "
                    "de vetores"
                )

            rows = []
            for document, vector in zip(
                changed_documents,
                vectors,
                strict=True,
            ):
                self._validate_vector(vector)
                rows.append(
                    (
                        self.collection_name,
                        document.name,
                        document.content,
                        document.content_hash,
                        self.embedding_model,
                        len(vector),
                        self._serialize_vector(vector),
                    )
                )
            connection.executemany(
                """
                INSERT INTO tool_embeddings (
                    collection_name,
                    tool_name,
                    content,
                    content_hash,
                    embedding_model,
                    dimensions,
                    embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(collection_name, tool_name) DO UPDATE SET
                    content = excluded.content,
                    content_hash = excluded.content_hash,
                    embedding_model = excluded.embedding_model,
                    dimensions = excluded.dimensions,
                    embedding = excluded.embedding
                """,
                rows,
            )

    async def search(
        self,
        query: str,
        *,
        allowed_tool_names: set[str],
        k: int | None,
    ) -> list[ToolSearchResult]:
        normalized_query = query.strip()
        if not normalized_query or not allowed_tool_names:
            return []

        result_limit = (
            len(allowed_tool_names)
            if k is None
            else min(
                k,
                len(allowed_tool_names),
            )
        )
        if result_limit < 1:
            return []

        query_vector = await self.embeddings.aembed_query(normalized_query)
        self._validate_vector(query_vector)
        stored_vectors = self._load_vectors(allowed_tool_names)

        results = [
            ToolSearchResult(
                name=name,
                score=max(
                    0.0,
                    min(1.0, self._cosine_similarity(query_vector, vector)),
                ),
            )
            for name, vector in stored_vectors
        ]
        results.sort(key=lambda result: result.score, reverse=True)
        return results[:result_limit]

    def _initialize_database(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_embeddings (
                    collection_name TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    dimensions INTEGER NOT NULL,
                    embedding BLOB NOT NULL,
                    PRIMARY KEY (collection_name, tool_name)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _load_vectors(
        self,
        allowed_tool_names: set[str],
    ) -> list[tuple[str, list[float]]]:
        names = sorted(allowed_tool_names)
        placeholders = ", ".join("?" for _ in names)
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT tool_name, dimensions, embedding
                FROM tool_embeddings
                WHERE collection_name = ?
                AND tool_name IN ({placeholders})
                """,
                (self.collection_name, *names),
            ).fetchall()
        return [
            (name, self._deserialize_vector(blob, dimensions))
            for name, dimensions, blob in rows
        ]

    def _tool_document(self, tool: BaseTool) -> _ToolEmbeddingDocument:
        description = TOOL_SELECTOR_DESCRIPTIONS.get(
            tool.name,
            tool.description.strip(),
        )
        content = f"Nome da ferramenta: {tool.name}\nDescrição: {description}"
        content_hash = sha256(
            f"{self.embedding_model}\n{content}".encode("utf-8")
        ).hexdigest()
        return _ToolEmbeddingDocument(
            name=tool.name,
            content=content,
            content_hash=content_hash,
        )

    @staticmethod
    def _validate_vector(vector: Sequence[float]) -> None:
        if not vector or not all(math.isfinite(value) for value in vector):
            raise ValueError("O provedor retornou um embedding inválido")

    @staticmethod
    def _serialize_vector(vector: Sequence[float]) -> bytes:
        return struct.pack(f"<{len(vector)}f", *vector)

    @staticmethod
    def _deserialize_vector(blob: bytes, dimensions: int) -> list[float]:
        expected_size = dimensions * 4
        if len(blob) != expected_size:
            raise ValueError("Embedding persistido possui tamanho inválido")
        return list(struct.unpack(f"<{dimensions}f", blob))

    @staticmethod
    def _cosine_similarity(
        left: Sequence[float],
        right: Sequence[float],
    ) -> float:
        if len(left) != len(right):
            raise ValueError("Embeddings possuem dimensões incompatíveis")
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        dot_product = sum(a * b for a, b in zip(left, right, strict=True))
        return dot_product / (left_norm * right_norm)


def get_selected_tool_names(state: Any) -> list[str]:
    if isinstance(state, dict):
        value = state.get(TOOL_SELECTOR_STATE_KEY, [])
    else:
        value = getattr(state, TOOL_SELECTOR_STATE_KEY, [])
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(name for name in value if isinstance(name, str)))
