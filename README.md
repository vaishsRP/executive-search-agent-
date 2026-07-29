# executive-search-agent

live demo: https://vaish-executive-agent.streamlit.app/
ps: the demo runs on a free-tier groq api key so it may not work sometimes

Streamlit app that screens candidates against a job description using the
groq api. paste a jd and a cv (or upload pdf) and it gives back scores,
strengths, gaps, and interview questions to ask. shortlist mode does the
same for up to 3 candidates and ranks them.

the two ways these tools usually fail: they flatter everyone (every cv
scores 80%), and they grade against the wrong bar (an intern judged on
P&L scope). most of the work in this project went into guardrails
against those two things.

## Scoring dimensions

four scores out of 10 plus an overall match %:

1. Technical benchmarks - the hard skills the jd actually asks for
2. Leadership context - ownership and leadership evidence, calibrated to the role (intern: TA/club office/team-project lead; IC: project ownership and mentoring; senior+: team scope, P&L, org-level impact)
3. Soft signals & culture - tone, framing, longevity, the stuff between the lines
4. Growth potential - trajectory, not just current state

I split it this way because a single number hides what kind of fit it is.
"strong technical, weak leadership context" tells you something.

## The guardrails

- the model has to pin the jd's seniority level (intern through
  executive) before scoring anything, and every bar is set at that
  level. an intern role isn't graded against P&L and a c-suite role
  isn't impressed by hackathon wins.
- the rubric says 5/10 is "average fit", 8+ needs explicit evidence at
  the right level, and partial matches belong in the 40-60% range.
  generic claims ("passionate learner", "strategic thinker") clear
  nothing. llms default to generosity, so this has to be spelled out.
- the overall % is clamped in code to within ±15 of the four-score
  average, so the headline can't drift away from the breakdown the
  model just justified. prompts alone don't hold; the clamp does.

## Missing information

Every cv has gaps the model can't resolve from text alone. so the app
flags each gap and pairs it with the interview question you'd ask to
clear it up. that part was actually the point of the project for me,
the scoring is just context.

## Under the hood

- groq api (llama-3.3-70b-versatile by default, override with GROQ_MODEL),
  temperature 0.2, json mode
- three-stage parse for the model's json: plain parse, then a bracket
  fixer (llama sometimes closes a dict with `]`), then json_repair. if
  groq's own validator rejects the response, the raw text gets salvaged
  from the error body instead of failing the screen
- results are normalised before rendering so a missing key doesn't
  crash the ui

## Setup

needs python 3.10+ and a free groq api key from console.groq.com.

```
pip install -r requirements.txt
cp .env.example .env
```

then open `.env` and paste your key in. then:

```
streamlit run app.py
```

when you run it locally, it opens at http://localhost:8501 and uses the
key in your local `.env`. the live demo link above is the hosted version
on streamlit cloud.

## limitations, and the responsible AI part

used for real hiring, a tool in this category is high-risk under the EU
AI Act (Annex III covers employment). this is a student demo and has
never screened a real candidate, but the standard is worth stating
because right now it would not meet it:

1. It can't verify anything the cv claims. inflated titles, fake scope,
   hidden gaps etc. the missing-information output helps but doesn't
   solve it.
2. It's biased toward well-written cvs. someone who writes a modest cv
   gets undersold, someone with a polished one gets flattered. writing
   quality tracks native language, education, and coaching, so this is
   a proxy-discrimination channel, not a cosmetic issue.
3. It has no context on the client, the market, or who the firm has
   rejected before, so it can't tell when its patterns mirror a biased
   history.

next stage: a proper bias audit of this tool. matched synthetic cv
pairs (same qualifications, different names/genders/universities/career
gaps), measure the score differences, publish the findings here. I'd
rather audit my own tool than pretend it doesn't need one.
