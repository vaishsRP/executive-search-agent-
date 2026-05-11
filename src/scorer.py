from collections import Counter


def rank_candidates(results):
    """sort by overall_match desc and tag each with a rank."""
    def score(item):
        try:
            return int(item.get("overall_match", 0) or 0)
        except (TypeError, ValueError):
            return 0

    ordered = sorted(results, key=score, reverse=True)
    for idx, item in enumerate(ordered, start=1):
        item["rank"] = idx
    return ordered


def compute_summary(ranked):
    """best candidate, most common gap, first interview question from the top one."""
    summary = {
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

    # count gaps case-insensitively but keep the original spelling for display
    counter = Counter()
    display = {}
    for cand in valid:
        for gap in cand.get("top_3_gaps") or []:
            if not gap:
                continue
            key = gap.strip().lower()
            counter[key] += 1
            display.setdefault(key, gap.strip())
    if counter:
        most_common_key, _ = counter.most_common(1)[0]
        summary["common_gap"] = display[most_common_key]

    missing = top.get("missing_information") or []
    if missing and isinstance(missing[0], dict):
        summary["first_interview_question"] = missing[0].get("question", "")
    return summary
