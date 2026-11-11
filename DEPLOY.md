# Deploy Safar (free stack)

Order matters: Atlas, then GitHub, then the API on Vercel, then the website on Vercel, then connect them.
Use the one Google account for all of them.

## 1. MongoDB Atlas (database)
1. Open the project, then your cluster, then Database Access: add a user (username and password, read and write to any database).
2. Network Access: add `0.0.0.0/0` (Vercel has no fixed address).
3. Cluster, Connect, Drivers: copy the `mongodb+srv://...` string and put the password in it.
   If the password has symbols such as `@` or `#`, use letters and digits only.

## 2. Load the places into Atlas (once, from your computer)
In `backend`, with the venv active, put the Atlas string in `.env` as `MONGODB_URI`, then:
```
python -m scripts.seed_places --geocode --email YOUR_EMAIL
python -m scripts.seed_places --photos --email YOUR_EMAIL
python -m scripts.seed_places --import
```
Check: Atlas, Browse Collections, database `smart_tour`, collection `places` shows about 77 documents.

## 3. GitHub
Create a new empty repository. From the project root:
```
git init
git add .
git commit -m "Safar"
git branch -M main
git remote add origin https://github.com/USER/REPO.git
git push -u origin main
```
`.gitignore` keeps `.env` and `node_modules` out. Never commit a real key.

## 4. Vercel (API)
Add New, Project, pick the repository.
- Project name: `safar-api`
- Root Directory: `backend`
- Framework: FastAPI (detected from `app/asgi.py`)
- Environment variables:
  - `MONGODB_URI`: the Atlas string
  - `MONGODB_DB`: `smart_tour`
  - `JWT_SECRET`: a random value of 40 or more characters (`python -m scripts.gen_secret`)
  - `ENVIRONMENT`: `production`
  - `TRUST_PROXY`: `true`
  - `CORS_ORIGINS`: `http://localhost:5173` for now, set the website address in step 6
  - `NOMINATIM_CONTACT_EMAIL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`
  - `OPENAI_API_KEY`: leave empty until the AI step

When it is live, open `https://YOUR-API.vercel.app/health`. It should answer `ok`.

## 5. Vercel (website)
Add New, Project, pick the same repository.
- Project name: `safar`
- Root Directory: `frontend`
- Framework: Vite
- Environment variable: `VITE_API_URL` = your API address, no trailing slash

## 6. Connect
On the `safar-api` project, set `CORS_ORIGINS` to the website address (for example `https://safar.vercel.app`) and redeploy.
Open the website address, register, plan a trip.

## Notes
- The API runs as a Vercel Function. A Hobby function may run for at most 300 seconds, and WebSocket connections close at that limit, so the live companion reconnects or falls back to plain HTTP.
- Rate limits and other in-memory state are per function instance.
- Free tiers are not meant for commercial use (Vercel Hobby is non-commercial). Fine for a university project.
- To add AI: put `OPENAI_API_KEY` in the `safar-api` environment variables, redeploy, then run `python -m scripts.check_openai` locally with the same key to confirm the model name.
