"""
main.py
-------
FastAPI backend for the Smart Resume Screener.

Endpoints:
  POST /api/resumes            -> upload + parse a resume (PDF or .txt)
  POST /api/job-descriptions   -> submit a job description
  POST /api/match              -> LLM-score one resume against one job
  GET  /api/results/{job_id}   -> ranked, shortlisted candidates for a job

Run with:
  uvicorn main:app --reload
"""

import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import database as db
import resume_parser
import matcher
from models import JobDescriptionIn, MatchRequest, CandidateResult

SHORTLIST_THRESHOLD = 7  # score >= this is considered "shortlisted"

app = FastAPI(title="Smart Resume Screener")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    db.init_db()


@app.post("/api/resumes")
async def upload_resume(file: UploadFile = File(...)):
    if not (file.filename.lower().endswith(".pdf") or file.filename.lower().endswith(".txt")):
        raise HTTPException(400, "Only .pdf or .txt resumes are supported.")

    file_bytes = await file.read()
    parsed = resume_parser.parse_resume(file.filename, file_bytes)

    resume_id = db.insert_resume(
        filename=file.filename,
        raw_text=parsed["raw_text"],
        candidate_name=parsed["candidate_name"],
        skills=parsed["skills"],
        education=parsed["education"],
        experience=parsed["experience"],
    )
    return {
        "id": resume_id,
        "filename": file.filename,
        "candidate_name": parsed["candidate_name"],
        "skills": parsed["skills"],
        "education": parsed["education"],
        "experience": parsed["experience"],
    }


@app.post("/api/job-descriptions")
def create_job_description(job: JobDescriptionIn):
    job_id = db.insert_job_description(job.title, job.text)
    return {"id": job_id, "title": job.title}


@app.post("/api/match")
def match(req: MatchRequest):
    resume = db.get_resume(req.resume_id)
    job = db.get_job(req.job_id)
    if not resume:
        raise HTTPException(404, "Resume not found")
    if not job:
        raise HTTPException(404, "Job description not found")

    result = matcher.score_resume_against_job(resume, job["raw_text"])
    match_id = db.insert_match(
        req.resume_id, req.job_id, result["score"], result["justification"]
    )
    return {
        "match_id": match_id,
        "resume_id": req.resume_id,
        "job_id": req.job_id,
        "score": result["score"],
        "justification": result["justification"],
    }


@app.get("/api/results/{job_id}", response_model=list[CandidateResult])
def get_results(job_id: int):
    rows = db.list_matches_for_job(job_id)
    results = []
    for r in rows:
        results.append(
            CandidateResult(
                match_id=r["id"],
                resume_id=r["resume_id"],
                filename=r["filename"],
                candidate_name=r["candidate_name"] or "Unknown",
                skills=json.loads(r["skills"]) if r["skills"] else [],
                score=r["score"],
                justification=r["justification"],
                shortlisted=r["score"] >= SHORTLIST_THRESHOLD,
            )
        )
    return results


# Serve the simple dashboard frontend at "/"
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
