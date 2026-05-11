import io
import json
from html import escape

import pandas as pd
import streamlit as st

from src import analyser, parser, scorer


st.set_page_config(
    page_title="Executive Search Agent",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CUSTOM_CSS = """
<style>
  .esa-title { font-size: 2.2rem; font-weight: 700; margin-bottom: 0.1rem; }
  .esa-subtitle { color: #6b7280; font-size: 1.0rem; margin-bottom: 1.2rem; }
  .esa-pill {
      display: inline-block;
      padding: 4px 10px;
      margin: 2px 4px 2px 0;
      border-radius: 999px;
      font-size: 0.82rem;
      font-weight: 500;
      line-height: 1.3;
  }
  .esa-pill-green  { background: #dcfce7; color: #166534; border: 1px solid #86efac; }
  .esa-pill-blue   { background: #dbeafe; color: #1e40af; border: 1px solid #93c5fd; }
  .esa-pill-red    { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
  .esa-pill-grey   { background: #f3f4f6; color: #374151; border: 1px solid #d1d5db; }
  .esa-badge {
      display: inline-block;
      padding: 6px 14px;
      border-radius: 8px;
      font-weight: 700;
      font-size: 0.95rem;
      color: white;
  }
  .esa-badge-green  { background: #16a34a; }
  .esa-badge-blue   { background: #2563eb; }
  .esa-badge-orange { background: #ea580c; }
  .esa-badge-red    { background: #dc2626; }
  .esa-score-card {
      padding: 12px 14px;
      border-radius: 10px;
      border: 1px solid #e5e7eb;
      background: #ffffff;
      height: 100%;
  }
  .esa-score-card h4 { margin: 0 0 4px 0; font-size: 0.95rem; color: #374151; }
  .esa-score-card .esa-score-value { font-size: 1.9rem; font-weight: 800; color: #111827; }
  .esa-score-card .esa-score-reason { font-size: 0.86rem; color: #4b5563; margin-top: 4px; }
  .esa-section-title { font-size: 1.1rem; font-weight: 700; margin: 0.8rem 0 0.3rem 0; }
  .esa-gap-box {
      background: #fffbeb;
      border: 1px solid #fde68a;
      border-radius: 10px;
      padding: 14px 16px;
      margin-top: 6px;
  }
  .esa-gap-item { margin-bottom: 8px; }
  .esa-gap-item .esa-gap-text { font-style: italic; color: #6b7280; }
  .esa-gap-item .esa-gap-q { font-weight: 600; color: #111827; }
  .esa-bullet-list { margin: 0; padding-left: 1.1rem; }
  .esa-bullet-list li { margin-bottom: 4px; }
  .esa-strengths li { color: #166534; }
  .esa-gaps li { color: #991b1b; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


RECOMMENDATION_BADGE = {
    "Strong Yes": "esa-badge-green",
    "Yes": "esa-badge-blue",
    "Maybe": "esa-badge-orange",
    "No": "esa-badge-red",
}


def render_pills(items, css_class):
    if not items:
        return "<span class='esa-pill esa-pill-grey'>None listed</span>"
    return "".join(
        f"<span class='esa-pill {css_class}'>{escape(str(item))}</span>"
        for item in items
        if item
    )


def render_recommendation_badge(recommendation):
    css = RECOMMENDATION_BADGE.get(recommendation, "esa-pill-grey")
    return f"<span class='esa-badge {css}'>{escape(recommendation or 'Unknown')}</span>"


def copy_to_clipboard_button(label, payload, button_key):
    # json-encode so quotes and newlines round-trip into the inline js safely
    payload_json = json.dumps(payload)
    html = f"""
    <div>
      <button id="{button_key}" style="
          background:#111827;color:#fff;border:none;border-radius:8px;
          padding:8px 14px;font-weight:600;cursor:pointer;width:100%;">
        {escape(label)}
      </button>
      <div id="{button_key}_status" style="font-size:0.8rem;color:#16a34a;margin-top:6px;"></div>
    </div>
    <script>
      const btn = document.getElementById("{button_key}");
      btn.addEventListener("click", () => {{
        const text = {payload_json};
        navigator.clipboard.writeText(text).then(() => {{
          document.getElementById("{button_key}_status").innerText = "Copied to clipboard.";
        }}).catch((err) => {{
          document.getElementById("{button_key}_status").innerText = "Copy failed: " + err;
        }});
      }});
    </script>
    """
    st.components.v1.html(html, height=70)


def build_full_summary_text(result):
    lines = []
    lines.append(f"Candidate: {result.get('candidate_label', '')}")
    lines.append(f"Role: {result.get('role_title', '')}")
    lines.append(f"Seniority: {result.get('seniority_level', '')}")
    lines.append(f"Overall Match: {result.get('overall_match', 0)}%")
    lines.append(f"Recommendation: {result.get('shortlist_recommendation', '')}")
    lines.append("")
    lines.append("Scores:")
    scores = result.get("scores", {})
    for dim, label in (
        ("technical_benchmarks", "Technical Benchmarks"),
        ("leadership_context", "Leadership Context"),
        ("soft_signals_culture", "Soft Signals & Culture"),
        ("growth_potential", "Growth Potential"),
    ):
        block = scores.get(dim, {}) or {}
        lines.append(f"  - {label}: {block.get('score', 0)}/10 - {block.get('reasoning', '')}")
    lines.append("")
    lines.append("Required Skills: " + ", ".join(result.get("required_skills", [])))
    lines.append("Nice-to-Have:   " + ", ".join(result.get("nice_to_have_skills", [])))
    lines.append("Red Flags:      " + ", ".join(result.get("red_flags", [])))
    lines.append("")
    lines.append("Top 3 Strengths:")
    for s in result.get("top_3_strengths", []):
        lines.append(f"  - {s}")
    lines.append("Top 3 Gaps:")
    for g in result.get("top_3_gaps", []):
        lines.append(f"  - {g}")
    lines.append("")
    lines.append("Interview Questions to Fill Gaps:")
    for item in result.get("missing_information", []) or []:
        if isinstance(item, dict):
            lines.append(f"  - Gap: {item.get('gap', '')}")
            lines.append(f"    Q:   {item.get('question', '')}")
    lines.append("")
    notes = result.get("internal_notes_bullets", "")
    if notes:
        lines.append("Internal Notes:")
        lines.append(notes)
    return "\n".join(lines)


def render_error_block(result, context_label=""):
    where = f" for {context_label}" if context_label else ""
    st.error(f"analysis failed{where}: {result.get('error', 'unknown error')}")
    raw = result.get("raw") or ""
    if raw:
        with st.expander("show raw model response"):
            st.code(raw, language="json")


def render_analysis(result, *, key_prefix):
    if "error" in result:
        render_error_block(result, result.get("candidate_label", ""))
        return

    # row 1: role, seniority, overall, recommendation
    row1 = st.columns([3, 1.2, 1.2, 1.6])
    with row1[0]:
        st.markdown(
            f"<div class='esa-title' style='font-size:1.5rem;margin-bottom:0;'>"
            f"{escape(result.get('role_title', '') or 'Role')}</div>"
            f"<div class='esa-subtitle'>Candidate: "
            f"{escape(result.get('candidate_label', ''))}</div>",
            unsafe_allow_html=True,
        )
    with row1[1]:
        st.markdown(
            f"<div class='esa-pill esa-pill-grey' style='font-size:0.9rem;'>"
            f"{escape(result.get('seniority_level', '') or 'n/a')}</div>",
            unsafe_allow_html=True,
        )
    with row1[2]:
        st.metric("Overall Match", f"{result.get('overall_match', 0)}%")
    with row1[3]:
        st.markdown(
            render_recommendation_badge(result.get("shortlist_recommendation", "")),
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # row 2: 2x2 score cards
    st.markdown("<div class='esa-section-title'>Assessment Dimensions</div>", unsafe_allow_html=True)
    scores = result.get("scores", {}) or {}
    score_meta = [
        ("technical_benchmarks", "Technical Benchmarks"),
        ("leadership_context", "Leadership Context"),
        ("soft_signals_culture", "Soft Signals & Culture"),
        ("growth_potential", "Growth Potential"),
    ]
    top_row = st.columns(2)
    bottom_row = st.columns(2)
    cells = [top_row[0], top_row[1], bottom_row[0], bottom_row[1]]
    for (dim_key, dim_label), cell in zip(score_meta, cells):
        block = scores.get(dim_key, {}) or {}
        with cell:
            with st.container(border=True):
                st.markdown(
                    f"<div class='esa-score-card'>"
                    f"<h4>{escape(dim_label)}</h4>"
                    f"<div class='esa-score-value'>{int(block.get('score', 0))}/10</div>"
                    f"<div class='esa-score-reason'>{escape(block.get('reasoning', ''))}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # row 3: skills, nice-to-have, red flags
    st.markdown("<div class='esa-section-title'>Skill Mapping</div>", unsafe_allow_html=True)
    sk_cols = st.columns(3)
    with sk_cols[0]:
        st.markdown("**Required Skills**")
        st.markdown(render_pills(result.get("required_skills", []), "esa-pill-green"),
                    unsafe_allow_html=True)
    with sk_cols[1]:
        st.markdown("**Nice-to-Have**")
        st.markdown(render_pills(result.get("nice_to_have_skills", []), "esa-pill-blue"),
                    unsafe_allow_html=True)
    with sk_cols[2]:
        st.markdown("**Red Flags**")
        st.markdown(render_pills(result.get("red_flags", []), "esa-pill-red"),
                    unsafe_allow_html=True)

    # row 4: strengths, gaps, spacer
    st.markdown("<div class='esa-section-title'>Strengths and Gaps</div>", unsafe_allow_html=True)
    sg_cols = st.columns(3)
    with sg_cols[0]:
        st.markdown("**Top 3 Strengths**")
        items = "".join(f"<li>{escape(s)}</li>" for s in result.get("top_3_strengths", []) if s)
        st.markdown(
            f"<ul class='esa-bullet-list esa-strengths'>{items or '<li>-</li>'}</ul>",
            unsafe_allow_html=True,
        )
    with sg_cols[1]:
        st.markdown("**Top 3 Gaps**")
        items = "".join(f"<li>{escape(g)}</li>" for g in result.get("top_3_gaps", []) if g)
        st.markdown(
            f"<ul class='esa-bullet-list esa-gaps'>{items or '<li>-</li>'}</ul>",
            unsafe_allow_html=True,
        )
    with sg_cols[2]:
        st.markdown("&nbsp;", unsafe_allow_html=True)

    # row 5: missing info, interview questions
    st.markdown(
        "<div class='esa-section-title'>Interview Questions to Fill Gaps</div>",
        unsafe_allow_html=True,
    )
    missing = result.get("missing_information") or []
    if not missing:
        st.markdown(
            "<div class='esa-gap-box'>No critical gaps flagged. Proceed to standard "
            "interview structure.</div>",
            unsafe_allow_html=True,
        )
    else:
        items_html = []
        for item in missing:
            if not isinstance(item, dict):
                continue
            gap = escape(item.get("gap", ""))
            question = escape(item.get("question", ""))
            items_html.append(
                f"<div class='esa-gap-item'>"
                f"<div class='esa-gap-text'>{gap}</div>"
                f"<div class='esa-gap-q'>{question}</div>"
                f"</div>"
            )
        st.markdown(
            f"<div class='esa-gap-box'>{''.join(items_html)}</div>",
            unsafe_allow_html=True,
        )

    # row 6: copy buttons
    st.markdown("<div class='esa-section-title'>Quick Actions</div>", unsafe_allow_html=True)
    full_summary = build_full_summary_text(result)
    internal_notes = result.get("internal_notes_bullets", "") or full_summary
    btn_cols = st.columns(2)
    with btn_cols[0]:
        copy_to_clipboard_button("Copy Full Summary", full_summary, f"{key_prefix}_copy_full")
    with btn_cols[1]:
        copy_to_clipboard_button("Copy Internal Notes", internal_notes, f"{key_prefix}_copy_notes")


def cv_input_widget(prefix, *, height=300):
    method = st.radio(
        "CV input method",
        ["Upload PDF", "Paste Text"],
        key=f"{prefix}_method",
        horizontal=True,
    )
    if method == "Upload PDF":
        uploaded = st.file_uploader("Upload CV (PDF)", type=["pdf"], key=f"{prefix}_pdf")
        if uploaded is not None:
            text = parser.extract_text_from_pdf(uploaded)
            if text:
                st.caption(f"Extracted {len(text):,} characters from PDF.")
            return text
        return ""
    pasted = st.text_area(
        "Paste CV text",
        height=height,
        key=f"{prefix}_text",
        placeholder="Paste the candidate's CV here...",
    )
    return parser.clean_text(pasted or "")


def run_single_mode():
    left, right = st.columns([2, 3], gap="large")

    with left:
        st.markdown("### Inputs")
        jd_text = st.text_area(
            "Job Description",
            height=300,
            key="single_jd",
            placeholder="Paste the job description here...",
        )
        st.markdown("**Candidate CV**")
        cv_text = cv_input_widget("single_cv")
        candidate_label = st.text_input(
            "Candidate name / label",
            key="single_name",
            placeholder="e.g. Jane Doe",
        )
        analyse_clicked = st.button(
            "Analyse Candidate", type="primary", use_container_width=True
        )

    with right:
        if not analyse_clicked:
            st.info(
                "Fill in the JD, the candidate CV and the candidate name, then "
                "click **Analyse Candidate**. Results will appear here."
            )
            return

        if not jd_text.strip():
            st.error("Please provide a job description.")
            return
        if not cv_text.strip():
            st.error("Please provide the candidate CV (paste text or upload PDF).")
            return
        if not candidate_label.strip():
            st.error("Please provide a candidate name or label.")
            return

        with st.spinner("Analysing candidate against the JD..."):
            result = analyser.analyse_candidate(
                jd_text=jd_text,
                cv_text=cv_text,
                candidate_label=candidate_label.strip(),
            )

        render_analysis(result, key_prefix="single")


def _shortlist_dataframe(ranked):
    rows = []
    for item in ranked:
        if "error" in item:
            rows.append(
                {
                    "Rank": item.get("rank", ""),
                    "Candidate": item.get("candidate_label", ""),
                    "Role Fit %": 0,
                    "Recommendation": "Error",
                    "Top Strength": "",
                    "Critical Gap": item.get("error", "")[:80],
                }
            )
            continue
        strengths = item.get("top_3_strengths") or [""]
        gaps = item.get("top_3_gaps") or [""]
        rows.append(
            {
                "Rank": item.get("rank", ""),
                "Candidate": item.get("candidate_label", ""),
                "Role Fit %": int(item.get("overall_match", 0) or 0),
                "Recommendation": item.get("shortlist_recommendation", ""),
                "Top Strength": strengths[0] if strengths else "",
                "Critical Gap": gaps[0] if gaps else "",
            }
        )
    return pd.DataFrame(rows)


def run_shortlist_mode():
    st.markdown("### Job Description (shared across candidates)")
    jd_text = st.text_area(
        "Job Description",
        height=220,
        key="shortlist_jd",
        placeholder="Paste the job description here...",
        label_visibility="collapsed",
    )

    st.markdown("### Candidates")
    cand_cols = st.columns(3, gap="large")
    candidates = []
    for idx, col in enumerate(cand_cols, start=1):
        with col:
            st.markdown(f"**Candidate {idx}**")
            name = st.text_input(
                "Name / label", key=f"shortlist_name_{idx}",
                placeholder=f"Candidate {idx} name",
            )
            cv_text = cv_input_widget(f"shortlist_cv_{idx}", height=220)
            candidates.append({"name": (name or "").strip(), "cv": cv_text})

    st.markdown("")
    generate = st.button("Generate Shortlist", type="primary", use_container_width=True)
    if not generate:
        return

    if not jd_text.strip():
        st.error("Please provide a job description.")
        return

    valid_candidates = [c for c in candidates if c["name"] and c["cv"].strip()]
    if not valid_candidates:
        st.error("Please provide at least one candidate with both a name and a CV.")
        return

    progress = st.progress(0.0, text="Starting analysis...")
    status = st.empty()
    results = []
    total = len(valid_candidates)
    for i, cand in enumerate(valid_candidates, start=1):
        status.info(f"Analysing {cand['name']} ({i}/{total})...")
        result = analyser.analyse_candidate(
            jd_text=jd_text,
            cv_text=cand["cv"],
            candidate_label=cand["name"],
        )
        results.append(result)
        progress.progress(i / total, text=f"Analysed {i}/{total}")
    status.success(f"Completed analysis for {total} candidate(s).")

    ranked = scorer.rank_candidates(results)

    # ranking summary table
    st.markdown("## Ranking Summary")
    df = _shortlist_dataframe(ranked)
    try:
        styled = df.style.background_gradient(cmap="Greens", subset=["Role Fit %"], vmin=0, vmax=100)
        st.dataframe(styled, use_container_width=True, hide_index=True)
    except Exception:
        # fallback if styler can't render on this pandas build
        st.dataframe(df, use_container_width=True, hide_index=True)

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    st.download_button(
        "Download ranking as CSV",
        data=csv_buffer.getvalue(),
        file_name="shortlist_ranking.csv",
        mime="text/csv",
    )

    # insight panel
    st.markdown("## Insight Panel")
    summary = scorer.compute_summary(ranked)
    panel = st.container(border=True)
    with panel:
        if summary["best_candidate"]:
            st.markdown(
                f"**Best candidate:** {escape(summary['best_candidate'])} - "
                f"{escape(summary['best_reason'])}"
            )
        else:
            st.markdown("**Best candidate:** _no successful analyses to rank_")
        if summary["common_gap"]:
            st.markdown(f"**Most common gap:** {escape(summary['common_gap'])}")
        if summary["first_interview_question"]:
            st.markdown(
                f"**Recommended first interview question:** "
                f"{escape(summary['first_interview_question'])}"
            )

    # per-candidate detail
    st.markdown("## Per-Candidate Detail")
    for item in ranked:
        if "error" in item:
            label = item.get("candidate_label", "Unknown")
            with st.expander(f"{label} - analysis failed", expanded=False):
                render_error_block(item, label)
            continue
        label = (
            f"#{item.get('rank', '?')} · {item.get('candidate_label', '')} "
            f"- {item.get('overall_match', 0)}% match"
        )
        with st.expander(label, expanded=False):
            render_analysis(item, key_prefix=f"shortlist_{item.get('rank', 0)}")


def main():
    st.markdown(
        "<div class='esa-title'>Executive Search Agent</div>"
        "<div class='esa-subtitle'>AI-powered candidate screening for "
        "executive search professionals</div>",
        unsafe_allow_html=True,
    )

    mode = st.radio(
        "Mode",
        ["Single Candidate Analysis", "Shortlist Generator (up to 3 candidates)"],
        horizontal=True,
        label_visibility="collapsed",
    )

    st.markdown("---")

    if mode == "Single Candidate Analysis":
        run_single_mode()
    else:
        run_shortlist_mode()


if __name__ == "__main__":
    main()
