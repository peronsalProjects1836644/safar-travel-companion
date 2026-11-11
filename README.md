# Safar: AI Smart Tour and Live Travel Companion

`backend/` FastAPI and MongoDB API. `frontend/` React web app. Deployment steps are in `DEPLOY.md`.

## Run locally (no database, no keys, needs internet)

Needs Python 3.12 or newer and Node 20 or newer. Use your own email below.

Terminal 1, in `backend`:
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python -m scripts.seed_places --geocode --email you@example.com
python -m scripts.seed_places --photos --email you@example.com
python -m scripts.dev_server
```
Mac or Linux: activate with `source .venv/bin/activate`. The first two seed commands take about 10 minutes together and run once.
The server prints an admin login. It keeps data in memory only, so it is wiped on restart.

Terminal 2, in `frontend`:
```
npm install
npm run dev
```
Open http://localhost:5173.

## Checks
```
cd backend && python -m pytest -q && python -m ruff check .
cd frontend && npm run build
python -m scripts.check_services      # which free map and weather services answer from your network
python -m scripts.check_openai        # once an OpenAI key is in backend/.env
```

## Settings
All settings are listed in `backend/.env.example`. Copy it to `.env` to use a real MongoDB.
Without `OPENAI_API_KEY` trips use the built-in planner and the chat assistant is off.
