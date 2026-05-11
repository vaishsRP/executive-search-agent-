# executive-search-agent

Streamlit app that screens candidates against a job description using the groq api. paste a jd and a cv (or upload pdf) and it gives back scores, strengths, gaps, and interview questions to ask. shortlist mode does the same for up to 3 candidates and ranks them.

## scoring dimensions

four scores out of 10 plus an overall match %:

1. Technical benchmarks - the hard skills the jd actually asks for
2. Leadership context - team size, scope, what kind of leadership the cv shows
3. Soft signals & culture - tone, framing, longevity, the stuff between the lines
4. Growth potential - trajectory, not just current state

I split it this way because a single number hides what kind of fit it is. "strong technical, weak leadership context" tells you something.

## missing information

Every cv has gaps the model can't resolve from text alone. so the app also flags each gap and pairs it with the interview question you'd ask to clear it up. that part was actually the point of the project for me, the scoring is just context.

## setup

needs python 3.10+ and a free groq api key from console.groq.com (sign up, generate key, copy it).

```
pip install -r requirements.txt
cp .env.example .env
```

then open `.env` and paste your key in. then:

```
streamlit run app.py
```

opens at http://localhost:8501.

## limitations

1. It can't verify anything the cv claims. inflated titles, fake scope, hidden gaps etc. 
2. It's biased toward well-written cvs. someone who writes a modest cv will get undersold, someone with a polished one gets flattered.
3. It has no context on the client, the market, or who the firm has rejected before (future scope?)

