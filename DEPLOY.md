# Deploy Safar (free stack)

Order matters: Atlas, then GitHub, then Render, then Vercel, then connect them.
Use the one Google account for all four.

## 1. MongoDB Atlas (database)
1. Open the project, then your cluster, then Database Access: add a user (username and password, read and write to any database).
2. Network Access: add `0.0.0.0/0` (Render has no fixed address).
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
Create a new empty repository (private is fine). From the project root:
```
git init
git add .
git commit -m "Safar"
git branch -M main
git remote add origin https://github.com/USER/REPO.git
git push -u origin main
```
`.gitignore` keeps `.env` and `node_modules` out. Never commit a real key.

## 4. Render (API)
New, Blueprint, pick the repository. Render reads `render.yaml`. Fill the values it asks for:
- `MONGODB_URI`: the Atlas string
- `CORS_ORIGINS`: leave a placeholder now, set the Vercel address in step 6
- `NOMINATIM_CONTACT_EMAIL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`
- `OPENAI_API_KEY`: leave empty until the AI step

When it is live, open `https://YOUR-API.onrender.com/health`. It should answer `ok`.

## 5. Vercel (website)
Add New, Project, pick the repository.
- Root Directory: `frontend`
- Framework: Vite
- Environment variable: `VITE_API_URL` = your Render address, no trailing slash

## 6. Connect
In Render, set `CORS_ORIGINS` to the Vercel address (for example `https://safar.vercel.app`) and let it redeploy.
Open the Vercel address, register, plan a trip.

## Notes
- Render free services sleep after 15 minutes. The first request then takes about a minute. Open the site before a demo.
- Free tiers are not meant for commercial use (Render says not for production, Vercel Hobby is non-commercial). Fine for a university project.
- To add AI: put `OPENAI_API_KEY` in Render environment, redeploy, then run `python -m scripts.check_openai` locally with the same key to confirm the model name.
