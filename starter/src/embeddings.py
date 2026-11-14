"""Local dense embeddings using Sentence Transformers and BAAI/bge-m3."""
import os
from typing import Protocol

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer


DEFAULT_MODEL_NAME = "BAAI/bge-m3"
EXPECTED_BGE_M3_DIMENSIONS = 1024
DEFAULT_BATCH_SIZE = 16


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """Encode retrieval queries and documents with the same local model.

    BGE-M3 does not require a query instruction. Sentence Transformers' query
    and document entry points are used to preserve retrieval-specific behavior
    if the selected model defines any prompts or task routes.
    """

    def __init__(
        self,
        model_name: str | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        load_dotenv()
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL") or DEFAULT_MODEL_NAME
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        self.batch_size = batch_size
        self.model = SentenceTransformer(self.model_name)
        dimensions = self.model.get_embedding_dimension()
        if dimensions is None:
            raise RuntimeError(f"Could not determine embedding dimensions for {self.model_name}")
        self.dimensions = int(dimensions)
        if self.model_name == DEFAULT_MODEL_NAME and self.dimensions != EXPECTED_BGE_M3_DIMENSIONS:
            raise RuntimeError(
                f"{DEFAULT_MODEL_NAME} should produce {EXPECTED_BGE_M3_DIMENSIONS}-dimensional "
                f"vectors, got {self.dimensions}"
            )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self._validate_texts(texts)
        if not texts:
            return []
        vectors = self.model.encode_document(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vectors.astype("float32").tolist()

    def embed_query(self, question: str) -> list[float]:
        self._validate_texts([question])
        vector = self.model.encode_query(
            question,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vector.astype("float32").tolist()

    @staticmethod
    def _validate_texts(texts: list[str]) -> None:
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Embedding inputs must be non-empty strings")
