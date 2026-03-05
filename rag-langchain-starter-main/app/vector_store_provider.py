"""
Vector Store Provider Module - A wrapper for different vector store backends.

This module provides a unified interface for using different vector store providers
(FAISS or Chroma) with LangChain.

To switch between providers:
1. Set VECTOR_STORE_PROVIDER="faiss" or "chroma" in your .env file
2. The persist directory will be auto-suffixed (e.g., ./index/faiss or ./index/chroma)

Both providers support:
- Creating a vector store from documents
- Saving/persisting to disk
- Loading from disk
- Converting to a retriever
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings


class BaseVectorStoreProvider(ABC):
    """Abstract base class for vector store providers."""

    def __init__(self, persist_dir: str, embeddings: HuggingFaceEmbeddings):
        self.persist_dir = persist_dir
        self.embeddings = embeddings

    @abstractmethod
    def from_documents(self, documents: List[Document]):
        """Create a vector store from documents and persist it."""
        pass

    @abstractmethod
    def load(self):
        """Load the vector store from disk."""
        pass

    @abstractmethod
    def as_retriever(self, k: int = 4):
        """Return a retriever from the loaded vector store."""
        pass


class FAISSProvider(BaseVectorStoreProvider):
    """FAISS Vector Store Provider."""

    def from_documents(self, documents: List[Document]):
        """Create a FAISS index from documents and save to disk."""
        from langchain_community.vectorstores import FAISS
        vs = FAISS.from_documents(documents, embedding=self.embeddings)
        vs.save_local(self.persist_dir)
        return vs

    def load(self):
        """Load FAISS index from disk."""
        from langchain_community.vectorstores import FAISS
        return FAISS.load_local(
            self.persist_dir, self.embeddings,
            allow_dangerous_deserialization=True
        )

    def as_retriever(self, k: int = 4):
        """Return a retriever from the FAISS index."""
        vs = self.load()
        return vs.as_retriever(search_kwargs={"k": k})


class ChromaProvider(BaseVectorStoreProvider):
    """Chroma Vector Store Provider."""

    def from_documents(self, documents: List[Document]):
        """Create a Chroma DB from documents and persist to disk."""
        from langchain_community.vectorstores import Chroma
        vs = Chroma.from_documents(
            documents, embedding=self.embeddings,
            persist_directory=self.persist_dir
        )
        vs.persist()
        return vs

    def load(self):
        """Load Chroma DB from disk."""
        from langchain_community.vectorstores import Chroma
        return Chroma(
            persist_directory=self.persist_dir,
            embedding_function=self.embeddings
        )

    def as_retriever(self, k: int = 4):
        """Return a retriever from the Chroma DB."""
        vs = self.load()
        return vs.as_retriever(search_kwargs={"k": k})


class VectorStoreFactory:
    """Factory class for creating vector store provider instances."""

    PROVIDERS = {
        "faiss": FAISSProvider,
        "chroma": ChromaProvider,
    }

    @classmethod
    def create(cls, provider: str, persist_dir: str,
               embeddings: HuggingFaceEmbeddings) -> BaseVectorStoreProvider:
        """
        Create a vector store provider instance.

        Args:
            provider: Provider name ("faiss" or "chroma")
            persist_dir: Directory to persist the vector store
            embeddings: HuggingFace embeddings instance

        Returns:
            A vector store provider instance
        """
        provider_lower = provider.lower()
        if provider_lower not in cls.PROVIDERS:
            available = ", ".join(cls.PROVIDERS.keys())
            raise ValueError(
                f"Unsupported vector store provider: '{provider}'. "
                f"Available providers: {available}"
            )
        return cls.PROVIDERS[provider_lower](persist_dir, embeddings)

    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """Register a new vector store provider at runtime."""
        cls.PROVIDERS[name.lower()] = provider_class


def get_vector_store_provider(
    provider: Optional[str] = None,
    persist_dir: Optional[str] = None,
    embed_model: Optional[str] = None,
    cache_folder: Optional[str] = None,
) -> BaseVectorStoreProvider:
    """
    Get a vector store provider based on environment variables or parameters.

    Reads from config by default:
    - VECTOR_STORE_PROVIDER: "faiss" or "chroma" (default: "faiss")
    - PERSIST_DIR: Directory to persist the index
    - EMBED_MODEL: Embedding model name

    Args:
        provider: Override VECTOR_STORE_PROVIDER env var
        persist_dir: Override PERSIST_DIR env var
        embed_model: Override EMBED_MODEL env var
        cache_folder: HuggingFace cache folder path
    """
    from config import VECTOR_STORE_PROVIDER, PERSIST_DIR, EMBED_MODEL

    actual_provider = provider or VECTOR_STORE_PROVIDER
    actual_persist_dir = persist_dir or PERSIST_DIR
    actual_embed_model = embed_model or EMBED_MODEL

    kwargs = {}
    if cache_folder:
        kwargs["cache_folder"] = cache_folder

    embeddings = HuggingFaceEmbeddings(model_name=actual_embed_model, **kwargs)
    return VectorStoreFactory.create(actual_provider, actual_persist_dir, embeddings)


__all__ = [
    'BaseVectorStoreProvider',
    'FAISSProvider',
    'ChromaProvider',
    'VectorStoreFactory',
    'get_vector_store_provider',
]