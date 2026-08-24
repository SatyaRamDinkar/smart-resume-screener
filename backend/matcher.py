"""
matcher.py
----------
Uses an LLM (Google Gemini, free tier) to semantically compare a parsed
resume against a job description and produce a 1-10 fit score with
justification. This is the "LLM Usage" piece called out in the assignment
brief.

Requires the environment variable GOOGLE_API_KEY to be set.
Get a free key at: https://aistudio.google.com/apikey
"""

import os
import re
import json
from google import genai
from google.genai import types

MODEL = "gemini-2.0-flash"  # fast + free-tier friendly

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. Add it to your .env file "
                "(see .env.example) before calling /match. Get a free key "
                "at https://aistudio.google.com/apikey"
            )
        _client = genai.Client(api_key=api_key)
    return _client


PROMPT_TEMPLATE = """Compare the following resume with this job description and \
rate fit on 1-10 with justification.

Respond ONLY with a JSON object in this exact shape, no other text, no markdown fences:
{{"score": <integer 1-10>, "justification": "<2-3 sentence explanation>"}}

Resume:
Candidate: {candidate_name}
Extracted skills: {skills}
Extracted education: {education}
Extracted experience: {experience}
Full resume text:
{resume_text}

Job Description:
{job_text}
"""


def build_prompt(resume: dict, job_text: str) -> str:
    return PROMPT_TEMPLATE.format(
        candidate_name=resume.get("candidate_name", "Unknown"),
        skills=", ".join(json.loads(resume["skills"])) if isinstance(resume["skills"], str) else resume["skills"],
        education=resume.get("education", []),
        experience=resume.get("experience", []),
        resume_text=resume.get("raw_text", "")[:4000],  # keep prompt bounded
        job_text=job_text[:3000],
    )


def score_resume_against_job(resume: dict, job_text: str) -> dict:
    """Calls Gemini to get a {score, justification} dict for one resume/job pair."""
    client = _get_client()
    prompt = build_prompt(resume, job_text)

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=300),
    )
    text = (response.text or "").strip()

    # Be defensive: strip code fences if the model adds them, then parse JSON.
    cleaned = re.sub(r"```json|```", "", text).strip()
    try:
        data = json.loads(cleaned)
        score = int(data["score"])
        justification = str(data["justification"])
    except (json.JSONDecodeError, KeyError, ValueError):
        # Fallback so a malformed LLM response never crashes the API
        score = 0
        justification = f"Could not parse LLM response: {text[:200]}"

    score = max(1, min(10, score)) if score else 0
    return {"score": score, "justification": justification}
