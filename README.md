# Yale Courses

Course catalog for every Yale school, with an AI chat assistant (Lecture 7 app, deployed in Lecture 8).

- `backend/` — FastAPI + PydanticAI agent (Portkey)
- `frontend/` — React + Vite
- `data/` — course data: `yale_courses.json` (all schools, what the site serves) and `yale_som_classes.json` (SOM's own listing, merged in)

## Refresh the course data

Other schools come from [Yale Course Search](https://courses.yale.edu), the official catalogue; SOM keeps its own richer listing. Yale Law School is not in Yale Course Search. Takes about 5 minutes:

```bash
cd backend && .venv/bin/python fetch_yale_courses.py --term 202603
```

Term codes: `YYYY01` spring, `YYYY02` summer, `YYYY03` fall.

## Run locally

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python main.py
```

```bash
cd frontend && npm install && npm run dev
```

Copy `.env.example` to `.env` and add your `PORTKEY_API_KEY`. Never commit `.env`.
