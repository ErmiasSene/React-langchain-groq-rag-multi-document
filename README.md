# React-langchain-groq-rag-multi-document
upload multiple document 
# RAG Groq — React + FastAPI (Render + Vercel)

Laravel has been removed. React now calls the FastAPI/LangChain service
directly from the browser.

```
rag-react/
├── backend/     FastAPI + LangChain + Groq + Chroma  → deploy to Render
└── frontend/    React (Vite)                          → deploy to Vercel
```

## Local development

**Backend**
```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: put your NEW, rotated Groq key in GROQ_API_KEY
uvicorn main:app --reload --port 8000
```

**Frontend** (separate terminal)
```bash
cd frontend
npm install
cp .env.example .env      # VITE_API_URL=http://127.0.0.1:8000 by default
npm run dev                # opens on http://localhost:5173
```

Upload a PDF, then ask a question — the two should now talk to each other
with no PHP layer in between.

---

## Deploy the backend to Render

1. Push this repo to GitHub.
2. In Render: **New → Web Service**, connect the repo, set the root
   directory to `backend/`.
3. Render will detect `render.yaml` and pre-fill the build/start commands.
   If it doesn't, set them manually:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Under **Environment**, add:
   - `GROQ_API_KEY` — your rotated key
   - `GROQ_MODEL` — `openai/gpt-oss-120b` (or leave unset, that's the default)
   - `FRONTEND_URL` — leave as `http://localhost:5173` for now, you'll
     update this once your Vercel URL exists (step below)
5. **Persistent disk**: Chroma writes to `./vector_db` on local disk. Render's
   free tier has an *ephemeral* filesystem — anything ingested disappears on
   redeploy or restart. Attach a persistent disk (Starter plan or above) at
   `vector_db`, as set up in `render.yaml`, or your uploads won't survive.
6. Deploy. Confirm it's live: `https://your-service.onrender.com/health`.

## Deploy the frontend to Vercel

1. In Vercel: **New Project**, import the same repo, set the root directory
   to `frontend/`.
2. Vercel auto-detects Vite (or `vercel.json` confirms it) — no build
   command changes needed.
3. Under **Settings → Environment Variables**, add:
   - `VITE_API_URL` = `https://your-service.onrender.com` (your Render URL
     from above, no trailing slash)
4. Deploy. Vercel gives you a URL like `https://your-app.vercel.app`.

## Connect them

Go back to Render → your backend service → Environment, and set:
```
FRONTEND_URL=https://your-app.vercel.app
```
Redeploy the backend so the new CORS origin takes effect. Without this step
the browser will block every request from Vercel with a CORS error.

---

## Notes

- **Rotate your Groq key** if you haven't yet — the original one was
  exposed in an earlier message in this conversation.
- `GET /models` on the backend lists which model IDs your key can use, in
  case `openai/gpt-oss-120b` ever gets deprecated too.
- Render's free tier spins the service down after inactivity; the first
  request after a while will be slow (cold start) while it wakes up and
  reloads the embedding model. Upgrade the plan if that's a problem.
- CORS is locked to a single `FRONTEND_URL` origin — if you add a custom
  domain on Vercel later, update this env var to match, or requests will
  be blocked again.
