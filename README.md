# PA Review Copilot

My prototype for the prior authorization case study.

The plan gets 15,000 prior auth requests a month, and each one takes about 4 days because nurses read
everything by hand and 22% come back with missing info. I built a tool that reads each request as soon as
it arrives, finds the evidence with exact quotes, checks it against the coverage policy, and tells the
nurse in plain words what's wrong and what's missing. The nurse still makes the call. The AI can't deny anything.

## How it works

Three agents run in order (LangGraph):

1. **Intake & Safety** (rules): checks the files, removes hidden instructions aimed at the AI, catches pages
   from the wrong patient, and masks personal details.
2. **Clinical Evidence** (Claude): pulls out the facts the policy needs, each with a quote and page number.
   The code checks every quote is really on that page.
3. **Policy & Compliance** (rules): checks the policy, flags conflicts, picks the route, and drafts a
   letter to the doctor if something is missing.

The React screen shows the result. Click any yellow number to jump to the exact quote in the document.

## Running it

You need Python 3.10+.

```
python -m venv .venv
.venv\Scripts\activate          (Mac: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          (Mac: cp .env.example .env)
```

Put your Anthropic API key in `.env`. Without it, the app still works using simple rules instead of Claude.

```
python create_sample_cases.py   # makes 11 test cases
python run_pipeline.py          # should say 11/11
pytest -q                       # safety tests
python start_app.py             # opens the app at localhost:8000
```

Then click **Run AI on all cases**.

## What's where

- `backend/` has the three agents, the safety checks, the coverage rules and the API
- `frontend/` has the React app (already built in `dist/`, so no Node needed)
- `sample_data/` has the fake members, providers and test cases
- `tests/` has the safety tests
- `slides/` has the presentation

## Notes

All data is made up. The coverage rules are simplified versions of real policies. In production this would
run Claude under a HIPAA BAA, use the plan's licensed criteria, and connect to their real systems.
