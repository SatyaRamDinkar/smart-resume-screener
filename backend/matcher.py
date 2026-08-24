"""
matcher.py
----------
Uses an LLM (Claude, via the Anthropic API) to semantically compare a
parsed resume against a job description and produce a 1-10 fit score with
justification. This is the "LLM Usage" piece called out in the assignment
brief.

Requires the environment variable ANTHROPIC_API_KEY to be set.
"""

import os
import re
import json
from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"

client = None


def get_client() -> Anthropic:
    global client
    if client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file "
                "(see .env.example) before calling /match."
            )
        client = Anthropic(api_key=api_key)
    return client


PROMPT_TEMPLATE = """Compare the following resume with this job description and \
rate fit on 1-10 with justification.

Respond ONLY with a JSON object in this exact shape, no other text:
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
    """Calls Claude to get a {score, justification} dict for one resume/job pair."""
    prompt = build_prompt(resume, job_text)
    response = get_client().messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")

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
