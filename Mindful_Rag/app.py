"""
Student Wellness Scheduler - Streamlit RAG Chat Interface
----------------------------------------------------------
Uses local embeddings for classification/retrieval and OpenAI for generation.
API Key loaded securely from .env file.
"""

import os
import streamlit as st
import numpy as np
from dotenv import load_dotenv
from sklearn.metrics.pairwise import cosine_similarity
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


# ============================================================================
# CONFIGURATION
# ============================================================================

# Load environment variables from .env file
load_dotenv()

WELLNESS_CATEGORIES = [
    "Physical Activity",
    "Sleep Hygiene", 
    "Dietary Intake",
    "Stress Management",
    "Social Connection",
    "Substance Use",
    "Mindfulness"
]

CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "wellness_ablation"

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

@st.cache_resource
def load_embedding_model():
    """Load the local HuggingFace embedding model (cached)."""
    return HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )


@st.cache_resource
def load_vectorstore(_embeddings):
    """Load ChromaDB vector store (cached)."""
    return Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=_embeddings,
        collection_name=COLLECTION_NAME
    )


@st.cache_resource
def get_category_embeddings(_embeddings):
    """Pre-compute embeddings for all categories (cached)."""
    category_vectors = _embeddings.embed_documents(WELLNESS_CATEGORIES)
    return np.array(category_vectors)


def get_llm(api_key: str):
    """Initialize OpenAI LLM with the provided API key."""
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.3,
        api_key=api_key
    )


# ============================================================================
# CLASSIFICATION LOGIC
# ============================================================================

def classify_intent(user_query: str, embeddings, category_embeddings: np.ndarray) -> tuple[str, float]:
    """
    Classify user query into one of the 7 wellness categories.
    Uses cosine similarity between query embedding and category name embeddings.
    """
    query_vector = embeddings.embed_query(user_query)
    query_vector = np.array(query_vector).reshape(1, -1)
    similarities = cosine_similarity(query_vector, category_embeddings)[0]
    best_idx = np.argmax(similarities)
    return WELLNESS_CATEGORIES[best_idx], similarities[best_idx]


# ============================================================================
# RETRIEVAL LOGIC
# ============================================================================

def retrieve_relevant_chunks(query: str, category: str, vectorstore, top_k: int = 3) -> list[dict]:
    """Retrieve top_k relevant chunks from ChromaDB filtered by category."""
    results = vectorstore.similarity_search_with_score(
        query=query,
        k=top_k,
        filter={"category": category}
    )
    
    # Fallback: if no results with filter, try without
    if not results:
        results = vectorstore.similarity_search_with_score(query=query, k=top_k)
    
    return [
        {
            'content': doc.page_content,
            'filename': doc.metadata.get('filename', 'Unknown').replace('.pdf', ''),
            'category': doc.metadata.get('category', 'Unknown'),
        }
        for doc, score in results
    ]


# ============================================================================
# LLM GENERATION LOGIC
# ============================================================================

def generate_response_with_llm(user_query: str, chunks: list[dict], llm) -> str:
    """
    Generate a tailored response using OpenAI LLM.
    Passes retrieved context + user query to the model.
    """
    if not chunks:
        return "No relevant research found for your query. Please try rephrasing your question."
    
    # Build context from retrieved chunks
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(f"Source {i} ({chunk['filename']}):\n{chunk['content']}")
    
    context = "\n\n".join(context_parts)
    
    # Build the human message with context and query
    human_message = f"""CONTEXT (Research Abstracts):
{context}

USER QUERY: {user_query}

Based on the above research context, provide an actionable wellness plan following the exact output format specified."""

    # Call the LLM
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=human_message)
    ]
    
    response = llm.invoke(messages)
    return response.content


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
    
    # =========================================================================
    # API KEY VALIDATION
    # =========================================================================
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        st.error("**System Error:** API Key not found in environment. Please add `OPENAI_API_KEY` to your `.env` file.")
        st.info("Create a `.env` file in the project root with:\n```\nOPENAI_API_KEY=your-api-key-here\n```")
        st.stop()
    
    # =========================================================================
    # LOAD RESOURCES
    # =========================================================================
    with st.spinner("Initializing..."):
        embeddings = load_embedding_model()
        vectorstore = load_vectorstore(embeddings)
        category_embeddings = get_category_embeddings(embeddings)
        llm = get_llm(api_key)
    
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
                # Step 1: Classify intent (silent - no UI output)
                detected_category, _ = classify_intent(
                    prompt, embeddings, category_embeddings
                )
                
                # Step 2: Retrieve relevant chunks
                chunks = retrieve_relevant_chunks(
                    query=prompt,
                    category=detected_category,
                    vectorstore=vectorstore,
                    top_k=3
                )
                
                # Step 3: Generate response with LLM
                response = generate_response_with_llm(prompt, chunks, llm)
                
                # Display response
                st.markdown(response)
        
        # Save to history
        st.session_state.messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
