"""Pydantic request/response schemas for the FastAPI app."""

from pydantic import BaseModel
from typing import List, Optional


class JobDescriptionIn(BaseModel):
    title: Optional[str] = "Untitled Role"
    text: str


class MatchRequest(BaseModel):
    resume_id: int
    job_id: int


class ResumeOut(BaseModel):
    id: int
    filename: str
    candidate_name: str
    skills: List[str]
    education: List[str]
    experience: List[str]


class MatchOut(BaseModel):
    match_id: int
    resume_id: int
    job_id: int
    score: int
    justification: str


class CandidateResult(BaseModel):
    match_id: int
    resume_id: int
    filename: str
    candidate_name: str
    skills: List[str]
    score: int
    justification: str
    shortlisted: bool
