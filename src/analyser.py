import json
import math
import os
import re

import json_repair
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


SYSTEM_PROMPT = """### ROLE
You are a Talent Auditor. You evaluate candidates against a specific Job Description (JD) across the full seniority range — internships, fresher / student-worker roles, individual-contributor positions, mid-level, senior, leadership, and C-suite / executive search. The bar for what counts as "strong evidence" MUST scale to the level the JD is hiring for. Do not impose a senior-leadership bar on an intern. Do not accept coursework or hackathon evidence as proof of executive readiness.

### EVALUATION RUBRIC (STRICT ADHERENCE REQUIRED)
1.  **Calibrate to the JD's Seniority Level First.** Before scoring, decide what level the JD is hiring for (intern / fresher / junior IC / mid / senior / leadership / executive) and use it to set the bar for every dimension. Record it in `seniority_level`. This single decision drives the rest of the audit.
2.  **Evidence-Based Scoring, Calibrated to Level.** A score of 5/10 is "Average Fit." 8/10+ requires explicit, level-appropriate evidence:
    - Intern / fresher: relevant projects, internships, coursework, hackathons, open-source (e.g., "shipped a Flask app used by 200 students," "GPA 3.8 in CS," "top 5 in regional hackathon").
    - Mid-level IC: shipped production systems with measurable scope (e.g., "owned the billing service through three major releases," "cut p95 latency by 40%").
    - Senior / leadership: team ownership, cross-functional outcomes, mentoring (e.g., "led a team of 6 through reorg," "drove a $3M ARR initiative").
    - Executive: P&L, org-level strategy, multi-year outcomes, board-level work (e.g., "doubled revenue over 3 years," "scaled org from 20 to 150").
    Generic claims like "passionate learner," "strong leader," or "strategic thinker" do NOT clear 8/10 at any level.
3.  **The "Gap" Priority — Relative to THIS JD.** Penalize what is missing relative to what this JD asks for. If the JD requires it and the CV does not demonstrate it, that dimension MUST be penalized. Do NOT penalize for senior signal an intern role does not require. Do NOT penalize for entry-level signal a senior role does not require.
4.  **Anti-Inflation Clause:** Do not default to 80% or 20%. If the candidate is a partial match, stay in the 40-60% range. Use the full 1-100 scale.
5.  **No Hallucinations:** Do not infer skills the CV does not state. A school name does not imply framework knowledge. A job title does not imply scope. A club office does not imply leadership. Mark unstated requirements as a Gap or Red Flag.

### STEP-BY-STEP ANALYSIS PROCESS (Internal Monologue)
- Step 1: Read the JD and pin its seniority level — this sets the bar for every dimension that follows.
- Step 2: Identify "Hard Constraints" in the JD (must-have skills, tools, qualifications, experience minimums) at that level.
- Step 3: Search the CV for specific evidence of those constraints — projects/coursework for early-career, shipped systems for IC, strategic outcomes and org scope for leadership / exec.
- Step 4: Identify "Soft Signals" (communication style, ownership, initiative, cultural fit indicators).
- Step 5: Assess trajectory at the right scale — coursework / project complexity for early-career, scope-of-ownership growth for IC, organizational impact growth for leadership / exec. Is the candidate growing fast enough for THIS role?
- Step 6: Draft the JSON response based on these objective findings.

You MUST respond with a single valid JSON object only. No markdown fences,
no preamble, no trailing commentary. Every required field must be present.
"""


JSON_SCHEMA_INSTRUCTION = """### OUTPUT INSTRUCTIONS
- Return ONLY valid JSON.
- No markdown formatting (no ```json).
- No preamble or "Here is the analysis."
- Use the exact keys requested below.

### REQUIRED JSON STRUCTURE
{
    "candidate_label": "<exact candidate name from DATA section>",
    "role_title": "Clean version of the target role",
    "seniority_level": "",
    "required_skills": ["List only skills explicitly found in both"],
    "nice_to_have_skills": ["List desired skills from JD found in CV"],
    "red_flags": ["Concerns relative to THIS role's level — missing prerequisite skills, unexplained gaps, very short tenures, claimed skills with no evidence, level mismatch (over- or under-qualified for the JD)"],
    "scores": {
        "technical_benchmarks": {
            "score": 1-10,
            "reasoning": "Match against the JD's must-have technical skills, with evidence calibrated to the JD's level (coursework/projects for intern, shipped systems for IC, architecture/platform strategy for senior+). Be blunt about gaps."
        },
        "leadership_context": {
            "score": 1-10,
            "reasoning": "Ownership and leadership evidence relative to the JD's level — intern: TA, club office, team-project lead, hackathon captain; IC/mid: project ownership, mentoring juniors; senior/leadership: team management, cross-functional drive; executive: P&L, org-level strategy, board-level work. Score against what THIS role demands; do not penalize missing exec scope on an intern role or vice versa."
        },
        "soft_signals_culture": {
            "score": 1-10,
            "reasoning": "Communication style, ownership signals, and cultural match based on CV tone and the roles/projects the candidate chose to pursue."
        },
        "growth_potential": {
            "score": 1-10,
            "reasoning": "Trajectory calibrated to level — coursework/project progression for early-career, scope-of-ownership growth for IC/mid, organizational impact growth for senior+. Is this candidate growing fast enough for the role's demands?"
        }
    },
    "overall_match": 1-100,
    "shortlist_recommendation": "Strong Yes / Yes / Maybe / No",
    "top_3_strengths": ["Must be unique and evidence-based"],
    "top_3_gaps": ["Crucial missing components"],
    "missing_information": [
        {
            "gap": "What is unclear",
            "question": "The specific question to ask in a screening call to verify this."
        }
    ],
    "internal_notes_bullets": "\\n\\u2022 First point\\n\\u2022 Second point (Max 6 points total)"
}

Rules:
- "shortlist_recommendation" MUST be exactly one of: "Strong Yes", "Yes", "Maybe", "No".
- "top_3_strengths" and "top_3_gaps" each contain exactly 3 short strings.
- Scores are integers 1 to 10. "overall_match" is an integer 1 to 100.
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
        f"### DATA\n"
        f"CANDIDATE NAME: {candidate_label}\n\n"
        f"JOB DESCRIPTION:\n{jd_text}\n\n"
        f"CANDIDATE CV:\n{cv_text}\n\n"
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


def _sanity_check_overall_match(model_overall, scores):
    # the model returns overall_match as a holistic judgment, but it sometimes
    # diverges wildly from the four dimension scores. clamp to +/-15 of the
    # simple average so red-flag/seniority weighting still has room (~1.5 avg
    # score points) without letting the headline score drift into nonsense.
    dim_scores = [block.get("score", 0) for block in scores.values()]
    if not dim_scores or not any(dim_scores):
        return max(1, min(100, model_overall))
    baseline = sum(dim_scores) / 40 * 100
    tolerance = 15
    clamped = max(baseline - tolerance, min(baseline + tolerance, model_overall))
    clamped = max(1, min(100, clamped))
    return min(100, math.ceil(clamped / 5) * 5)


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
        raw_overall = int(result.get("overall_match", 0))
    except (TypeError, ValueError):
        raw_overall = 0

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

    result["overall_match"] = _sanity_check_overall_match(raw_overall, scores)
    return result
