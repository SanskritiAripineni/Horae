"""
Student Wellness Scheduler - Streamlit RAG Chat Interface
----------------------------------------------------------
Uses Gemini embeddings for retrieval and Gemini 2.5 Flash for generation.
API Key loaded securely from .env file.
"""

import os
import time
import streamlit as st
from dotenv import load_dotenv
from google import genai
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from mindful_rag.config import ROOT_DIR, get_env_file, get_experiment
from mindful_rag.retrieval import RetrievalSettings, production_retrieve


# ============================================================================
# CONFIGURATION
# ============================================================================

# Load environment variables from root .env file
load_dotenv(dotenv_path=get_env_file())

EXPERIMENT_NAME = os.getenv("RAG_EXPERIMENT", "by_type")
EXPERIMENT = get_experiment(EXPERIMENT_NAME)
CHROMA_DIR = os.getenv("CHROMA_DIR", str(EXPERIMENT.chroma_dir))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", EXPERIMENT.collection_name)
EMBEDDING_MODEL = "models/gemini-embedding-001"
GENERATION_MODEL = "gemini-2.5-flash"


def _env_int(name: str, default: int, min_value: int, max_value: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return max(min_value, min(max_value, parsed))


def _env_float(name: str, default: float, min_value: float, max_value: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        parsed = float(raw)
    except ValueError:
        return default
    return max(min_value, min(max_value, parsed))


RETRIEVAL_SETTINGS = RetrievalSettings(
    top_k=_env_int("RETRIEVAL_TOP_K", 4, 1, 12),
    fetch_k=_env_int("RETRIEVAL_FETCH_K", 24, 4, 128),
    mmr_lambda=_env_float("RETRIEVAL_MMR_LAMBDA", 0.5, 0.0, 1.0),
    max_per_source=_env_int("RETRIEVAL_MAX_PER_SOURCE", 2, 1, 6),
    min_hybrid_score=_env_float("RETRIEVAL_MIN_SCORE", 0.05, 0.0, 1.0),
)
GENERATION_MAX_RETRIES = _env_int("GENERATION_MAX_RETRIES", 2, 0, 5)
GENERATION_RETRY_BASE_SECONDS = _env_float("GENERATION_RETRY_BASE_SECONDS", 1.0, 0.1, 10.0)

# System prompt for the LLM
SYSTEM_PROMPT = """You are an expert academic wellness scheduler. Your goal is to convert research abstracts into a strict, actionable plan.

RULES:
1. NO Emojis. Do not use any emojis in the output.
2. Be concise.
3. Base all advice strictly on the provided context.

OUTPUT FORMAT:
Step 1: State the user's intent in one brief sentence. 
(Format: "The user is intending to [goal].")

Step 2: State the evidence basis.
(Format: "Research supports the following evidence-based techniques:")

Step 3: Provide exactly 4-5 bullet points.
- Each bullet must specify WHAT to do and WHEN to do it.
- Format: "[Specific Action] at [Time/Context]."
- Example: "Practice deep breathing immediately after dinner."

Step 4: List sources at the bottom."""


# ============================================================================
# CACHED RESOURCES
# ============================================================================

class GeminiDualTaskEmbeddings(Embeddings):
    """Use retrieval-optimized task types for document and query embeddings."""

    def __init__(self, api_key: str):
        self._doc_embedder = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=api_key,
            task_type="retrieval_document"
        )
        self._query_embedder = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=api_key,
            task_type="retrieval_query"
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._doc_embedder.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._query_embedder.embed_query(text)


@st.cache_resource
def load_embedding_model(api_key: str):
    """Load Gemini embedding model wrapper (cached)."""
    return GeminiDualTaskEmbeddings(api_key)


@st.cache_resource
def load_vectorstore(_embeddings):
    """Load ChromaDB vector store (cached)."""
    return Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=_embeddings,
        collection_name=COLLECTION_NAME
    )


def get_llm(api_key: str):
    """Initialize Google GenAI client with the provided API key."""
    return genai.Client(api_key=api_key)


# ============================================================================
# RETRIEVAL LOGIC
# ============================================================================

def retrieve_relevant_chunks(query: str, vectorstore) -> tuple[list[dict], dict]:
    """
    Retrieve chunks with hybrid ranking + fallback behavior.
    """
    result = production_retrieve(query=query, vectorstore=vectorstore, settings=RETRIEVAL_SETTINGS)
    return result.chunks, result.stats


# ============================================================================
# LLM GENERATION LOGIC
# ============================================================================

def generate_response_with_llm(user_query: str, chunks: list[dict], client) -> str:
    """
    Generate a tailored response using Gemini LLM.
    Passes retrieved context + user query to the model.
    """
    if not chunks:
        return "No relevant research found for your query. Please try rephrasing your question."
    
    # Build context from retrieved chunks
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(f"Source {i} ({chunk['filename']}):\n{chunk['content']}")
    
    context = "\n\n".join(context_parts)
    
    prompt = f"""{SYSTEM_PROMPT}

CONTEXT (Research Abstracts):
{context}

USER QUERY: {user_query}

Based on the above research context, provide an actionable wellness plan following the exact output format specified."""

    last_error = None
    for attempt in range(GENERATION_MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=GENERATION_MODEL,
                contents=prompt,
            )
            if getattr(response, "text", None):
                return response.text
            return "No response generated."
        except Exception as exc:
            last_error = exc
            if attempt < GENERATION_MAX_RETRIES:
                backoff = GENERATION_RETRY_BASE_SECONDS * (2 ** attempt)
                time.sleep(backoff)

    return (
        "I could not generate a response right now due to a temporary model error. "
        f"Please try again. ({last_error})"
    )


# ============================================================================
# STREAMLIT UI
# ============================================================================

def main():
    st.set_page_config(
        page_title="Student Wellness Scheduler",
        page_icon="📋",
        layout="centered"
    )
    
    # Custom CSS for clean, professional look
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(160deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
        }
        .main-header {
            text-align: center;
            padding: 1rem 0;
            color: #e6edf3;
        }
        .main-header h1 {
            font-size: 2rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        .subtitle {
            text-align: center;
            color: #8b949e;
            font-size: 0.9rem;
            margin-bottom: 1.5rem;
        }
        .stChatMessage {
            background: rgba(255,255,255,0.02);
            border-radius: 8px;
        }
        .stDivider {
            border-color: #30363d;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
        <div class='main-header'>
            <h1>Student Wellness Scheduler</h1>
        </div>
        <p class='subtitle'>
            Evidence-based recommendations for sleep, stress, exercise, social connection, and mindfulness
        </p>
    """, unsafe_allow_html=True)
    
    st.divider()
    st.caption(
        f"Experiment: `{EXPERIMENT.name}` | Collection: `{COLLECTION_NAME}` | DB: `{CHROMA_DIR}`"
    )
    st.caption(
        "Retrieval: "
        f"top_k={RETRIEVAL_SETTINGS.top_k}, "
        f"fetch_k={RETRIEVAL_SETTINGS.fetch_k}, "
        f"max_per_source={RETRIEVAL_SETTINGS.max_per_source}"
    )
    
    # =========================================================================
    # API KEY VALIDATION
    # =========================================================================
    google_api_key = os.getenv("GOOGLE_API_KEY")

    if not google_api_key:
        st.error("**System Error:** API Key not found in environment. Please add `GOOGLE_API_KEY` to your `.env` file.")
        st.info("Create a `.env` file in the project root with:\n```\nGOOGLE_API_KEY=your-google-api-key-here\n```")
        st.stop()

    # =========================================================================
    # LOAD RESOURCES
    # =========================================================================
    with st.spinner("Initializing..."):
        embeddings = load_embedding_model(google_api_key)
        vectorstore = load_vectorstore(embeddings)
        client = get_llm(google_api_key)
    
    # =========================================================================
    # CHAT INTERFACE
    # =========================================================================
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("What wellness goal can I help you with?"):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Process query
        with st.chat_message("assistant"):
            with st.spinner("Generating your personalized plan..."):
                # Step 1: Retrieve relevant chunks
                chunks, retrieval_stats = retrieve_relevant_chunks(query=prompt, vectorstore=vectorstore)
                
                # Step 2: Generate response with LLM
                response = generate_response_with_llm(prompt, chunks, client)
                
                # Display response
                st.markdown(response)
                with st.expander("Retrieval Diagnostics", expanded=False):
                    st.json(retrieval_stats)
        
        # Save to history
        st.session_state.messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
