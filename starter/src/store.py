"""Persistent exact cosine search on PostgreSQL + pgvector."""
import json
from typing import Any

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from .models import Chunk

_FILTER_FIELDS = {"section", "document_type", "language", "category", "year"}


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if dimensions < 1:
            raise ValueError("dimensions must be positive")
        self.database_url = database_url
        self.dimensions = dimensions

    def create_schema(self) -> None:
        with psycopg.connect(self.database_url) as conn:
            register_vector(conn)
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS corpus_chunks (
                strategy text NOT NULL, chunk_id text NOT NULL, document_id text NOT NULL,
                source text NOT NULL, page integer NOT NULL, content text NOT NULL,
                metadata jsonb NOT NULL, embedding vector({self.dimensions}) NOT NULL,
                PRIMARY KEY(strategy, chunk_id))""")
            conn.execute("CREATE INDEX IF NOT EXISTS corpus_chunks_meta_idx ON corpus_chunks USING gin(metadata)")

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have equal lengths")
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise ValueError(f"Expected {self.dimensions} dimensions, got {len(vector)}")
        rows = [(strategy, c.chunk_id, c.document_id, c.source, c.page, c.text,
                 json.dumps(c.metadata), Vector(v)) for c, v in zip(chunks, vectors)]
        with psycopg.connect(self.database_url) as conn:
            register_vector(conn)
            # Replace one strategy atomically, so re-ingest cannot retain stale chunks.
            with conn.transaction():
                conn.execute("DELETE FROM corpus_chunks WHERE strategy = %s", (strategy,))
                if rows:
                    with conn.cursor() as cursor:
                        cursor.executemany("""INSERT INTO corpus_chunks
                            (strategy,chunk_id,document_id,source,page,content,metadata,embedding)
                            VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""", rows)

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if len(query_vector) != self.dimensions:
            raise ValueError(f"Expected {self.dimensions} query dimensions")
        if top_k < 1:
            raise ValueError("top_k must be positive")
        clauses = ["strategy = %s"]
        filter_params: list[Any] = []
        for field, value in (filters or {}).items():
            if field not in _FILTER_FIELDS:
                raise ValueError(f"Unsupported metadata filter: {field}")
            clauses.append("metadata ->> %s = %s")
            filter_params.extend([field, str(value)])
        sql = f"""SELECT chunk_id, document_id, source, page, content, metadata,
            1 - (embedding <=> %s) AS score
            FROM corpus_chunks WHERE {' AND '.join(clauses)}
            ORDER BY embedding <=> %s LIMIT %s"""
        vector = Vector(query_vector)
        params = [vector, strategy, *filter_params, vector, top_k]
        with psycopg.connect(self.database_url) as conn:
            register_vector(conn)
            rows = conn.execute(sql, params).fetchall()
        return [{"chunk_id": r[0], "document_id": r[1], "source": r[2],
                 "page": r[3], "text": r[4], "metadata": r[5], "score": float(r[6])}
                for r in rows]

    def is_current(self, strategy: str, chunks: list[Chunk]) -> bool:
        """Return whether stored IDs, text and metadata match this input exactly."""
        with psycopg.connect(self.database_url) as conn:
            rows = conn.execute(
                "SELECT chunk_id, content, metadata FROM corpus_chunks WHERE strategy = %s",
                (strategy,),
            ).fetchall()
        if len(rows) != len(chunks):
            return False
        stored = {row[0]: (row[1], row[2]) for row in rows}
        return all(stored.get(chunk.chunk_id) == (chunk.text, chunk.metadata) for chunk in chunks)
