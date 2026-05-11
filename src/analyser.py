import json
import os
import re

import json_repair
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

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
- "red_flags" are concrete concerns visible in the CV.
- Scores are integers 1 to 10. Reasoning is grounded in the CV.
- "overall_match" is an integer 1 to 100.
- "shortlist_recommendation" MUST be one of: "Strong Yes", "Yes", "Maybe", "No".
- "top_3_strengths" and "top_3_gaps" each contain exactly 3 short strings.
- "missing_information" lists concrete unknowns and the interview question that would resolve each.
- "internal_notes_bullets" is a plain text string of at most 6 bullets, each prefixed with "\\n\\u2022 ".
- Return ONLY the JSON object. No code fences, no explanation.
"""


def _strip_code_fences(raw):
    cleaned = raw.strip()
    fenced = re.match(r"^```(?:json|JSON)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    return cleaned


def _extract_json_object(raw):
    # walk to the first balanced {...} in case the model adds a prefix
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


def _repair_brackets(s):
    # fix mismatched ]/} closers by reconciling against a stack of openers.
    # llama sometimes closes a dict with ] or a list with }, which is enough
    # to make json.loads (and groq's server-side validator) reject the whole
    # response. this swaps the wrong closer for the expected one.
    out = []
    stack = []
    in_string = False
    escape = False
    for ch in s:
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
        elif ch == "{":
            stack.append("}")
            out.append(ch)
        elif ch == "[":
            stack.append("]")
            out.append(ch)
        elif ch in ("}", "]"):
            if stack:
                expected = stack.pop()
                out.append(expected)
            else:
                out.append(ch)
        else:
            out.append(ch)
    return "".join(out)


def _extract_failed_generation(exc):
    # groq returns 400 with the raw model text under error.failed_generation
    # when response_format=json_object validation fails server-side.
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error") or {}
        if err.get("code") == "json_validate_failed":
            return err.get("failed_generation")
    return None


def analyse_candidate(jd_text, cv_text, candidate_label):
    """send jd + cv to groq, return a dict with scores and gaps."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {
            "error": "GROQ_API_KEY not set. locally: copy .env.example to .env and add your key. on streamlit cloud: add GROQ_API_KEY in Settings > Secrets.",
            "raw": "",
            "candidate_label": candidate_label,
        }
    if not jd_text or not jd_text.strip():
        return {"error": "job description is empty.", "raw": "", "candidate_label": candidate_label}
    if not cv_text or not cv_text.strip():
        return {"error": "candidate cv is empty.", "raw": "", "candidate_label": candidate_label}

    user_prompt = (
        f"Candidate label: {candidate_label}\n\n"
        f"=== JOB DESCRIPTION ===\n{jd_text}\n\n"
        f"=== CANDIDATE CV ===\n{cv_text}\n\n"
        f"{JSON_SCHEMA_INSTRUCTION}"
    )

    raw_response = ""
    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        raw_response = completion.choices[0].message.content or ""
    except Exception as exc:
        # if groq rejected the response for failing its own json validator,
        # the model text is still inside the error body. try to salvage it.
        salvaged = _extract_failed_generation(exc)
        if salvaged:
            raw_response = salvaged
        else:
            return {
                "error": f"groq api call failed: {exc}",
                "raw": raw_response,
                "candidate_label": candidate_label,
            }

    cleaned = _strip_code_fences(raw_response)
    cleaned = _extract_json_object(cleaned)

    parsed = None
    # try plain parse, then our bracket-swap repair, then json_repair (handles
    # truncation, missing commas, unescaped quotes, the usual llm json sins).
    for attempt in (cleaned, _repair_brackets(cleaned)):
        try:
            parsed = json.loads(attempt)
            break
        except json.JSONDecodeError:
            continue
    if parsed is None:
        try:
            parsed = json_repair.loads(cleaned)
        except Exception:
            parsed = None
    if not isinstance(parsed, dict):
        return {
            "error": "couldn't parse model response as json after repair.",
            "raw": raw_response,
            "candidate_label": candidate_label,
        }

    # force the label so the model can't override what the user typed
    parsed["candidate_label"] = candidate_label
    return _normalise_result(parsed)


def _normalise_result(result):
    # fill missing keys so the ui never crashes on a KeyError
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

    try:
        result["overall_match"] = int(result.get("overall_match", 0))
    except (TypeError, ValueError):
        result["overall_match"] = 0

    scores = result.get("scores") or {}
    for dim in ("technical_benchmarks", "leadership_context", "soft_signals_culture", "growth_potential"):
        block = scores.get(dim) or {}
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
