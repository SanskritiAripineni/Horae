"""
Student Wellness Scheduler - Streamlit RAG Chat Interface
----------------------------------------------------------
Uses Gemini embeddings for retrieval and OpenAI for generation.
API Key loaded securely from .env file.
"""

import os
import streamlit as st
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_core.embeddings import Embeddings
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import GoogleGenerativeAIEmbeddings


# ============================================================================
# CONFIGURATION
# ============================================================================

# Load environment variables from .env file
load_dotenv()

CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "wellness_papers"
EMBEDDING_MODEL = "models/gemini-embedding-001"

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
    """Initialize OpenAI LLM with the provided API key."""
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.3,
        api_key=api_key
    )


# ============================================================================
# RETRIEVAL LOGIC
# ============================================================================

def retrieve_relevant_chunks(query: str, vectorstore, top_k: int = 4, fetch_k: int = 20) -> list[dict]:
    """
    Retrieve semantically relevant chunks using a standard MMR retriever.
    MMR improves diversity while keeping relevance high.
    """
    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": top_k,
            "fetch_k": max(fetch_k, top_k),
            "lambda_mult": 0.5,
        },
    )
    docs = retriever.invoke(query)

    return [
        {
            'content': doc.page_content,
            'filename': str(doc.metadata.get('filename') or doc.metadata.get('source') or 'Unknown').replace('.pdf', ''),
            'category': doc.metadata.get('category', 'Unknown'),
        }
        for doc in docs
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
    openai_api_key = os.getenv("OPENAI_API_KEY")
    google_api_key = os.getenv("GOOGLE_API_KEY")

    if not openai_api_key:
        st.error("**System Error:** API Key not found in environment. Please add `OPENAI_API_KEY` to your `.env` file.")
        st.info("Create a `.env` file in the project root with:\n```\nOPENAI_API_KEY=your-api-key-here\n```")
        st.stop()

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
        llm = get_llm(openai_api_key)
    
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
                chunks = retrieve_relevant_chunks(
                    query=prompt,
                    vectorstore=vectorstore,
                    top_k=4
                )
                
                # Step 2: Generate response with LLM
                response = generate_response_with_llm(prompt, chunks, llm)
                
                # Display response
                st.markdown(response)
        
        # Save to history
        st.session_state.messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
