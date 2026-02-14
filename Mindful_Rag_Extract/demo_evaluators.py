"""
Quick Demo of Evaluation Metrics
---------------------------------
This demonstrates the evaluators without loading the full RAG system.
"""

from dotenv import load_dotenv
load_dotenv()  # Load OpenAI API key from .env

from evaluators import correctness, relevance, groundedness, retrieval_relevance
from langchain.schema import Document

print("=" * 70)
print("RAG EVALUATION METRICS - QUICK DEMO")
print("=" * 70)

# Sample data
question = "How can I improve my sleep quality?"

# Simulated retrieved documents
doc1 = Document(
    page_content="Sleep hygiene practices include maintaining a consistent sleep schedule, avoiding screens before bedtime, keeping the bedroom cool and dark, and practicing relaxation techniques.",
    metadata={"source": "sleep_hygiene_protocol.pdf", "category": "Sleep Hygiene"}
)

doc2 = Document(
    page_content="Research shows that cognitive behavioral therapy for insomnia (CBT-I) is effective. Key components include sleep restriction, stimulus control, and sleep hygiene education.",
    metadata={"source": "insomnia_treatment.pdf", "category": "Sleep Hygiene"}
)

doc3 = Document(
    page_content="Blue light from screens suppresses melatonin production. Avoiding screens 1-2 hours before bed can improve sleep onset latency.",
    metadata={"source": "circadian_rhythm.pdf", "category": "Sleep Hygiene"}
)

documents = [doc1, doc2, doc3]

# Generated answer (grounded in docs)
good_answer = "To improve sleep quality, maintain a consistent sleep schedule, avoid screens 1-2 hours before bedtime to prevent blue light from suppressing melatonin, keep your bedroom cool and dark, and practice relaxation techniques. Consider cognitive behavioral therapy for insomnia (CBT-I) which includes sleep restriction and stimulus control."

# Generated answer (hallucinated - NOT in docs)
bad_answer = "Take melatonin supplements every night, drink chamomile tea, and use a weighted blanket. Also, exercise vigorously right before bed to tire yourself out."

# Ground truth
ground_truth = "Maintain a consistent sleep schedule, avoid screens before bed, keep your bedroom cool and dark, and practice relaxation techniques."

print("\n📝 TEST QUESTION:")
print(f"   {question}")

print("\n📚 RETRIEVED DOCUMENTS:")
for i, doc in enumerate(documents, 1):
    print(f"   {i}. {doc.metadata['source']}: {doc.page_content[:80]}...")

# Test with GOOD answer
print("\n" + "=" * 70)
print("TEST 1: GOOD ANSWER (Grounded in documents)")
print("=" * 70)
print(f"\n💬 Answer: {good_answer}")

inputs = {"question": question}
outputs_good = {"answer": good_answer, "documents": documents}
reference = {"answer": ground_truth}

print("\n📊 Evaluation Results:")
print(f"   ✓ Retrieval Relevance: {retrieval_relevance(inputs, outputs_good)}")
print(f"   ✓ Groundedness: {groundedness(inputs, outputs_good)}")
print(f"   ✓ Relevance: {relevance(inputs, outputs_good)}")
print(f"   ✓ Correctness: {correctness(inputs, outputs_good, reference)}")

# Test with BAD answer
print("\n" + "=" * 70)
print("TEST 2: BAD ANSWER (Hallucinated - not in documents)")
print("=" * 70)
print(f"\n💬 Answer: {bad_answer}")

outputs_bad = {"answer": bad_answer, "documents": documents}

print("\n📊 Evaluation Results:")
print(f"   ✓ Retrieval Relevance: {retrieval_relevance(inputs, outputs_bad)}")
print(f"   ✗ Groundedness: {groundedness(inputs, outputs_bad)} (Should be False!)")
print(f"   ✓ Relevance: {relevance(inputs, outputs_bad)}")
print(f"   ? Correctness: {correctness(inputs, outputs_bad, reference)}")

print("\n" + "=" * 70)
print("✅ Demo Complete!")
print("=" * 70)
print("\nKey Takeaway:")
print("- The GOOD answer should pass all metrics")
print("- The BAD answer should FAIL groundedness (hallucinated info)")
print("- This shows how the metrics catch different types of issues")
