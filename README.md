# Smart Resume Screener

Intelligently parses resumes, extracts structured candidate data, and uses an
LLM (Google Gemini) to compute a semantic fit score against a job description —
returning a ranked, shortlisted candidate list with justifications.

## Objective

Given one or more resumes (PDF/text) and a job description, the system:
1. Extracts structured data (skills, education, experience) from each resume.
2. Uses an LLM to semantically compare each resume with the job description.
3. Produces a 1–10 fit score with a short justification.
4. Displays ranked, shortlisted candidates in a simple dashboard.

## Architecture

```
                ┌────────────────────┐
                │   Frontend (SPA)   │   frontend/index.html
                │  upload / view UI  │   vanilla JS, fetch()
                └─────────┬──────────┘
                          │ REST (JSON / multipart)
                          ▼
                ┌────────────────────┐
                │   FastAPI backend  │   backend/main.py
                └───┬────────┬───────┘
                    │        │
     ┌──────────────┘        └───────────────┐
     ▼                                        ▼
┌──────────────────┐                ┌───────────────────┐
│ resume_parser.py  │                │    matcher.py      │
│ - PDF/text extract│                │ - builds LLM prompt│
│ - rule-based skill/│                │ - calls Gemini API  │
│   education/exp.   │                │ - parses JSON score│
│   extraction       │                └─────────┬──────────┘
└──────────┬─────────┘                          │
           │                                     │
           ▼                                     ▼
                ┌────────────────────┐
                │    database.py     │   SQLite (stdlib sqlite3)
                │ resumes / jobs /   │   backend/resume_screener.db
                │ matches tables     │
                └────────────────────┘
```

**Why this split?** Structured extraction (skills, education, experience) is
handled with fast, deterministic rule-based parsing (regex + keyword
matching) — it doesn't need semantic reasoning. The **matching/scoring**
step is where an LLM genuinely adds value (understanding *fit*, not just
keyword overlap), so that's the only place the LLM is called, keeping the
pipeline fast and minimizing API usage/cost.

## Tech Stack

- **Backend:** FastAPI (Python)
- **Database:** SQLite (Python stdlib `sqlite3`, no ORM — kept dependency-free)
- **Resume parsing:** `pypdf` for PDF text extraction + rule-based extraction
- **LLM:** Google Gemini API (`google-genai` Python SDK, free tier) for match scoring
- **Frontend:** Single static HTML/JS dashboard (no framework/build step)

## LLM Usage

The LLM is used exclusively for **semantic matching & scoring** in
`backend/matcher.py`. Prompt template sent to Gemini for every resume/job pair:

```
Compare the following resume with this job description and rate fit on
1-10 with justification.

Respond ONLY with a JSON object in this exact shape, no other text:
{"score": <integer 1-10>, "justification": "<2-3 sentence explanation>"}

Resume:
Candidate: <name>
Extracted skills: <skills>
Extracted education: <education>
Extracted experience: <experience>
Full resume text:
<resume text, truncated to 4000 chars>

Job Description:
<job description text, truncated to 3000 chars>
```

The response is parsed as JSON; if parsing fails, the API returns a score of
`0` with the raw model output included in the justification so a failure is
visible instead of silently crashing.

## Project Structure

```
smart-resume-screener/
├── backend/
│   ├── main.py            # FastAPI app & routes
│   ├── database.py        # SQLite schema + CRUD helpers
│   ├── resume_parser.py   # PDF/text extraction + rule-based field extraction
│   ├── matcher.py         # LLM prompt + Gemini API call
│   ├── models.py          # Pydantic request/response schemas
│   └── requirements.txt
├── frontend/
│   └── index.html         # Upload UI + ranked results table
├── .env.example
├── .gitignore
└── README.md
```

## Setup & Run

```bash
# 1. Clone and enter the repo
git clone <your-repo-url>
cd smart-resume-screener/backend

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your free Gemini API key (get one at https://aistudio.google.com/apikey)
cp ../.env.example .env
# then edit .env and add your real GOOGLE_API_KEY
export $(cat .env | xargs)   # or use a tool like python-dotenv / direnv

# 4. Run the server
uvicorn main:app --reload

# 5. Open the dashboard
# http://127.0.0.1:8000/
```

## API Endpoints

| Method | Endpoint                  | Description                              |
|--------|----------------------------|-------------------------------------------|
| POST   | `/api/job-descriptions`   | Save a job description                    |
| POST   | `/api/resumes`            | Upload + parse a resume (PDF/.txt)        |
| POST   | `/api/match`              | LLM-score one resume against one job      |
| GET    | `/api/results/{job_id}`   | Ranked, shortlisted candidates for a job  |

Candidates scoring **7 or higher** are marked "Shortlisted" in the results
(configurable via `SHORTLIST_THRESHOLD` in `main.py`).

## How to Use (Dashboard)

1. Paste a job description and click **Save Job**.
2. Upload one or more resumes (PDF or .txt) and click **Upload & Parse**.
3. Click **Match all uploaded resumes to job** — this calls the LLM once per
   resume and stores the score + justification.
4. Ranked, shortlisted candidates appear in the results table.

## Notes on Submission Compliance

- No `node_modules`, `.env`, build artifacts, or editor-specific files are
  committed (see `.gitignore`).
- Dependencies are kept minimal — only what's strictly required (6 packages).
- SQLite (stdlib-adjacent, file-based) is used instead of a heavier database
  to avoid extra infrastructure/services.

## 🎥 Demo Video
[Watch the 2-minute demo here](https://drive.google.com/file/d/1Jjf_3xPsCy41OnNA6ryl2RPC25Fadexc/view?usp=sharing)