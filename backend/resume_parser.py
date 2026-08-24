"""
resume_parser.py
-----------------
Extracts raw text from an uploaded resume (PDF or plain text) and pulls out
structured fields (name, skills, education, experience) using lightweight
rule-based parsing. Semantic *matching/scoring* against a job description is
handled separately by the LLM in matcher.py — this module only prepares
structured data for that step.
"""

import io
import re
from pypdf import PdfReader

# A reasonably broad, easily-extended skills vocabulary. Keeping this
# rule-based (instead of another LLM call) keeps the pipeline fast and
# avoids unnecessary API usage for a task that doesn't need semantics.
SKILL_KEYWORDS = [
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "sql", "nosql", "mongodb", "postgresql", "mysql", "sqlite",
    "react", "angular", "vue", "node.js", "node", "express", "django",
    "flask", "fastapi", "spring", "spring boot",
    "html", "css", "tailwind", "bootstrap",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd",
    "git", "github", "gitlab",
    "machine learning", "deep learning", "nlp", "llm", "pytorch",
    "tensorflow", "scikit-learn", "pandas", "numpy",
    "rest api", "graphql", "microservices",
    "agile", "scrum", "linux", "bash",
]

EDUCATION_KEYWORDS = [
    "bachelor", "b.tech", "b.e.", "bsc", "b.sc", "master", "m.tech", "m.e.",
    "msc", "m.sc", "mba", "phd", "ph.d", "diploma", "university", "college",
    "institute of technology",
]

EXPERIENCE_LINE_PATTERN = re.compile(
    r"(?P<title>[A-Za-z][A-Za-z .]+?)\s+\bat\b\s+(?P<company>[A-Za-z0-9 .&]+?)"
    r"\s*(?:\(|\-|–)?\s*(?P<dates>\d{4}\s*[-–—]\s*(?:\d{4}|present|Present))?",
)


def extract_text(filename: str, file_bytes: bytes) -> str:
    """Extract raw text from a PDF or plain-text upload."""
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    # Fallback: treat as UTF-8 text
    return file_bytes.decode("utf-8", errors="ignore")


def extract_candidate_name(text: str) -> str:
    """Best-effort guess: first non-empty line that looks like a name."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip lines that look like headers/emails/phone numbers
        if "@" in line or any(ch.isdigit() for ch in line):
            continue
        words = line.split()
        if 1 <= len(words) <= 4:
            return line
    return "Unknown Candidate"


def extract_skills(text: str) -> list:
    lower = text.lower()
    found = []
    for kw in SKILL_KEYWORDS:
        # Word-boundary match so "sql" doesn't fire inside "postgresql", etc.
        pattern = r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])"
        if re.search(pattern, lower):
            found.append(kw)
    return found


def extract_education(text: str) -> list:
    lines = text.splitlines()
    hits = []
    for line in lines:
        low = line.lower()
        if any(kw in low for kw in EDUCATION_KEYWORDS):
            cleaned = line.strip()
            if cleaned:
                hits.append(cleaned)
    return hits[:5]


def extract_experience(text: str) -> list:
    """Grab lines that look like 'Title at Company (Year - Year)' style entries."""
    hits = []
    for line in text.splitlines():
        match = EXPERIENCE_LINE_PATTERN.search(line)
        if match and match.group("company"):
            hits.append(line.strip())
    return hits[:10]


def parse_resume(filename: str, file_bytes: bytes) -> dict:
    text = extract_text(filename, file_bytes)
    return {
        "raw_text": text,
        "candidate_name": extract_candidate_name(text),
        "skills": extract_skills(text),
        "education": extract_education(text),
        "experience": extract_experience(text),
    }
