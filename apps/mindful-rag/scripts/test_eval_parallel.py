
import logging
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'apps/mindful-rag/src'))

from mindful_rag.evaluators import evaluate_all_sources

# Dummy data
query = "How to improve sleep?"
source_results = [
    {
        "source": "relevant_info",
        "response": "Based on research, establish a consistent sleep schedule and avoid screens before bed.",
        "chunks": [{"content": "Studies show consistent sleep timing aids circadian rhythm.", "filename": "sleep_study.pdf"}]
    },
    {
        "source": "intro_concl",
        "response": "Sleep is good for health.",
        "chunks": [{"content": "Introduction: Sleep is vital.", "filename": "intro.pdf"}]
    }
]

print("Running parallel evaluation...")
try:
    results = evaluate_all_sources(query, source_results)
    print("Evaluation successful!")
    print(results["overview"])
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
