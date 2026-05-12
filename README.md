# executive-search-agent

live demo: https://vaish-executive-agent.streamlit.app/
ps: this demo website uses a free-tier grok api call so it may not work sometimes

Streamlit app that screens candidates against a job description using the groq api. paste a jd and a cv (or upload pdf) and it gives back scores, strengths, gaps, and interview questions to ask. shortlist mode does the same for up to 3 candidates and ranks them.

## Scoring dimensions

four scores out of 10 plus an overall match %:

1. Technical benchmarks - the hard skills the jd actually asks for
2. Leadership context - ownership and leadership evidence, calibrated to the role (intern: TA/club office/team-project lead; IC: project ownership and mentoring; senior+: team scope, P&L, org-level impact)
3. Soft signals & culture - tone, framing, longevity, the stuff between the lines
4. Growth potential - trajectory, not just current state

the bar for every dimension adapts to what the jd is hiring for. the model pins the seniority level from the jd first (intern through executive) and scores against that bar, so an intern role isn't graded against P&L scope and a c-suite role isn't graded against hackathon wins.

I split it this way because a single number hides what kind of fit it is. "strong technical, weak leadership context" tells you something.

the overall % is the model's holistic call, but clamped to within ±15 of the four-score average and rounded up to the nearest 5, so the headline can't drift far from the breakdown.

## Missing information

Every cv has gaps the model can't resolve from text alone. so the app also flags each gap and pairs it with the interview question you'd ask to clear it up. that part was actually the point of the project for me, the scoring is just context.

## Setup

needs python 3.10+ and a free groq api key from console.groq.com (sign up, generate key, copy it).

```
pip install -r requirements.txt
cp .env.example .env
```

then open `.env` and paste your key in. then:

```
streamlit run app.py
```

when you run it locally, it opens at http://localhost:8501 on your own machine and uses the key in your local `.env`. the live demo link above is the hosted version on streamlit cloud.

## limitations

1. It can't verify anything the cv claims. inflated titles, fake scope, hidden gaps etc. 
2. It's biased toward well-written cvs. someone who writes a modest cv will get undersold, someone with a polished one gets flattered.
3. It has no context on the client, the market, or who the firm has rejected before (future scope?)
