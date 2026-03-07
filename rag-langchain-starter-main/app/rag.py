"""
RAG → retrieve (based on the question) → prompt LLM → answer with citations.
RAG (Retrieval-Augmented Generation):
1. Retrieve the most relevant chunks from the vector store.
2. Feed them into the LLM with a prompt template.
3. Get a grounded answer + citations.
"""

import time
from typing import List, Dict, Optional
from pathlib import Path
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from config import TOP_K

# Import the LLM wrapper module
from llm_provider import get_llm as get_llm_provider
# Import the vector store wrapper module
from vector_store_provider import get_vector_store_provider, VectorStoreFactory
# Import logger
from logger import logger, log_time, Timer


# ---- Prompt templates ----
ANSWER_PROMPT = PromptTemplate.from_template(
    """You are a precise assistant. Answer the user's question using ONLY the context below.
If the answer is not in the context, say you don't know.

Return:
- A short answer (3-6 sentences).
- Numbered inline citations like [1], [2].
- A "Sources" list mapping numbers to file names and pages.

Previous conversation:
{chat_history}

Question: {question}

Context:
{context}
"""
)


class RAGPipeline:
    """
    RAG Pipeline class that initializes LLM and vector store provider once.
    Retriever is created at runtime with dynamic TOP_K.
    
    Usage:
        # Initialize once at application startup
        rag = RAGPipeline()
        
        # Call answer() with different k values
        result = rag.answer("What is the document about?", k=4)
        result = rag.answer("Another question?", k=6)
    """
    
    def __init__(self, cache_folder: str = "./hugging_face/cache/"):
        """
        Initialize the RAG pipeline.
        
        Args:
            cache_folder: HuggingFace cache folder for embeddings
        """
        self._cache_folder = cache_folder
        self._llm = None
        self._vs_provider = None
        self._embeddings = None
        self._initialized = False
        self._chat_history: List[Dict] = []
    
    @log_time("Initialize RAG Pipeline")
    def initialize(self):
        """Load LLM and embeddings. Called automatically on first use or manually."""
        if self._initialized:
            return
        
        # Load LLM provider
        with Timer("Load LLM"):
            llm_provider = get_llm_provider()
            self._llm = llm_provider.get_llm()
        
        # Load embeddings (shared between ingest and retrieve)
        from config import EMBED_MODEL
        with Timer("Load Embeddings"):
            kwargs = {}
            if self._cache_folder:
                kwargs["cache_folder"] = self._cache_folder
            self._embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL, **kwargs)
        
        self._initialized = True
    
    def set_vector_store(self, provider: str, persist_dir: str):
        """
        Set the vector store provider.
        
        Args:
            provider: "faiss" or "chroma"
            persist_dir: Directory for the vector store
        """
        if not self._initialized:
            self.initialize()
        
        self._vs_provider = VectorStoreFactory.create(
            provider, persist_dir, self._embeddings
        )
    
    @log_time("Load Vector Store")
    def load_vector_store(self):
        """Load the vector store from disk."""
        if self._vs_provider is None:
            # Load from config defaults
            self._vs_provider = get_vector_store_provider(cache_folder=self._cache_folder)
        return self._vs_provider.load()
    
    def get_retriever(self, k: int = TOP_K):
        """
        Get a retriever with the specified k value.
        Created at runtime for dynamic TOP_K.
        
        Args:
            k: Number of documents to retrieve
            
        Returns:
            A retriever instance
        """
        if self._vs_provider is None:
            self._vs_provider = get_vector_store_provider(cache_folder=self._cache_folder)
        return self._vs_provider.as_retriever(k=k)
    
    def _format_context(self, docs: List[Document]) -> str:
        """Format docs as numbered blocks so the LLM can cite them."""
        lines = []
        for i, d in enumerate(docs, start=1):
            meta = d.metadata or {}
            src = Path(meta.get("source", "unknown")).name if "source" in meta else "unknown"
            page = meta.get("page", None)
            header = f"[{i}] {src}" + (f", page {page}" if page is not None else "")
            lines.append(f"{header}\n{d.page_content}\n")
        return "\n".join(lines)
    
    def _format_chat_history(self) -> str:
        """Format chat history for the prompt."""
        if not self._chat_history:
            return "No previous conversation."
        
        lines = []
        for msg in self._chat_history:
            role = msg["role"].capitalize()
            content = msg["content"]
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
    
    def clear_history(self):
        """Clear the conversation history."""
        self._chat_history = []
        logger.info("Chat history cleared")
    
    def answer(self, question: str, k: int = TOP_K, use_history: bool = False) -> Dict:
        """
        Answer a question using RAG pipeline.
        
        Args:
            question: User's question
            k: Number of documents to retrieve (runtime setting)
            use_history: Whether to include conversation history
            
        Returns:
            Dict with 'answer' (str) and 'citations' (list)
        """
        logger.info(f"Processing question: {question[:50]}...")
        
        # Ensure initialized
        if not self._initialized:
            self.initialize()
        
        # Get retriever with runtime k value
        retriever = self.get_retriever(k=k)
        
        # Retrieve relevant documents
        with Timer(f"Retrieve {k} documents"):
            docs = retriever.invoke(question)
        logger.info(f"Retrieved {len(docs)} documents")
        
        # Format context
        context = self._format_context(docs)
        
        # Generate prompt (with or without history)
        if use_history and self._chat_history:
            chat_history = self._format_chat_history()
            prompt = ANSWER_PROMPT.format(
                question=question, 
                context=context,
                chat_history=chat_history
            )
        else:
            prompt = ANSWER_PROMPT.format(question=question, context=context, chat_history="None")
        
        # Generate answer
        with Timer("LLM generate answer"):
            resp = self._llm.invoke(prompt)
        
        # Add to history
        self._chat_history.append({"role": "user", "content": question})
        self._chat_history.append({"role": "assistant", "content": resp.content})
        
        # Build citation list for UI
        cites = []
        for i, d in enumerate(docs, start=1):
            meta = d.metadata or {}
            cites.append({
                "n": i,
                "source": meta.get("source", "unknown"),
                "page": meta.get("page", None),
                "snippet": d.page_content[:200].replace("\n", " ") + ("..." if len(d.page_content) > 200 else "")
            })
        
        logger.info("Answer generated successfully")
        return {"answer": resp.content, "citations": cites}
    
    @property
    def is_initialized(self) -> bool:
        """Check if the pipeline is initialized."""
        return self._initialized
    
    @property
    def chat_history(self) -> List[Dict]:
        """Get the conversation history."""
        return self._chat_history.copy()


class IngestPipeline:
    """
    Pipeline for ingesting documents into a vector store.
    
    Usage:
        ingest = IngestPipeline()
        ingest.set_vector_store("faiss", "./index/faiss")
        ingest.ingest_documents(documents, chunk_size=800, chunk_overlap=120)
    """
    
    def __init__(self, cache_folder: str = "./hugging_face/cache/"):
        """
        Initialize the ingest pipeline.
        
        Args:
            cache_folder: HuggingFace cache folder for embeddings
        """
        self._cache_folder = cache_folder
        self._embeddings = None
        self._vs_provider = None
    
    @log_time("Initialize Ingest Pipeline")
    def initialize(self):
        """Initialize embeddings."""
        if self._embeddings is not None:
            return
        
        from config import EMBED_MODEL
        kwargs = {}
        if self._cache_folder:
            kwargs["cache_folder"] = self._cache_folder
        self._embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL, **kwargs)
    
    def set_vector_store(self, provider: str, persist_dir: str):
        """
        Set the vector store provider.
        
        Args:
            provider: "faiss" or "chroma"
            persist_dir: Directory for the vector store
        """
        self.initialize()
        self._vs_provider = VectorStoreFactory.create(
            provider, persist_dir, self._embeddings
        )
    
    @log_time("Ingest Documents")
    def ingest_documents(self, documents: List[Document], 
                         chunk_size: int = 800, 
                         chunk_overlap: int = 120) -> int:
        """
        Ingest documents into the vector store.
        
        Args:
            documents: List of Document objects
            chunk_size: Size of each chunk
            chunk_overlap: Overlap between chunks
            
        Returns:
            Number of chunks created
        """
        if self._vs_provider is None:
            raise ValueError("Vector store not set. Call set_vector_store() first.")
        
        # Split documents into chunks
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        with Timer("Split documents into chunks"):
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size, 
                chunk_overlap=chunk_overlap
            )
            chunks = splitter.split_documents(documents)
        logger.info(f"Created {len(chunks)} chunks from {len(documents)} documents")
        
        # Create vector store
        with Timer("Create vector store"):
            self._vs_provider.from_documents(chunks)
        
        return len(chunks)


# ---- Global instance for backward compatibility ----
_rag_instance: Optional[RAGPipeline] = None


def get_rag_pipeline(cache_folder: str = "./hugging_face/cache/") -> RAGPipeline:
    """
    Get or create a global RAG pipeline instance.
    
    This ensures LLM and embeddings are only loaded once.
    
    Args:
        cache_folder: HuggingFace cache folder
        
    Returns:
        RAGPipeline instance
    """
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGPipeline(cache_folder=cache_folder)
        _rag_instance.initialize()
    return _rag_instance


def answer(question: str, k: int = TOP_K, use_history: bool = False) -> Dict:
    """
    Answer a question using the global RAG pipeline.
    
    This is a convenience function for backward compatibility.
    For better control, use get_rag_pipeline() instead.
    
    Args:
        question: User's question
        k: Number of documents to retrieve
        use_history: Whether to include conversation history
        
    Returns:
        Dict with 'answer' (str) and 'citations' (list)
    """
    rag = get_rag_pipeline()
    return rag.answer(question, k=k, use_history=use_history)