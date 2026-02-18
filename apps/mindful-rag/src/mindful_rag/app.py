"""
Student Wellness Scheduler - Streamlit RAG Chat Interface
----------------------------------------------------------
Uses Gemini embeddings for retrieval and Gemini 2.5 Flash for generation.
API Key loaded securely from .env file.
"""

import os
import time
import uuid
import streamlit as st
from dotenv import load_dotenv
from google import genai
from langchain_chroma import Chroma

from mindful_rag.config import ROOT_DIR, get_env_file, get_experiment
from mindful_rag.embeddings import create_dual_task_embeddings
from mindful_rag.retrieval import RetrievalSettings, production_retrieve
from mindful_rag.evaluators import evaluate_all_sources


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
SYSTEM_PROMPT = """You are a supportive and knowledgeable wellness counselor for university students. Your goal is to provide evidence-based, actionable advice based *strictly* on the provided research context.

GUIDELINES:
- **Tone:** Professional, encouraging, and clear.
- **Structure:** Use efficient constraints but allow for natural language. Use bolding for emphasis.
- **Evidence:** Every recommendation must be backed by the provided context.
- **No Emojis:** Keep it clean and academic.

OUTPUT FORMAT:
1. **Understanding:** A single sentence acknowledging the user's goal.
2. **Evidence-Based Plan:** 3-5 specific, actionable steps found in the research.
   - Format: "**[Action]**: [Details/Timing] (Source N)"
3. > **Key Insight:** One brief sentence summarizing *why* this works based on the studies. (Use blockquote `>` for this line)

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

def _build_source_references(chunks: list[dict]) -> str:
    """
    Build a references section mapping Source N → actual paper filename.
    Returns a markdown string to append after the LLM response.
    """
    if not chunks:
        return ""

    lines = ["\n---\n**References:**"]
    for i, chunk in enumerate(chunks, 1):
        filename = chunk.get("filename", "Unknown")
        retrieval_source = chunk.get("retrieval_source", "unknown")
        category = chunk.get("category", "")
        ref_parts = [f"- **Source {i}:** {filename}"]
        if category:
            ref_parts[0] += f" — *{category}*"
        ref_parts[0] += f" (via {retrieval_source})"
        lines.append(ref_parts[0])
    return "\n".join(lines)


def generate_response_with_llm(user_query: str, chunks: list[dict], client) -> str:
    """
    Generate a tailored response using Gemini LLM.
    Passes retrieved context + user query to the model.
    Appends a references section mapping Source N to actual filenames.
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
                # Append source references
                references = _build_source_references(chunks)
                return response.text + references
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


# ============================================================================
# EVALUATION ANALYTICS RENDERING
# ============================================================================

def _score_bar(score: float) -> str:
    """Return a colored bar representation of a 0-1 score."""
    if score >= 0.8:
        color = "#2ea043"   # green
    elif score >= 0.6:
        color = "#d29922"   # yellow
    elif score >= 0.4:
        color = "#da3633"   # orange-red
    else:
        color = "#f85149"   # red
    pct = int(score * 100)
    return f'<div style="background:#30363d;border-radius:4px;overflow:hidden;height:20px;width:100%"><div style="background:{color};height:100%;width:{pct}%;border-radius:4px;display:flex;align-items:center;justify-content:center;color:white;font-size:12px;font-weight:600">{pct}%</div></div>'


def render_evaluation_dashboard(eval_results: dict):
    """Render the full evaluation analytics dashboard."""
    per_source = eval_results["per_source"]
    overview = eval_results["overview"]
    sources = list(per_source.keys())
    metric_labels = {
        "faithfulness": "Faithfulness",
        "context_relevance": "Context Relevance",
        "answer_relevance": "Answer Relevance",
        "completeness": "Completeness",
    }

    st.markdown("---")
    st.markdown("## Evaluation Analytics")
    st.caption("Research-backed metrics: RAGAS (Faithfulness), ARES (Context Relevance), G-Eval (Answer Relevance), RGB (Completeness)")

    # ---- OVERVIEW COMPARISON TABLE ----
    st.markdown("### Overview — Source Comparison")
    
    # Build comparison table
    header_cols = st.columns([2] + [1] * len(sources))
    header_cols[0].markdown("**Metric**")
    for i, src in enumerate(sources):
        is_winner = (src == overview["winner"])
        label = f"**`{src}`** 🏆" if is_winner else f"**`{src}`**"
        header_cols[i + 1].markdown(label)
    
    for m_key, m_label in metric_labels.items():
        row_cols = st.columns([2] + [1] * len(sources))
        winner_source = overview["metric_winners"].get(m_key)
        row_cols[0].markdown(f"**{m_label}**")
        for i, src in enumerate(sources):
            score = per_source[src][m_key]["score"]
            is_metric_winner = (src == winner_source) and len(sources) > 1
            icon = " 🏆" if is_metric_winner else ""
            row_cols[i + 1].markdown(
                _score_bar(score) + f"{icon}",
                unsafe_allow_html=True,
            )
    
    # Aggregate row
    agg_cols = st.columns([2] + [1] * len(sources))
    agg_cols[0].markdown("**Overall**")
    for i, src in enumerate(sources):
        agg_score = per_source[src]["aggregate"]
        is_winner = (src == overview["winner"]) and len(sources) > 1
        icon = " 🏆" if is_winner else ""
        agg_cols[i + 1].markdown(
            _score_bar(agg_score) + f"{icon}",
            unsafe_allow_html=True,
        )
    
    # Verdict
    if len(sources) > 1:
        winner = overview["winner"]
        winner_score = overview["source_scores"][winner]
        st.success(
            f"**Best Source: `{winner}`** with an aggregate score of **{int(winner_score * 100)}%**. "
            f"This source produced the most faithful, relevant, and complete response."
        )

    # ---- PER-SOURCE DETAIL ----
    st.markdown("### Detailed Analysis per Source")
    
    tabs = st.tabs([f"Source: {src}" for src in sources])
    for tab, src in zip(tabs, sources):
        with tab:
            data = per_source[src]
            for m_key, m_label in metric_labels.items():
                metric_data = data[m_key]
                score = metric_data["score"]
                explanation = metric_data.get("explanation", "")
                
                with st.expander(f"{m_label} — **{int(score * 100)}%**", expanded=False):
                    st.markdown(_score_bar(score), unsafe_allow_html=True)
                    st.markdown(f"**Explanation:** {explanation}")
                    
                    # Show chunk-level detail for context relevance
                    if m_key == "context_relevance" and "chunk_scores" in metric_data:
                        st.markdown("**Per-chunk scores:**")
                        for cs in metric_data["chunk_scores"]:
                            st.caption(
                                f"Chunk {cs['chunk_index']} (`{cs['filename']}`): "
                                f"**{cs['score']}/5** — {cs['reason']}"
                            )


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
                # Filter out "all" for comparison mode usually, but kept for flexibility
                available_sources = [s for s in options if s != "all"]
                
                selected_sources = []
                st.markdown("Select sources to compare:")
                for src in available_sources:
                    # Default relevant_info and intro_concl to True
                    default_checked = src in ["relevant_info", "intro_concl"]
                    if st.checkbox(SOURCE_FILTER_LABELS.get(src, src), value=default_checked, key=f"chk_{src}"):
                        selected_sources.append(src)
                
                if not selected_sources:
                    st.warning("Please select at least one source.")
            else:
                selected_sources = [st.selectbox(
                    "Retrieval source",
                    options=list(SOURCE_FILTER_LABELS.keys()),
                    format_func=lambda key: SOURCE_FILTER_LABELS.get(key, key),
                    index=0
                )]

        if st.sidebar.button("🗑️ Clear Chat", type="primary"):
            st.session_state.messages = []
            st.session_state.evaluations = {}
            st.rerun()

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

    # Initialize session state for data persistence
    if "evaluations" not in st.session_state:
        st.session_state.evaluations = {}
    if "trace_logs" not in st.session_state:
        st.session_state.trace_logs = {}

    # =========================================================================
    # DISPLAY CHAT HISTORY
    # =========================================================================
    last_evaluable_group_id = None

    for i, message in enumerate(st.session_state.messages):
        role = message["role"]
        
        # Special handling for comparison rows
        if message.get("type") == "comparison":
            results = message.get("comparison_data", [])
            group_id = message.get("group_id")
            cols = st.columns(len(results))
            for idx, res in enumerate(results):
                with cols[idx]:
                    st.markdown(f"### Source: `{res['source']}`")
                    st.markdown(res['content'])
                    
                    # Diagnostics
                    if res.get("stats"):
                        with st.expander("Diagnostics (Copyable)", expanded=False):
                            st.caption("Hover top-right of code block to copy")
                            st.code(str(res["stats"]), language="json")
            
            last_evaluable_group_id = group_id
            
            # Render evaluation if it exists for this group
            eval_key = f"eval_{group_id}"
            if eval_key in st.session_state.evaluations:
                render_evaluation_dashboard(st.session_state.evaluations[eval_key])
                        
        else:
            # Standard message rendering
            with st.chat_message(role):
                st.markdown(message["content"])
                
                # Render interactive elements for assistant messages
                if role == "assistant" and not message.get("type"):
                    stats = message.get("stats")
                    group_id = message.get("group_id")
                    
                    if stats:
                        with st.expander("Diagnostics (Copyable)", expanded=False):
                            st.caption("Hover top-right of code block to copy")
                            st.code(str(stats), language="json")
                    
                    if group_id:
                        last_evaluable_group_id = group_id
            
            # Render evaluation if it exists (outside chat_message for better layout)
            if role == "assistant" and not message.get("type"):
                group_id = message.get("group_id")
                if group_id:
                    eval_key = f"eval_{group_id}"
                    if eval_key in st.session_state.evaluations:
                        render_evaluation_dashboard(st.session_state.evaluations[eval_key])

    # =========================================================================
    # EVALUATE ALL BUTTON — appears once after all messages
    # =========================================================================
    if last_evaluable_group_id:
        eval_key = f"eval_{last_evaluable_group_id}"
        if eval_key not in st.session_state.evaluations:
            if st.button("📊 Evaluate All Responses", key=f"eval_all_{last_evaluable_group_id}", type="primary"):
                # Gather all source results for the latest query group
                latest_msg = None
                for msg in reversed(st.session_state.messages):
                    if msg.get("group_id") == last_evaluable_group_id:
                        latest_msg = msg
                        break
                
                if latest_msg:
                    query_text = latest_msg.get("query_text", "")
                    source_results = []
                    
                    if latest_msg.get("type") == "comparison":
                        # Comparison mode: multiple sources
                        for res in latest_msg.get("comparison_data", []):
                            source_results.append({
                                "source": res["source"],
                                "response": res["content"],
                                "chunks": res.get("chunks", []),
                            })
                    else:
                        # Standard mode: single source
                        source_label = latest_msg.get("source_filter", "all")
                        source_results.append({
                            "source": source_label,
                            "response": latest_msg["content"],
                            "chunks": latest_msg.get("chunks", []),
                        })
                    
                    with st.spinner("Running evaluation across all sources... (this may take 30-60 seconds)"):
                        eval_data = evaluate_all_sources(query_text, source_results)
                        st.session_state.evaluations[eval_key] = eval_data
                        st.rerun()

    # =========================================================================
    # PROCESS NEW USER INPUT
    # =========================================================================
    if user_input:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        
        group_id = str(uuid.uuid4())[:8]
        
        if comparison_mode and len(selected_sources) > 1:
            # Prepare comparison data container
            comparison_results = []
            
            cols = st.columns(len(selected_sources))
            
            for idx, source in enumerate(selected_sources):
                with cols[idx]:
                    st.markdown(f"### Source: `{source}`")
                    with st.spinner("Retrieving & Generating..."):
                        chunks, stats = retrieve_relevant_chunks(user_input, vectorstore, source)
                        response = generate_response_with_llm(user_input, chunks, client)
                        st.markdown(response)
                        
                        comparison_results.append({
                            "source": source,
                            "content": response,
                            "chunks": chunks,
                            "stats": stats,
                        })
            
            # Save the composite message
            st.session_state.messages.append({
                "role": "assistant",
                "type": "comparison",
                "content": "",  # Placeholder
                "comparison_data": comparison_results,
                "query_text": user_input,
                "group_id": group_id,
            })
            st.rerun()

        else:
            # Standard Mode (Single Source)
            source = selected_sources[0]
            with st.chat_message("assistant"):
                with st.spinner("Generating..."):
                    chunks, stats = retrieve_relevant_chunks(user_input, vectorstore, source)
                    stats["selected_source_filter"] = source
                    response = generate_response_with_llm(user_input, chunks, client)
                    st.markdown(response)
            
            # Save rich message to history
            st.session_state.messages.append({
                "role": "assistant", 
                "content": response,
                "chunks": chunks,
                "stats": stats,
                "query_text": user_input,
                "group_id": group_id,
                "source_filter": source,
            })
            st.rerun()

if __name__ == "__main__":
    main()
