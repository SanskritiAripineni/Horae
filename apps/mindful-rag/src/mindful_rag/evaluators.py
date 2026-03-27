"""
RAGAS-style LLM-judge evaluators using Gemini.

Each function returns {"score": float, "reasoning": str} where score is in [0, 1].
The GOOGLE_API_KEY environment variable must be set before calling these functions
(rigorous_eval.py handles this via os.environ["GOOGLE_API_KEY"] = api_key).
"""

from __future__ import annotations

import json
import os
import re

from google import genai


def _client() -> genai.Client:
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GOOGLE_API_KEY or GEMINI_API_KEY must be set.")
    return genai.Client(api_key=api_key)


_JUDGE_MODEL = "gemini-2.5-flash"


def _parse_score(text: str) -> tuple[float, str]:
    """Extract score and reasoning from a judge response."""
    score = 0.0
    reasoning = text.strip()

    # Look for a JSON block first
    json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if json_match:
        try:
            obj = json.loads(json_match.group())
            if "score" in obj:
                score = float(obj["score"])
                reasoning = str(obj.get("reasoning", reasoning))
                return max(0.0, min(1.0, score)), reasoning
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback: find first float/int 0-1 pattern
    num_match = re.search(r"\b(0(?:\.\d+)?|1(?:\.0+)?)\b", text)
    if num_match:
        score = float(num_match.group())
        score = max(0.0, min(1.0, score))

    return score, reasoning


def _call_judge(prompt: str) -> dict:
    """Call the Gemini judge and parse the response."""
    try:
        response = _client().models.generate_content(
            model=_JUDGE_MODEL, contents=prompt
        )
        text = response.text or ""
        score, reasoning = _parse_score(text)
        return {"score": round(score, 4), "reasoning": reasoning}
    except Exception as exc:  # noqa: BLE001
        return {"score": 0.0, "reasoning": f"Evaluation failed: {exc}"}


# ── Public evaluators ────────────────────────────────────────────────────────


def faithfulness(query_text: str, answer: str, chunks: list[dict]) -> dict:
    """
    Score how faithfully the answer is grounded in the retrieved chunks.
    Returns {"score": float, "reasoning": str}.
    """
    context = "\n\n---\n\n".join(
        f"Source: {c.get('source', 'Unknown')}\n{c.get('content', '')[:1500]}"
        for c in chunks
    )
    prompt = f"""You are an impartial judge evaluating a RAG system.

QUESTION: {query_text}

RETRIEVED CONTEXT:
{context}

GENERATED ANSWER:
{answer}

Evaluate how faithfully the answer is grounded in the retrieved context.
A score of 1.0 means every claim in the answer is supported by the context.
A score of 0.0 means the answer contains claims not supported by the context.

Respond with JSON only:
{{"score": <float 0-1>, "reasoning": "<one sentence>"}}"""
    return _call_judge(prompt)


def context_relevance(query_text: str, chunks: list[dict]) -> dict:
    """
    Score how relevant the retrieved chunks are to the query.
    Returns {"score": float, "reasoning": str}.
    """
    excerpts = "\n\n---\n\n".join(
        f"[{i+1}] {c.get('content', '')[:800]}" for i, c in enumerate(chunks)
    )
    prompt = f"""You are an impartial judge evaluating a RAG retrieval system.

QUESTION: {query_text}

RETRIEVED CHUNKS:
{excerpts}

Score how relevant the retrieved chunks are for answering the question.
1.0 = all chunks are highly relevant; 0.0 = all chunks are irrelevant.

Respond with JSON only:
{{"score": <float 0-1>, "reasoning": "<one sentence>"}}"""
    return _call_judge(prompt)


def answer_relevance(query_text: str, answer: str) -> dict:
    """
    Score how directly and completely the answer addresses the query.
    Returns {"score": float, "reasoning": str}.
    """
    prompt = f"""You are an impartial judge evaluating a RAG system.

QUESTION: {query_text}

GENERATED ANSWER:
{answer}

Score how relevant and on-topic the answer is to the question.
1.0 = the answer directly and completely addresses the question.
0.0 = the answer is off-topic or does not address the question at all.

Respond with JSON only:
{{"score": <float 0-1>, "reasoning": "<one sentence>"}}"""
    return _call_judge(prompt)


def response_completeness(query_text: str, answer: str, chunks: list[dict]) -> dict:
    """
    Score how complete the answer is given the available context.
    Returns {"score": float, "reasoning": str}.
    """
    context = "\n\n---\n\n".join(
        f"Source: {c.get('source', 'Unknown')}\n{c.get('content', '')[:1500]}"
        for c in chunks
    )
    prompt = f"""You are an impartial judge evaluating a RAG system.

QUESTION: {query_text}

RETRIEVED CONTEXT:
{context}

GENERATED ANSWER:
{answer}

Score how completely the answer covers the key information available in the context
that is relevant to the question.
1.0 = the answer covers all key relevant information from the context.
0.0 = the answer omits most key relevant information available in the context.

Respond with JSON only:
{{"score": <float 0-1>, "reasoning": "<one sentence>"}}"""
    return _call_judge(prompt)
