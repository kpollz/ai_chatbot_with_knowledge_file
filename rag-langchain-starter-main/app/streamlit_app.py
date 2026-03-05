"""
Comprehensive Streamlit RAG Application with Two Phases:
- Phase 1: Document Upload & Indexing (upload docs, configure settings, create index)
- Phase 2: Q&A Chat Interface (with conversation history)
"""

import os
import tempfile
from pathlib import Path
from typing import List, Optional
import streamlit as st
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader, 
    TextLoader,
    CSVLoader,
    UnstructuredExcelLoader
)
from rag import RAGPipeline, IngestPipeline
from config import TOP_K, EMBED_MODEL

# Page setup
st.set_page_config(
    page_title="RAG Chat Application",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better chat UI
st.markdown("""
<style>
.chat-message {
    padding: 1rem;
    border-radius: 0.5rem;
    margin-bottom: 1rem;
    display: flex;
    flex-direction: column;
}
.chat-message.user {
    background-color: #e3f2fd;
}
.chat-message.assistant {
    background-color: #f5f5f5;
}
.chat-message .role {
    font-weight: bold;
    margin-bottom: 0.5rem;
}
.chat-message.user .role {
    color: #1976d2;
}
.chat-message.assistant .role {
    color: #388e3c;
}
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if "phase" not in st.session_state:
        st.session_state.phase = "setup"  # "setup" or "chat"
    if "rag_pipeline" not in st.session_state:
        st.session_state.rag_pipeline = None
    if "ingest_pipeline" not in st.session_state:
        st.session_state.ingest_pipeline = None
    if "indexed" not in st.session_state:
        st.session_state.indexed = False
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = []
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []  # List of {role, content, citations}
    if "settings" not in st.session_state:
        st.session_state.settings = {
            "vector_store": "faiss",
            "chunk_size": 800,
            "chunk_overlap": 120,
            "top_k": 4,
            "persist_dir": "./index/faiss"
        }


def load_documents_from_files(uploaded_files) -> List[Document]:
    """Load documents from uploaded files."""
    documents = []
    
    for uploaded_file in uploaded_files:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name
        
        try:
            file_ext = Path(uploaded_file.name).suffix.lower()
            
            if file_ext == ".pdf":
                loader = PyPDFLoader(tmp_path)
                docs = loader.load()
            elif file_ext in [".txt", ".md"]:
                loader = TextLoader(tmp_path)
                docs = loader.load()
            elif file_ext == ".csv":
                loader = CSVLoader(tmp_path)
                docs = loader.load()
            elif file_ext in [".xlsx", ".xls"]:
                loader = UnstructuredExcelLoader(tmp_path)
                docs = loader.load()
            else:
                st.warning(f"Unsupported file type: {uploaded_file.name}")
                continue
            
            # Add source metadata
            for doc in docs:
                doc.metadata["source"] = uploaded_file.name
            
            documents.extend(docs)
            
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
    
    return documents


def render_setup_phase():
    """Render Phase 1: Document Upload & Indexing."""
    st.title("📚 Phase 1: Document Setup")
    st.markdown("Upload your documents, configure settings, and create the vector index.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📄 Upload Documents")
        uploaded_files = st.file_uploader(
            "Upload PDF, Markdown, Text, CSV, or Excel files",
            type=["pdf", "md", "txt", "csv", "xlsx", "xls"],
            accept_multiple_files=True,
            help="You can upload multiple files at once"
        )
        
        if uploaded_files:
            st.session_state.uploaded_files = uploaded_files
            st.success(f"✅ {len(uploaded_files)} file(s) ready for indexing")
            
            # Show file list
            with st.expander("View uploaded files"):
                for f in uploaded_files:
                    st.markdown(f"- {f.name} ({f.size / 1024:.1f} KB)")
    
    with col2:
        st.subheader("⚙️ Configuration")
        
        # Vector Store Selection
        vector_store = st.selectbox(
            "Vector Store",
            options=["faiss", "chroma"],
            index=0,
            help="FAISS is faster, Chroma has richer features"
        )
        
        # Chunking Settings
        chunk_size = st.slider(
            "Chunk Size",
            min_value=200,
            max_value=2000,
            value=st.session_state.settings["chunk_size"],
            step=100,
            help="Size of each text chunk"
        )
        
        chunk_overlap = st.slider(
            "Chunk Overlap",
            min_value=0,
            max_value=500,
            value=st.session_state.settings["chunk_overlap"],
            step=50,
            help="Overlap between consecutive chunks"
        )
        
        # TOP_K for retrieval
        top_k = st.slider(
            "Top K (retrieval)",
            min_value=1,
            max_value=10,
            value=st.session_state.settings["top_k"],
            step=1,
            help="Number of chunks to retrieve per query"
        )
        
        # Persist directory
        persist_dir = st.text_input(
            "Index Directory",
            value=f"./index/{vector_store}",
            help="Directory to store the vector index"
        )
        
        # Update settings
        st.session_state.settings = {
            "vector_store": vector_store,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "top_k": top_k,
            "persist_dir": persist_dir
        }
    
    # Indexing Section
    st.divider()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button("🚀 Create Vector Index", type="primary", use_container_width=True):
            if not st.session_state.uploaded_files:
                st.error("❌ Please upload at least one document first!")
            else:
                with st.spinner("Creating index... This may take a few minutes."):
                    try:
                        # Load documents
                        st.info("📄 Loading documents...")
                        documents = load_documents_from_files(st.session_state.uploaded_files)
                        
                        if not documents:
                            st.error("❌ No documents could be loaded!")
                        else:
                            st.info(f"📝 Loaded {len(documents)} document pages")
                            
                            # Create ingest pipeline
                            st.info("🔧 Initializing ingest pipeline...")
                            ingest = IngestPipeline()
                            ingest.set_vector_store(vector_store, persist_dir)
                            
                            # Ingest documents
                            st.info("📊 Creating embeddings and index...")
                            num_chunks = ingest.ingest_documents(
                                documents,
                                chunk_size=chunk_size,
                                chunk_overlap=chunk_overlap
                            )
                            
                            # Create persist directory if needed
                            Path(persist_dir).mkdir(parents=True, exist_ok=True)
                            
                            st.session_state.ingest_pipeline = ingest
                            st.session_state.indexed = True
                            
                            st.success(f"✅ Index created successfully!")
                            st.info(f"📊 {len(documents)} pages → {num_chunks} chunks")
                            
                    except Exception as e:
                        st.error(f"❌ Error creating index: {str(e)}")
    
    # Proceed to Chat Phase
    if st.session_state.indexed:
        st.divider()
        st.markdown("### ✅ Ready for Q&A!")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("💬 Start Chatting →", type="primary", use_container_width=True):
                st.session_state.phase = "chat"
                st.rerun()


def render_chat_message(role: str, content: str, citations: Optional[List] = None):
    """Render a single chat message with optional citations."""
    if role == "user":
        st.markdown(f"""
        <div class="chat-message user">
            <div class="role">👤 You</div>
            <div class="content">{content}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="chat-message assistant">
            <div class="role">🤖 Assistant</div>
            <div class="content">{content}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Show citations if available
        if citations:
            with st.expander("📚 Sources"):
                for c in citations:
                    page = f", page {c['page']}" if c["page"] is not None else ""
                    st.markdown(f"**[{c['n']}]** {c['source']}{page}")
                    st.caption(c["snippet"])


def render_chat_phase():
    """Render Phase 2: Q&A Chat Interface."""
    st.title("💬 Phase 2: Q&A Chat")
    
    # Initialize RAG pipeline
    @st.cache_resource
    def get_rag():
        rag = RAGPipeline()
        rag.initialize()
        rag.set_vector_store(
            st.session_state.settings["vector_store"],
            st.session_state.settings["persist_dir"]
        )
        return rag
    
    # Get or create RAG pipeline
    if st.session_state.rag_pipeline is None:
        st.session_state.rag_pipeline = get_rag()
    
    rag = st.session_state.rag_pipeline
    
    # Sidebar with settings and controls
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        
        # TOP_K setting (runtime)
        current_top_k = st.slider(
            "Top K",
            min_value=1,
            max_value=10,
            value=st.session_state.settings["top_k"],
            key="chat_top_k"
        )
        
        # Use conversation history toggle
        use_history = st.toggle(
            "Conversation Memory",
            value=True,
            help="Include previous messages in context"
        )
        
        st.divider()
        
        # Clear history button
        if st.button("🗑️ Clear Chat History", use_container_width=True):
            rag.clear_history()
            st.session_state.chat_messages = []
            st.success("Chat history cleared!")
        
        # Back to setup button
        if st.button("📚 Back to Setup", use_container_width=True):
            st.session_state.phase = "setup"
            st.rerun()
        
        st.divider()
        
        # Show current settings
        with st.expander("📋 Current Settings"):
            st.markdown(f"- **Vector Store:** {st.session_state.settings['vector_store']}")
            st.markdown(f"- **Chunk Size:** {st.session_state.settings['chunk_size']}")
            st.markdown(f"- **Chunk Overlap:** {st.session_state.settings['chunk_overlap']}")
            st.markdown(f"- **Index Dir:** {st.session_state.settings['persist_dir']}")
    
    # Chat container
    chat_container = st.container()
    
    # Display chat history with citations
    with chat_container:
        if not st.session_state.chat_messages:
            st.info("👋 Ask a question about your documents to get started!")
        else:
            # Display all messages from session state (with citations)
            for msg in st.session_state.chat_messages:
                render_chat_message(
                    msg["role"], 
                    msg["content"], 
                    msg.get("citations")
                )
    
    # Chat input
    st.divider()
    
    # Use st.chat_input if available (Streamlit >= 1.24)
    if hasattr(st, 'chat_input'):
        prompt = st.chat_input("Ask a question about your documents...")
        
        if prompt:
            with st.spinner("Thinking..."):
                result = rag.answer(
                    prompt, 
                    k=current_top_k,
                    use_history=use_history
                )
                # Store user message
                st.session_state.chat_messages.append({
                    "role": "user",
                    "content": prompt,
                    "citations": None
                })
                # Store assistant message with citations
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": result["answer"],
                    "citations": result["citations"]
                })
            st.rerun()
    else:
        # Fallback for older Streamlit versions
        col1, col2 = st.columns([5, 1])
        with col1:
            user_input = st.text_input(
                "Ask a question:",
                key="user_input",
                label_visibility="collapsed"
            )
        with col2:
            send = st.button("Send", type="primary")
        
        if send and user_input.strip():
            with st.spinner("Thinking..."):
                result = rag.answer(
                    user_input,
                    k=current_top_k,
                    use_history=use_history
                )
                # Store user message
                st.session_state.chat_messages.append({
                    "role": "user",
                    "content": user_input,
                    "citations": None
                })
                # Store assistant message with citations
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": result["answer"],
                    "citations": result["citations"]
                })
            st.rerun()


def main():
    """Main application entry point."""
    init_session_state()
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown("# 🤖 RAG Chat")
        st.markdown("---")
        
        # Phase indicator
        if st.session_state.phase == "setup":
            st.markdown("**📍 Current Phase:** Setup")
            st.markdown("1. 📚 Setup *(current)*")
            st.markdown("2. 💬 Q&A Chat")
        else:
            st.markdown("**📍 Current Phase:** Chat")
            st.markdown("1. 📚 Setup")
            st.markdown("2. 💬 Q&A Chat *(current)*")
        
        st.markdown("---")
    
    # Render appropriate phase
    if st.session_state.phase == "setup":
        render_setup_phase()
    else:
        render_chat_phase()


if __name__ == "__main__":
    main()