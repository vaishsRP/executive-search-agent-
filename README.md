# Executive Search Agent

Executive search consultants spend the bulk of any new mandate doing the same handful of things by hand: reading dozens of CVs, holding each one up against a client's job description, deciding which signals matter for *this* level of seniority, scoring fit across qualitative dimensions, and writing internal notes for ATS and email. The work is judgement-heavy but it is also pattern-heavy, and the first pass — the one that turns a longlist into a shortlist — is where most of the unbillable hours go. This tool automates that first pass: paste a JD and one or more CVs, and the agent returns a structured assessment, a ranked shortlist, and a list of interview questions tailored to the gaps it found, all in a format a consultant can drop straight into client correspondence.

## The four scoring dimensions

For senior search the question is rarely "can this person do the job" — by the time a CV reaches a shortlist the technical floor is usually met. The interesting question is *what kind of fit* the candidate is. So instead of a single "score", the agent grades each candidate on four dimensions chosen to mirror how a consultant actually reasons:

1. **Technical Benchmarks** — depth of the hard skills the JD explicitly names: tools, certifications, sector experience, the specific functional craft of the role.
2. **Leadership Context** — the *environments* in which the candidate has led: scope (team size, P&L, geography), stage (startup, scale-up, turnaround, post-merger), and the realism of the leadership claims for the seniority level on offer.
3. **Soft Signals & Culture** — what the CV implies but does not state: writing style, signs of operator vs. strategist, longevity patterns, the way achievements are framed, and any cultural mismatch with the hiring organisation.
4. **Growth Potential** — trajectory rather than current state. Has the candidate consistently stretched? Are they likely to grow into the role over 18-24 months, or have they plateaued?

A senior hire is usually a trade-off between these dimensions. Surfacing them separately keeps the conversation with the client honest: "strong technical, weaker leadership context" is a far more useful sentence than "78% match".

## Missing Information — why consultative gap-finding matters more than scoring

A score on its own only tells the client what the model decided. What makes a consultant valuable is the *next question they ask*. Every CV has gaps the AI cannot resolve from text alone — an ambiguous title, an unexplained 14-month break, a vague claim of "transformed the function". The agent flags each of these as a `gap` and pairs it with a specific `question` to ask in interview. The output is therefore not just an assessment, it is the start of an interview brief: it tells the consultant exactly what to probe, and gives them a defensible reason for probing it. Scoring is the conclusion. The questions are the work.

## Install and run

You need Python 3.10+ and a free Groq API key.

1. Get a Groq API key at [console.groq.com](https://console.groq.com) — sign up, create a key, copy it.
2. Clone the repo and install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set the API key. Either copy `.env.example` to `.env` and replace the placeholder, or export it in your shell:

   ```bash
   cp .env.example .env
   # then edit .env and paste your real key
   ```

4. Run the app:

   ```bash
   streamlit run app.py
   ```

   Streamlit will open the UI in your browser at `http://localhost:8501`.

Optional: override the model with `GROQ_MODEL=<model-id>` in `.env` (defaults to `llama-3.3-70b-versatile`).

## Limitations

LLM-based screening is a sharper longlist filter, not a replacement for a consultant. Three honest things this tool cannot do:

1. **It cannot verify what the CV claims.** If a candidate inflates scope, invents a title, or omits a difficult exit, the model takes the CV at face value. Reference checks and structured interviews remain non-negotiable.
2. **It is biased toward written self-presentation.** Strong operators who write modest CVs will be undersold by the model; weaker candidates who write polished CVs will be flattered. Culture and leadership signal in person are not detectable here.
3. **It has no memory of the client or the market.** The agent does not know which firms compete with the hiring company, what the going compensation is, or what the client has rejected on previous searches. The consultant still owns the market context entirely.

Treat the output as a well-prepared first read — the kind a junior researcher would produce — and bring senior judgement to everything that matters.
