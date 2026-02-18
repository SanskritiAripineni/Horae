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
import pandas as pd

from mindful_rag.config import ROOT_DIR, get_env_file, get_experiment
from mindful_rag.embeddings import create_dual_task_embeddings
from mindful_rag.retrieval import RetrievalSettings, production_retrieve
from mindful_rag.evaluators import relevance, groundedness, retrieval_relevance


# ============================================================================
# CONFIGURATION
# ============================================================================

# Load environment variables from root .env file
load_dotenv(dotenv_path=get_env_file())

EXPERIMENT_NAME = os.getenv("RAG_EXPERIMENT", "by_type")
EXPERIMENT = get_experiment(EXPERIMENT_NAME)
CHROMA_DIR = os.getenv("CHROMA_DIR", str(EXPERIMENT.chroma_dir))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", EXPERIMENT.collection_name)
EMBEDDING_MODEL = "gemini-embedding-001"
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
ALLOW_EMBEDDING_FALLBACK = os.getenv("ALLOW_EMBEDDING_FALLBACK", "0").strip().lower() not in {
    "0",
    "false",
    "no",
}
SOURCE_FILTER_LABELS = {
    "all": "All indexed sources",
    "relevant_info": "relevant_info only",
    "intro_concl": "intro_concl only",
    "raw": "raw only",
}

# System prompt for the LLM
# System prompt for the LLM
SYSTEM_PROMPT = """You are a supportive and knowledgeable wellness counselor for university students. Your goal is to provide evidence-based, actionable advice based *strictly* on the provided research context.

GUIDELINES:
- **Tone:** Professional, encouraging, and clear.
- **Structure:** Use efficient constraints but allow for natural language. Use bolding for emphasis.
- **Evidence:** Every recommendation must be backed by the provided context.
- **No Emojis:** Keep it clean and academic.

OUTPUT FORMAT:
1. **Understanding:** A single sentence acknowledging the user's goal.
2. **Evidence-Based Plan:** 3-5 specific, actionable steps found in the research.
   - Format: "**[Action]**: [Details/Timing] ([Source])"
3. **Key Insight:** One brief sentence summarizing *why* this works based on the studies.

If the context does not contain relevant information, politely state that you cannot answer based on the available research."""


# ============================================================================
# CACHED RESOURCES
# ============================================================================

@st.cache_resource
def load_embedding_model(api_key: str):
    """Load Gemini embedding model wrapper (cached)."""
    return create_dual_task_embeddings(
        api_key=api_key,
        model=EMBEDDING_MODEL,
        allow_fallback=ALLOW_EMBEDDING_FALLBACK,
    )


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

def retrieve_relevant_chunks(
    query: str,
    vectorstore,
    source_filter: str = "all",
) -> tuple[list[dict], dict]:
    """
    Retrieve chunks with hybrid ranking + fallback behavior.
    """
    metadata_filter = None if source_filter == "all" else {"retrieval_source": source_filter}
    result = production_retrieve(
        query=query,
        vectorstore=vectorstore,
        settings=RETRIEVAL_SETTINGS,
        metadata_filter=metadata_filter,
    )
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
        retrieval_source = chunk.get("retrieval_source", "unknown")
        context_parts.append(
            f"Source {i} ({chunk['filename']} | source={retrieval_source}):\n{chunk['content']}"
        )
    
    context = "\n\n".join(context_parts)
    
    prompt = f"""{SYSTEM_PROMPT}

CONTEXT (Research Abstracts):
{context}

USER QUERY: {user_query}

Based on the above research context, provide an actionable wellness plan."""

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



def generate_example_prompts(client, count: int = 3) -> list[str]:
    """Generate diverse example prompts using a lightweight model."""
    prompt = f"""Generate {count} distinct, specific questions a university student might ask a wellness counselor about sleep, stress, or social connection.
    Return ONLY a JSON array of strings. Example: ["How can I sleep better?", "I feel lonely."]"""
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        if response.text:
            import json
            return json.loads(response.text)
    except Exception:
        pass
    return ["How can I manage exam stress?", "Tips for better sleep?", "How to make friends on campus?"]


def evaluate_response(query: str, response: str, chunks: list[dict]) -> pd.DataFrame:
    """Run evaluations on the response with robust error handling."""
    inputs = {"question": query}
    
    # Adapt outputs to match evaluator expectations
    class MockDoc:
        def __init__(self, content):
            self.page_content = str(content) # Ensure string
            
    try:
        docs = [MockDoc(c.get("content", "")) for c in chunks]
    except Exception:
        docs = []
        
    outputs = {"answer": str(response), "documents": docs}
    
    results = {}
    
    # Metric 1: Relevance
    try:
        results["Relevance"] = relevance(inputs, outputs)
    except Exception as e:
        # print(f"Relevance Eval Failed: {e}") # Debug log
        results["Relevance"] = None
        
    # Metric 2: Groundedness
    try:
        if not docs:
            results["Groundedness"] = False # No docs = not grounded
        else:
            results["Groundedness"] = groundedness(inputs, outputs)
    except Exception as e:
        results["Groundedness"] = None
        
    # Metric 3: Retrieval Quality
    try:
        if not docs:
             results["Retrieval Quality"] = False
        else:
            results["Retrieval Quality"] = retrieval_relevance(inputs, outputs)
    except Exception as e:
        results["Retrieval Quality"] = None
        
    return pd.DataFrame([results])


# ============================================================================
# CACHED RESOURCES
# ============================================================================

@st.cache_resource
def load_embedding_model(api_key: str):
    """Load Gemini embedding model wrapper (cached)."""
    return create_dual_task_embeddings(
        api_key=api_key,
        model=EMBEDDING_MODEL,
        allow_fallback=ALLOW_EMBEDDING_FALLBACK,
    )


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

def retrieve_relevant_chunks(
    query: str,
    vectorstore,
    source_filter: str = "all",
) -> tuple[list[dict], dict]:
    """
    Retrieve chunks with hybrid ranking + fallback behavior.
    """
    metadata_filter = None if source_filter == "all" else {"retrieval_source": source_filter}
    result = production_retrieve(
        query=query,
        vectorstore=vectorstore,
        settings=RETRIEVAL_SETTINGS,
        metadata_filter=metadata_filter,
    )
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
        retrieval_source = chunk.get("retrieval_source", "unknown")
        context_parts.append(
            f"Source {i} ({chunk['filename']} | source={retrieval_source}):\n{chunk['content']}"
        )
    
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



def generate_example_prompts(client, count: int = 3) -> list[str]:
    """Generate diverse example prompts using a lightweight model."""
    prompt = f"""Generate {count} distinct, specific questions a university student might ask a wellness counselor about sleep, stress, or social connection.
    Return ONLY a JSON array of strings. Example: ["How can I sleep better?", "I feel lonely."]"""
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        if response.text:
            import json
            return json.loads(response.text)
    except Exception:
        pass
    return ["How can I manage exam stress?", "Tips for better sleep?", "How to make friends on campus?"]


def evaluate_response(query: str, response: str, chunks: list[dict]) -> pd.DataFrame:
    """Run evaluations on the response."""
    inputs = {"question": query}
    # Adapt outputs to match evaluator expectations
    class MockDoc:
        def __init__(self, content):
            self.page_content = content
            
    docs = [MockDoc(c["content"]) for c in chunks]
    outputs = {"answer": response, "documents": docs}
    
    results = {}
    try:
        results["Relevance"] = relevance(inputs, outputs)
    except Exception:
        results["Relevance"] = None
        
    try:
        results["Groundedness"] = groundedness(inputs, outputs)
    except Exception:
        results["Groundedness"] = None
        
    try:
        results["Retrieval Quality"] = retrieval_relevance(inputs, outputs)
    except Exception:
        results["Retrieval Quality"] = None
        
    return pd.DataFrame([results])


# ============================================================================
# STREAMLIT UI
# ============================================================================

def main():
    st.set_page_config(
        page_title="Student Wellness Scheduler",
        page_icon="📋",
        layout="wide"
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

    # =========================================================================
    # API KEY VALIDATION
    # =========================================================================
    google_api_key = os.getenv("GOOGLE_API_KEY")

    if not google_api_key:
        st.error("**System Error:** API Key not found in environment. Please add `GOOGLE_API_KEY` to your `.env` file.")
        st.stop()

    # =========================================================================
    # LOAD RESOURCES
    # =========================================================================
    with st.spinner("Initializing..."):
        embeddings = load_embedding_model(google_api_key)
        vectorstore = load_vectorstore(embeddings)
        client = get_llm(google_api_key)

    # =========================================================================
    # SIDEBAR CONTROLS
    # =========================================================================
    with st.sidebar:
        st.header("Settings")
        st.caption(f"Experiment: `{EXPERIMENT.name}`")
        
        # Prompt Generation
        st.subheader("Generate Examples")
        num_prompts = st.slider("Number of prompts", 1, 5, 3)
        if st.button("Generate Prompts"):
            with st.spinner("Thinking..."):
                st.session_state.example_prompts = generate_example_prompts(client, num_prompts)
        
        if "example_prompts" in st.session_state and st.session_state.example_prompts:
            st.markdown("**Try one:**")
            for ex in st.session_state.example_prompts:
                if st.button(ex, key=f"btn_{ex[:10]}"):
                    st.session_state.example_clicked = ex

        st.divider()
        
        # Comparison Mode
        is_csv_experiment = EXPERIMENT.name == "csv_sources"
        comparison_mode = False
        selected_sources = ["all"]
        
        if is_csv_experiment:
            comparison_mode = st.toggle("Compare Sources", value=False)
            if comparison_mode:
                options = list(SOURCE_FILTER_LABELS.keys())
                # specific behavior: remove 'all' from comparison options to force specific source selection if desired, 
                # but 'all' is also a valid "source" (no filter). Let's keep it.
                default_sources = ["relevant_info", "intro_concl"]
                selected_sources = st.multiselect(
                    "Select sources to compare",
                    options=options,
                    default=[s for s in default_sources if s in options],
                    format_func=lambda key: SOURCE_FILTER_LABELS.get(key, key)
                )
            else:
                selected_sources = [st.selectbox(
                    "Retrieval source",
                    options=list(SOURCE_FILTER_LABELS.keys()),
                    format_func=lambda key: SOURCE_FILTER_LABELS.get(key, key),
                    index=0
                )]

    # =========================================================================
    # CHAT LOGIC
    # =========================================================================
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Handle Example Click
    user_input = st.chat_input("What wellness goal can I help you with?")
    if "example_clicked" in st.session_state and st.session_state.example_clicked:
        user_input = st.session_state.example_clicked
        del st.session_state.example_clicked  # Consumption

    # Display chat history (only for non-comparison mode or unified history? 
    # Comparison mode makes history tricky. Let's show history normally, 
    # and if comparison runs, we append a special block or just show it ephemeral.)
    # Decision: In comparison mode, we won't strictly enforce linear chat history 
    # because it gets wide. We'll just show the result. 
    # OR: We append the "User" message, then show the comparison block.
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_input:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Process
        if comparison_mode and len(selected_sources) > 1:
            cols = st.columns(len(selected_sources))
            
            # We won't append the huge comparison block to session_state history 
            # as it's hard to render layout there. We'll just render it ephemeral.
            
            for idx, source in enumerate(selected_sources):
                with cols[idx]:
                    st.markdown(f"### Source: `{source}`")
                    with st.spinner("Retrieving & Generating..."):
                        chunks, stats = retrieve_relevant_chunks(
                            query=user_input,
                            vectorstore=vectorstore,
                            source_filter=source,
                        )
                        response = generate_response_with_llm(user_input, chunks, client)
                        st.markdown(response)
                        
                        # Diagnostics
                        with st.expander("Diagnostics"):
                            st.json(stats)
                            
                        # Evaluation
                        key = f"eval_{source}_{hash(user_input)}"
                        if st.button("Evaluate Result", key=key):
                            with st.spinner("Grading..."):
                                df_eval = evaluate_response(user_input, response, chunks)
                                st.dataframe(df_eval)

        else:
            # Standard Mode (Single Source)
            source = selected_sources[0]
            with st.chat_message("assistant"):
                with st.spinner("Generating your personalized plan..."):
                    chunks, stats = retrieve_relevant_chunks(
                        query=user_input,
                        vectorstore=vectorstore,
                        source_filter=source,
                    )
                    stats["selected_source_filter"] = source
                    response = generate_response_with_llm(user_input, chunks, client)
                    st.markdown(response)
                    
                    with st.expander("Retrieval Diagnostics", expanded=False):
                        st.json(stats)
                        
                    # Evaluation
                    key = f"eval_single_{hash(user_input)}"
                    if st.button("Evaluate Result", key=key):
                        with st.spinner("Grading..."):
                            df_eval = evaluate_response(user_input, response, chunks)
                            st.dataframe(df_eval)

            # Save to history (only in single mode to keep it clean)
            st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()
