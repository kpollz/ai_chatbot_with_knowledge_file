# Ingest Raw Datasets -> Split them into digestible chunks -> Create embeddings -> Store them in a Vector DB
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

def load_docs(data_dir: str):
    """Load PDF, Markdown, Text, CSV, and Excel documents from the given folder."""
    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(f"{data_dir} does not exist")

    docs = []
    
    # Load all PDFs
    pdf_loader = DirectoryLoader(data_dir, glob="**/*.pdf", loader_cls=PyPDFLoader, show_progress=True)
    docs += pdf_loader.load()

    # Load Markdown and text files
    md_loader = DirectoryLoader(data_dir, glob="**/*.md", loader_cls=TextLoader, show_progress=True)
    txt_loader = DirectoryLoader(data_dir, glob="**/*.txt", loader_cls=TextLoader, show_progress=True)
    docs += md_loader.load() + txt_loader.load()
    
    # Load CSV files
    csv_loader = DirectoryLoader(data_dir, glob="**/*.csv", loader_cls=CSVLoader, show_progress=True)
    docs += csv_loader.load()
    
    # Load Excel files (.xlsx and .xls)
    xlsx_loader = DirectoryLoader(data_dir, glob="**/*.xlsx", loader_cls=UnstructuredExcelLoader, show_progress=True)
    xls_loader = DirectoryLoader(data_dir, glob="**/*.xls", loader_cls=UnstructuredExcelLoader, show_progress=True)
    docs += xlsx_loader.load() + xls_loader.load()
    
    return docs

def split_docs(docs):
    """Split docs into smaller chunks (important for embeddings & retrieval)."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    return splitter.split_documents(docs)


def build_store(chunks):
    """Embed chunks and store them in a persistent vector store (FAISS or Chroma)."""
    vs_provider = get_vector_store_provider(cache_folder="./hugging_face/cache/")
    vs = vs_provider.from_documents(chunks)
    return vs


if __name__ == "__main__":
    print("Loading documents…")
    docs = load_docs(DATA_DIR)
    print(f"Loaded {len(docs)} documents")

    print("Splitting into chunks…")
    chunks = split_docs(docs)
    print(f"Created {len(chunks)} chunks")

    print("Building vector store…")
    build_store(chunks)
    print(f"Done. Vector store persisted to {PERSIST_DIR}")