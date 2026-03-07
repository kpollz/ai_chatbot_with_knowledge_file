"""
Ingest pipeline:
1. Load documents from data/raw (PDF, Markdown, Text, CSV, Excel).
2. Split into smaller overlapping chunks for embedding.
3. Create embeddings and store them in a vector DB (FAISS or Chroma).
"""

from pathlib import Path
from langchain_community.document_loaders import (
    DirectoryLoader, 
    TextLoader, 
    PyPDFLoader,
    CSVLoader,
    UnstructuredExcelLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from config import DATA_DIR, PERSIST_DIR, EMBED_MODEL
from vector_store_provider import get_vector_store_provider
from logger import logger, log_time, Timer


@log_time("Load Documents")
def load_docs(data_dir: str):
    """Load PDF, Markdown, Text, CSV, and Excel documents from the given folder."""
    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(f"{data_dir} does not exist")

    docs = []
    
    # Load all PDFs
    logger.info("Loading PDF files...")
    pdf_loader = DirectoryLoader(data_dir, glob="**/*.pdf", loader_cls=PyPDFLoader, show_progress=True)
    docs += pdf_loader.load()

    # Load Markdown and text files
    logger.info("Loading Markdown and Text files...")
    md_loader = DirectoryLoader(data_dir, glob="**/*.md", loader_cls=TextLoader, show_progress=True)
    txt_loader = DirectoryLoader(data_dir, glob="**/*.txt", loader_cls=TextLoader, show_progress=True)
    docs += md_loader.load() + txt_loader.load()
    
    # Load CSV files
    logger.info("Loading CSV files...")
    csv_loader = DirectoryLoader(data_dir, glob="**/*.csv", loader_cls=CSVLoader, show_progress=True)
    docs += csv_loader.load()
    
    # Load Excel files (.xlsx and .xls)
    logger.info("Loading Excel files...")
    xlsx_loader = DirectoryLoader(data_dir, glob="**/*.xlsx", loader_cls=UnstructuredExcelLoader, show_progress=True)
    xls_loader = DirectoryLoader(data_dir, glob="**/*.xls", loader_cls=UnstructuredExcelLoader, show_progress=True)
    docs += xlsx_loader.load() + xls_loader.load()
    
    logger.info(f"Total documents loaded: {len(docs)}")
    return docs


@log_time("Split Documents into Chunks")
def split_docs(docs):
    """Split docs into smaller chunks (important for embeddings and retrieval)."""
    logger.info(f"Splitting {len(docs)} documents...")
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    chunks = splitter.split_documents(docs)
    logger.info(f"Created {len(chunks)} chunks")
    return chunks


@log_time("Build Vector Store")
def build_store(chunks):
    """Embed chunks and store them in a persistent vector store (FAISS or Chroma)."""
    logger.info(f"Creating embeddings with model: {EMBED_MODEL}")
    logger.info(f"Processing {len(chunks)} chunks...")
    
    with Timer("Initialize embedding model"):
        vs_provider = get_vector_store_provider(cache_folder="./hugging_face/cache/")
    
    with Timer("Create embeddings and store"):
        vs = vs_provider.from_documents(chunks)
    
    logger.info(f"Vector store saved to: {PERSIST_DIR}")
    return vs


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Starting RAG Ingestion Pipeline")
    logger.info("=" * 50)
    
    docs = load_docs(DATA_DIR)
    chunks = split_docs(docs)
    build_store(chunks)
    
    logger.info("=" * 50)
    logger.info("Ingestion Complete!")
    logger.info("=" * 50)