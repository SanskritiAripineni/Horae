import json
import os
import re

from google import genai


# ---------------------------------------------------------
# SETUP: Model Configuration
# ---------------------------------------------------------
EVALUATOR_MODEL = "gemini-2.5-flash"
_GENAI_CLIENT = None


def _get_genai_client():
    """Create (once) and return a Google GenAI client."""
    global _GENAI_CLIENT
    if _GENAI_CLIENT is None:
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment.")
        _GENAI_CLIENT = genai.Client(api_key=google_api_key)
    return _GENAI_CLIENT


def _extract_json_object(text: str) -> dict:
    """Extract a JSON object from model text output."""
    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _grade_boolean(instructions: str, payload: str, field_name: str) -> bool:
    """Run one evaluator prompt and return a boolean verdict."""
    prompt = f"""{instructions}

Return ONLY a valid JSON object with exactly these fields:
- "explanation": string
- "{field_name}": boolean

INPUT:
{payload}
"""
    response = _get_genai_client().models.generate_content(
        model=EVALUATOR_MODEL,
        contents=prompt,
    )
    text = response.text if getattr(response, "text", None) else ""
    grade = _extract_json_object(text)

    if field_name not in grade:
        raise ValueError(f"Evaluator response missing field '{field_name}': {grade}")
    return bool(grade[field_name])


# ---------------------------------------------------------
# METRIC 1: CORRECTNESS (Answer vs Ground Truth)
# ---------------------------------------------------------
correctness_instructions = """You are a teacher grading a quiz. You will be given a QUESTION, the GROUND TRUTH (correct) ANSWER, and the STUDENT ANSWER. Here is the grade criteria to follow:
(1) Grade the student answers based ONLY on their factual accuracy relative to the ground truth answer. (2) Ensure that the student answer does not contain any conflicting statements.
(3) It is OK if the student answer contains more information than the ground truth answer, as long as it is factually accurate relative to the  ground truth answer.

Correctness:
A correctness value of True means that the student's answer meets all of the criteria.
A correctness value of False means that the student's answer does not meet all of the criteria.

Explain your reasoning in a step-by-step manner to ensure your reasoning and conclusion are correct. Avoid simply stating the correct answer at the outset."""


def correctness(inputs: dict, outputs: dict, reference_outputs: dict) -> bool:
    """An evaluator for RAG answer accuracy."""
    answers = f"""\
QUESTION: {inputs['question']}
GROUND TRUTH ANSWER: {reference_outputs['answer']}
STUDENT ANSWER: {outputs['answer']}"""
    return _grade_boolean(correctness_instructions, answers, "correct")


# ---------------------------------------------------------
# METRIC 2: RELEVANCE (Answer vs Question)
# ---------------------------------------------------------
relevance_instructions = """You are a teacher grading a quiz. You will be given a QUESTION and a STUDENT ANSWER. Here is the grade criteria to follow:
(1) Ensure the STUDENT ANSWER is concise and relevant to the QUESTION
(2) Ensure the STUDENT ANSWER helps to answer the QUESTION

Relevance:
A relevance value of True means that the student's answer meets all of the criteria.
A relevance value of False means that the student's answer does not meet all of the criteria.

Explain your reasoning in a step-by-step manner to ensure your reasoning and conclusion are correct. Avoid simply stating the correct answer at the outset."""


def relevance(inputs: dict, outputs: dict) -> bool:
    """A simple evaluator for RAG answer helpfulness."""
    answer = f"QUESTION: {inputs['question']}\nSTUDENT ANSWER: {outputs['answer']}"
    return _grade_boolean(relevance_instructions, answer, "relevant")


# ---------------------------------------------------------
# METRIC 3: GROUNDEDNESS (Answer vs Retrieved Docs)
# ---------------------------------------------------------
grounded_instructions = """You are a teacher grading a quiz. You will be given FACTS and a STUDENT ANSWER. Here is the grade criteria to follow:
(1) Ensure the STUDENT ANSWER is grounded in the FACTS. (2) Ensure the STUDENT ANSWER does not contain "hallucinated" information outside the scope of the FACTS.

Grounded:
A grounded value of True means that the student's answer meets all of the criteria.
A grounded value of False means that the student's answer does not meet all of the criteria.

Explain your reasoning in a step-by-step manner to ensure your reasoning and conclusion are correct. Avoid simply stating the correct answer at the outset."""


def groundedness(inputs: dict, outputs: dict) -> bool:
    """A simple evaluator for RAG answer groundedness."""
    doc_string = "\n\n".join(doc.page_content for doc in outputs["documents"])
    answer = f"FACTS: {doc_string}\nSTUDENT ANSWER: {outputs['answer']}"
    return _grade_boolean(grounded_instructions, answer, "grounded")


# ---------------------------------------------------------
# METRIC 4: RETRIEVAL RELEVANCE (Retrieved Docs vs Question)
# ---------------------------------------------------------
retrieval_relevance_instructions = """You are a teacher grading a quiz. You will be given a QUESTION and a set of FACTS provided by the student. Here is the grade criteria to follow:
(1) You goal is to identify FACTS that are completely unrelated to the QUESTION
(2) If the facts contain ANY keywords or semantic meaning related to the question, consider them relevant
(3) It is OK if the facts have SOME information that is unrelated to the question as long as (2) is met

Relevance:
A relevance value of True means that the FACTS contain ANY keywords or semantic meaning related to the QUESTION and are therefore relevant.
A relevance value of False means that the FACTS are completely unrelated to the QUESTION.

Explain your reasoning in a step-by-step manner to ensure your reasoning and conclusion are correct. Avoid simply stating the correct answer at the outset."""


def retrieval_relevance(inputs: dict, outputs: dict) -> bool:
    """An evaluator for document relevance."""
    doc_string = "\n\n".join(doc.page_content for doc in outputs["documents"])
    answer = f"FACTS: {doc_string}\nQUESTION: {inputs['question']}"
    return _grade_boolean(retrieval_relevance_instructions, answer, "relevant")
