"""
matcher.py
----------
Uses Google Gemini to semantically compare a parsed resume against a job
description and produce a 1-10 fit score with justification.
"""

import os
import re
import json
from google import genai
from google.genai import types

MODEL = "gemini-3.6-flash"

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. Add it to backend/.env before calling /match. "
                "Get a free key at https://aistudio.google.com/apikey"
            )
        _client = genai.Client(api_key=api_key)
    return _client


PROMPT_TEMPLATE = """Compare the following resume with this job description and rate fit on 1-10 with justification.

Respond ONLY with a JSON object in this exact shape, no other text, no markdown fences.
Keep the justification under 120 characters.
{{"score": <integer 1-10>, "justification": "<concise explanation under 120 chars>"}}

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


def _parse_field(field):
    if isinstance(field, str):
        try:
            data = json.loads(field)
            return ", ".join(data) if isinstance(data, list) else str(data)
        except json.JSONDecodeError:
            return field
    return ", ".join(field) if isinstance(field, list) else str(field)


def build_prompt(resume: dict, job_text: str) -> str:
    return PROMPT_TEMPLATE.format(
        candidate_name=resume.get("candidate_name", "Unknown"),
        skills=_parse_field(resume.get("skills", [])),
        education=_parse_field(resume.get("education", [])),
        experience=_parse_field(resume.get("experience", [])),
        resume_text=resume.get("raw_text", "")[:4000],
        job_text=job_text[:3000],
    )


def _extract_json(text: str) -> dict:
    """Aggressively extract JSON from model response, even if truncated."""
    if not text:
        raise ValueError("Empty response")

    text = text.strip().lstrip("\ufeff")
    cleaned = re.sub(r"^```json\s*|^```\s*|\s*```$", "", text, flags=re.MULTILINE).strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find first { and last }
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start:end+1])
        except json.JSONDecodeError:
            pass

    # Regex for complete JSON
    match = re.search(r'\{\s*"score"\s*:\s*\d+.*?"justification"\s*:\s*".*?"\s*\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # FALLBACK: Extract score and justification even from truncated JSON
    score_match = re.search(r'"score"\s*:\s*(\d+)', cleaned)
    just_match = re.search(r'"justification"\s*:\s*"([^"]*)', cleaned, re.DOTALL)

    if score_match:
        score = int(score_match.group(1))
        justification = just_match.group(1).strip() if just_match else "Justification truncated by model."
        return {"score": score, "justification": justification}

    raise ValueError(f"No valid JSON found. Raw: {cleaned[:200]}")


def score_resume_against_job(resume: dict, job_text: str) -> dict:
    client = _get_client()
    prompt = build_prompt(resume, job_text)

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=1024,  # Doubled from 500
        ),
    )
    text = (response.text or "").strip()

    try:
        data = _extract_json(text)
        score = int(data["score"])
        justification = str(data["justification"])
    except Exception as e:
        score = 0
        justification = f"Parse error: {str(e)[:200]}"

    score = max(1, min(10, score)) if score else 0
    return {"score": score, "justification": justification}