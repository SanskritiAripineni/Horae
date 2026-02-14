"""
Test Script for RAG Evaluation Metrics
---------------------------------------
This script demonstrates how to use the evaluation metrics to test
your MindfulRAG system's performance.

Usage:
    python3 test_evaluators.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_core.embeddings import Embeddings
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import GoogleGenerativeAIEmbeddings

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import your evaluators
from src.mindful_rag.evaluators import correctness, relevance, groundedness, retrieval_relevance
from src.mindful_rag.config import ROOT_DIR, get_experiment

# Load environment
load_dotenv(dotenv_path=ROOT_DIR / ".env")

# Configuration (matching app.py)
EXPERIMENT = get_experiment("by_type")
CHROMA_DIR = str(EXPERIMENT.chroma_dir)
COLLECTION_NAME = EXPERIMENT.collection_name
EMBEDDING_MODEL = "models/gemini-embedding-001"
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


def load_rag_system():
    """Initialize the RAG system components."""
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment.")

    embeddings = GeminiDualTaskEmbeddings(google_api_key)
    
    vectorstore = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME
    )
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.3,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    return vectorstore, llm


def retrieve_and_generate(question: str, vectorstore, llm, top_k: int = 4, fetch_k: int = 20):
    """
    Retrieve relevant documents and generate an answer.
    Returns both the answer and the retrieved documents.
    """
    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": top_k,
            "fetch_k": max(fetch_k, top_k),
            "lambda_mult": 0.5,
        },
    )
    documents = retriever.invoke(question)

    if not documents:
        return "No relevant research found.", []

    # Build context
    context_parts = []
    for i, doc in enumerate(documents, 1):
        source = str(doc.metadata.get('filename') or doc.metadata.get('source') or 'Unknown').replace('.pdf', '')
        context_parts.append(f"Source {i} ({source}):\n{doc.page_content}")
    
    context = "\n\n".join(context_parts)
    
    # Generate answer
    human_message = f"""CONTEXT (Research Abstracts):
{context}

USER QUERY: {question}

Based on the above research context, provide an actionable wellness plan following the exact output format specified."""
    
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=human_message)
    ]
    
    response = llm.invoke(messages)
    
    return response.content, documents


def run_evaluation_example():
    """Run a complete evaluation example."""
    print("=" * 70)
    print("RAG EVALUATION TEST")
    print("=" * 70)
    
    # Load RAG system
    print("\n[1/5] Loading RAG system...")
    vectorstore, llm = load_rag_system()
    print("✓ RAG system loaded")
    
    # Define test case
    test_question = "How can I improve my sleep quality as a college student?"
    ground_truth = "Maintain a consistent sleep schedule, avoid screens before bed, keep your bedroom cool and dark, and practice relaxation techniques."
    
    print(f"\n[2/5] Test Question: {test_question}")
    
    # Retrieve and generate
    print("\n[3/5] Retrieving documents and generating answer...")
    answer, documents = retrieve_and_generate(
        question=test_question,
        vectorstore=vectorstore,
        llm=llm,
        top_k=4
    )
    
    print(f"\n✓ Retrieved {len(documents)} documents")
    print(f"✓ Generated answer ({len(answer)} chars)")
    
    # Prepare evaluation inputs
    inputs = {"question": test_question}
    outputs = {"answer": answer, "documents": documents}
    reference_outputs = {"answer": ground_truth}
    
    # Run evaluations
    print("\n[4/5] Running evaluations...")
    print("-" * 70)
    
    print("\n📊 METRIC 1: Retrieval Relevance (Are retrieved docs relevant?)")
    retrieval_score = retrieval_relevance(inputs, outputs)
    print(f"   Result: {'✓ PASS' if retrieval_score else '✗ FAIL'}")
    
    print("\n📊 METRIC 2: Groundedness (Is answer grounded in docs?)")
    groundedness_score = groundedness(inputs, outputs)
    print(f"   Result: {'✓ PASS' if groundedness_score else '✗ FAIL'}")
    
    print("\n📊 METRIC 3: Relevance (Does answer address question?)")
    relevance_score = relevance(inputs, outputs)
    print(f"   Result: {'✓ PASS' if relevance_score else '✗ FAIL'}")
    
    print("\n📊 METRIC 4: Correctness (Is answer factually correct?)")
    correctness_score = correctness(inputs, outputs, reference_outputs)
    print(f"   Result: {'✓ PASS' if correctness_score else '✗ FAIL'}")
    
    # Summary
    print("\n[5/5] Evaluation Summary")
    print("-" * 70)
    total_score = sum([retrieval_score, groundedness_score, relevance_score, correctness_score])
    print(f"Overall Score: {total_score}/4 ({total_score/4*100:.0f}%)")
    
    print("\n" + "=" * 70)
    print("DETAILED OUTPUT")
    print("=" * 70)
    
    print("\n📄 RETRIEVED DOCUMENTS:")
    for i, doc in enumerate(documents, 1):
        print(f"\n--- Document {i} ---")
        print(f"Source: {doc.metadata.get('filename') or doc.metadata.get('source', 'Unknown')}")
        print(f"Category: {doc.metadata.get('category', 'Unknown')}")
        print(f"Content: {doc.page_content[:200]}...")
    
    print("\n💬 GENERATED ANSWER:")
    print(answer)
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_evaluation_example()
