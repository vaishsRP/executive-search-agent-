"""LLM-driven candidate analysis using the Groq API.

The single public function :func:`analyse_candidate` sends a job description
and CV to a Groq-hosted model and returns a strictly-shaped dictionary the
Streamlit UI can render without further validation logic.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import Groq

# Load .env at import time so deployment environments and local runs behave
# identically: the variable is read once and cached in os.environ.
load_dotenv()

# Default to a capable, low-latency Groq-hosted model. Operators can override
# via the GROQ_MODEL environment variable without touching code.
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


SYSTEM_PROMPT = """You are an expert executive search consultant and talent assessor.
You evaluate candidates against job descriptions for senior, leadership and
specialist roles. You are precise, evidence-driven and never invent
qualifications the CV does not state.

You MUST respond with a single valid JSON object only. No markdown fences,
no preamble, no trailing commentary. Every required field must be present.
"""


JSON_SCHEMA_INSTRUCTION = """Return ONLY a JSON object with EXACTLY this shape:

{
  "candidate_label": string,
  "role_title": string,
  "seniority_level": string,
  "required_skills": [string, ...],
  "nice_to_have_skills": [string, ...],
  "red_flags": [string, ...],
  "scores": {
    "technical_benchmarks":   {"score": integer 1-10, "reasoning": string (max 2 sentences)},
    "leadership_context":     {"score": integer 1-10, "reasoning": string (max 2 sentences)},
    "soft_signals_culture":   {"score": integer 1-10, "reasoning": string (max 2 sentences)},
    "growth_potential":       {"score": integer 1-10, "reasoning": string (max 2 sentences)}
  },
  "overall_match": integer 1-100,
  "shortlist_recommendation": "Strong Yes" | "Yes" | "Maybe" | "No",
  "top_3_strengths": [string, string, string],
  "top_3_gaps": [string, string, string],
  "missing_information": [
    {"gap": string, "question": string}
  ],
  "internal_notes_bullets": string
}

Rules:
- "required_skills" and "nice_to_have_skills" come from the JD, not the CV.
- "red_flags" are concrete concerns visible in the CV (gaps, job-hopping, mismatched level, etc).
- Scores must be integers between 1 and 10 inclusive. Reasoning is grounded in the CV.
- "overall_match" is an integer 1-100 reflecting end-to-end fit against the JD.
- "shortlist_recommendation" MUST be one of: "Strong Yes", "Yes", "Maybe", "No".
- "top_3_strengths" and "top_3_gaps" each contain exactly 3 short bullet-style strings.
- "missing_information" lists concrete unknowns and the interview question that would resolve each.
- "internal_notes_bullets" is a plain text string of at most 6 bullets, each prefixed with "\\n\\u2022 " (newline + bullet + space).
- Return ONLY the JSON object. No code fences, no explanation.
"""


def _strip_code_fences(raw: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers if the model added them."""
    cleaned = raw.strip()
    # Remove triple-backtick fences with optional language tag.
    fenced = re.match(r"^```(?:json|JSON)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    return cleaned


def _extract_json_object(raw: str) -> str:
    """Best-effort extraction of the first balanced JSON object in ``raw``.

    Some models occasionally prepend an apology or a header line despite
    being told not to. This finds the first '{' and walks to the matching
    '}' so we can still parse the payload.
    """
    start = raw.find("{")
    if start == -1:
        return raw
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start : i + 1]
    return raw


def analyse_candidate(jd_text: str, cv_text: str, candidate_label: str) -> dict:
    """Analyse a single candidate against a job description.

    Parameters
    ----------
    jd_text:
        The full job description as plain text.
    cv_text:
        The candidate's CV as plain text (already extracted from any PDF).
    candidate_label:
        A human-friendly identifier for the candidate, e.g. "Jane Doe".

    Returns
    -------
    dict
        A dictionary matching the schema described in
        :data:`JSON_SCHEMA_INSTRUCTION`. On any failure path the returned
        dictionary contains an ``"error"`` key and, where possible, a
        ``"raw"`` key containing the unparsed model response so the UI can
        show the operator what actually came back.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {
            "error": (
                "GROQ_API_KEY is not set. Copy .env.example to .env and add "
                "your key, or export GROQ_API_KEY in your shell."
            ),
            "raw": "",
            "candidate_label": candidate_label,
        }

    if not jd_text or not jd_text.strip():
        return {
            "error": "Job description is empty.",
            "raw": "",
            "candidate_label": candidate_label,
        }
    if not cv_text or not cv_text.strip():
        return {
            "error": "Candidate CV is empty.",
            "raw": "",
            "candidate_label": candidate_label,
        }

    user_prompt = (
        f"Candidate label: {candidate_label}\n\n"
        f"=== JOB DESCRIPTION ===\n{jd_text}\n\n"
        f"=== CANDIDATE CV ===\n{cv_text}\n\n"
        f"{JSON_SCHEMA_INSTRUCTION}"
    )

    raw_response = ""
    try:
        client = Groq(api_key=api_key)
        # response_format with json_object asks Groq to constrain output to
        # valid JSON. We still defensively strip fences as a belt-and-braces.
        completion = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=2048,
            response_format={"type": "json_object"},
        )
        raw_response = completion.choices[0].message.content or ""
    except Exception as exc:
        return {
            "error": f"Groq API call failed: {exc}",
            "raw": raw_response,
            "candidate_label": candidate_label,
        }

    cleaned = _strip_code_fences(raw_response)
    cleaned = _extract_json_object(cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return {
            "error": f"Failed to parse model response as JSON: {exc}",
            "raw": raw_response,
            "candidate_label": candidate_label,
        }

    if not isinstance(parsed, dict):
        return {
            "error": "Model response was valid JSON but not an object.",
            "raw": raw_response,
            "candidate_label": candidate_label,
        }

    # Force the candidate_label to the value the operator typed, so even if the
    # model invents a name from the CV it stays consistent in the UI.
    parsed["candidate_label"] = candidate_label
    return _normalise_result(parsed)


def _normalise_result(result: dict) -> dict:
    """Fill in any missing keys with safe defaults so the UI never KeyErrors."""
    result.setdefault("role_title", "")
    result.setdefault("seniority_level", "")
    result.setdefault("required_skills", [])
    result.setdefault("nice_to_have_skills", [])
    result.setdefault("red_flags", [])
    result.setdefault("top_3_strengths", [])
    result.setdefault("top_3_gaps", [])
    result.setdefault("missing_information", [])
    result.setdefault("internal_notes_bullets", "")
    result.setdefault("shortlist_recommendation", "Maybe")

    overall = result.get("overall_match", 0)
    try:
        result["overall_match"] = int(overall)
    except (TypeError, ValueError):
        result["overall_match"] = 0

    scores = result.get("scores") or {}
    for dim in (
        "technical_benchmarks",
        "leadership_context",
        "soft_signals_culture",
        "growth_potential",
    ):
        block: Any = scores.get(dim) or {}
        if not isinstance(block, dict):
            block = {}
        try:
            block["score"] = int(block.get("score", 0))
        except (TypeError, ValueError):
            block["score"] = 0
        block.setdefault("reasoning", "")
        scores[dim] = block
    result["scores"] = scores

    return result
