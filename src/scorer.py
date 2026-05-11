"""Ranking and summary helpers for the shortlist mode."""

from __future__ import annotations

from collections import Counter
from typing import Any


def rank_candidates(results: list[dict]) -> list[dict]:
    """Sort candidate analysis dicts by ``overall_match`` descending.

    Parameters
    ----------
    results:
        A list of analysis dicts as returned by ``analyser.analyse_candidate``.
        Entries that errored (contain an ``"error"`` key) are still sorted but
        treated as having a match score of 0.

    Returns
    -------
    list[dict]
        The same dicts, sorted highest-match first, with a new integer
        ``"rank"`` key (1-based) added in place.
    """
    def _score(item: dict) -> int:
        try:
            return int(item.get("overall_match", 0) or 0)
        except (TypeError, ValueError):
            return 0

    ordered = sorted(results, key=_score, reverse=True)
    for idx, item in enumerate(ordered, start=1):
        item["rank"] = idx
    return ordered


def compute_summary(ranked: list[dict]) -> dict:
    """Produce a small insight panel summarising a ranked shortlist.

    Parameters
    ----------
    ranked:
        Output of :func:`rank_candidates`.

    Returns
    -------
    dict
        ``best_candidate``: name of the top-ranked candidate (or empty string).
        ``best_reason``: their first strength, framed as the headline reason.
        ``common_gap``: the most frequently mentioned gap across all candidates.
        ``first_interview_question``: the first missing-information question
        from the top candidate, ready to copy into an interview brief.
    """
    summary: dict[str, Any] = {
        "best_candidate": "",
        "best_reason": "",
        "common_gap": "",
        "first_interview_question": "",
    }

    valid = [r for r in ranked if "error" not in r]
    if not valid:
        return summary

    top = valid[0]
    summary["best_candidate"] = top.get("candidate_label", "")
    strengths = top.get("top_3_strengths") or []
    if strengths:
        summary["best_reason"] = strengths[0]

    # Find the most common gap across all candidates. We normalise to
    # lower-case for counting but display the original-cased version.
    gap_counter: Counter[str] = Counter()
    display_form: dict[str, str] = {}
    for cand in valid:
        for gap in cand.get("top_3_gaps") or []:
            if not gap:
                continue
            key = gap.strip().lower()
            gap_counter[key] += 1
            display_form.setdefault(key, gap.strip())
    if gap_counter:
        most_common_key, _ = gap_counter.most_common(1)[0]
        summary["common_gap"] = display_form[most_common_key]

    missing = top.get("missing_information") or []
    if missing and isinstance(missing[0], dict):
        summary["first_interview_question"] = missing[0].get("question", "")

    return summary
