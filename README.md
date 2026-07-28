# Executive Search Agent

LLM-assisted candidate screening with a scorecard that is engineered not to flatter.

**Live demo:** https://vaish-executive-agent.streamlit.app/
(The demo runs on a free-tier Groq API key, so it may occasionally hit rate limits.)

> **At a glance**
> **Question:** when an LLM screens a CV against a job description, the two
> failure modes are inflation (everyone scores 80%) and level confusion
> (grading an intern against a P&L bar). Can prompt design plus a few
> hard-coded guardrails keep the output honest enough to be useful?
> **Approach:** a four-dimension scorecard where the model must first pin
> the JD's seniority level and score against that bar, an explicit
> anti-inflation clause, and a post-hoc clamp that stops the headline
> number from drifting away from the dimension scores.
> **The actual point:** every screen ends with the *missing information* —
> what the CV cannot prove, paired with the interview question that would
> resolve it. The score is context; the questions are the product.
> **Status:** working demo. A structured bias audit of this tool (matched
> synthetic CV pairs, score-differential analysis) is the planned next
> stage — see "Responsible AI" below.

Paste a job description and a CV (or upload a PDF) and it returns scores,
strengths, gaps, and the screening questions a recruiter should ask next.
Shortlist mode does the same for up to three candidates and ranks them.

## How the scoring works

Four scores out of 10, plus an overall match percentage:

1. **Technical benchmarks** — the hard skills the JD actually asks for.
2. **Leadership context** — ownership evidence, calibrated to the role.
   For an intern that means TA roles, club office, or leading a team
   project; for a mid-level IC it means project ownership and mentoring;
   for senior+ it means team scope, P&L, org-level impact.
3. **Soft signals and culture** — tone, framing, longevity, the things
   between the lines.
4. **Growth potential** — trajectory, not just current state.

I split it this way because a single number hides what *kind* of fit a
candidate is. "Strong technical, weak leadership context" tells you
something a 72% does not.

Three guardrails do most of the work of keeping the output honest:

- **Seniority calibration first.** The system prompt forces the model to
  decide what level the JD is hiring for *before* scoring anything, and
  to set every bar at that level. An intern role is not graded against
  executive scope, and a C-suite search is not impressed by hackathon
  wins.
- **An anti-inflation clause.** LLMs default to generosity. The rubric
  states that 5/10 is "average fit," that 8+ requires explicit,
  level-appropriate evidence, and that partial matches belong in the
  40–60% range. Generic claims ("passionate learner," "strategic
  thinker") are told to clear nothing.
- **A sanity clamp in code, not in the prompt.** The model's holistic
  overall percentage is clamped to within ±15 points of the four-score
  average. Whatever the model wants the headline to say, it cannot drift
  far from the breakdown it just justified.

## Missing information is the real output

Every CV has gaps the model cannot resolve from text alone. So each
screen flags what is unverifiable — inflated-looking titles, unexplained
gaps, claimed skills with no evidence — and pairs every gap with the
specific interview question that would clear it up. That part was the
point of the project for me; the scoring exists to give the questions
context.

## Under the hood

- Groq API (`llama-3.3-70b-versatile` by default, overridable via
  `GROQ_MODEL`), temperature 0.2, JSON-mode responses.
- A three-stage parse cascade for the model's JSON: plain parse, then a
  bracket-reconciliation pass (llama sometimes closes a dict with `]`),
  then `json_repair` for truncation and unescaped quotes. If Groq's own
  server-side JSON validator rejects the response, the raw text is
  salvaged from the error body instead of failing the screen.
- Every result is normalised before rendering so a missing key degrades
  gracefully instead of crashing the UI.

## Responsible AI

Used for real hiring, a system like this would be a **high-risk AI
system under the EU AI Act** (Annex III covers employment and worker
selection). This is a student demo and has never screened a real
candidate, but the obligations that would apply — bias testing,
documentation, human oversight — are a useful standard to hold it to,
and the honest position is that it would not currently meet them:

1. **It cannot verify anything the CV claims.** Inflated titles, fake
   scope, and hidden gaps pass straight through. The
   missing-information output mitigates this but does not solve it.
2. **It is biased toward well-written CVs.** Someone who writes modestly
   gets undersold; someone polished gets flattered. Writing quality
   correlates with native language, education, and coaching — which
   makes this a proxy-discrimination channel, not a cosmetic issue.
3. **It has no context on the client, the market, or past hiring
   decisions**, so it cannot detect when its own patterns mirror a
   biased history.

The next stage of this project is a structured audit: matched synthetic
CV pairs (identical qualifications; varied names, genders, universities,
and career-gap patterns), score-differential analysis across those
pairs, and a written findings report in the same repo. I would rather
publish the audit of my own tool than pretend the tool doesn't need one.

## Setup

Needs Python 3.10+ and a free Groq API key from console.groq.com.

```bash
pip install -r requirements.txt
cp .env.example .env
# open .env and paste your key after GROQ_API_KEY=
streamlit run app.py
```

Running locally, the app opens at http://localhost:8501 and uses the key
in your local `.env`. The live demo above is the hosted version on
Streamlit Cloud.
