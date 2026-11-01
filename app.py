import streamlit as st
import os
import io
import re
import json
from pypdf import PdfReader
from dotenv import load_dotenv

# Load local .env if available
load_dotenv()

# Streamlit page config
st.set_page_config(
    page_title="Smart Resume Screener",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------- Helper Functions & Skill Rules -----------------
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

def extract_text(filename: str, file_bytes: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return file_bytes.decode("utf-8", errors="ignore")

def extract_candidate_name(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
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

def parse_resume(filename: str, file_bytes: bytes) -> dict:
    text = extract_text(filename, file_bytes)
    return {
        "filename": filename,
        "raw_text": text,
        "candidate_name": extract_candidate_name(text),
        "skills": extract_skills(text),
        "education": extract_education(text),
    }

def score_with_gemini(api_key: str, parsed_resume: dict, job_title: str, job_text: str) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    prompt = f"""Compare the following resume with this job description and rate fit on 1-10 with justification.

Respond ONLY with a JSON object in this exact shape, no other text, no markdown fences:
{{"score": <integer 1-10>, "justification": "<concise explanation under 150 chars>"}}

Job Title: {job_title}
Job Description:
{job_text[:2500]}

Candidate Name: {parsed_resume.get("candidate_name", "Unknown")}
Extracted Skills: {", ".join(parsed_resume.get("skills", []))}
Extracted Education: {", ".join(parsed_resume.get("education", []))}
Resume Text:
{parsed_resume.get("raw_text", "")[:2500]}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=1024,
            response_mime_type="application/json",
        ),
    )
    raw_text = (response.text or "").strip()
    
    # Clean JSON
    cleaned = re.sub(r"^```json\s*|^```\s*|\s*```$", "", raw_text, flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
    except Exception:
        score_match = re.search(r'"score"\s*:\s*(\d+)', cleaned)
        just_match = re.search(r'"justification"\s*:\s*"([^"]*)', cleaned)
        score = int(score_match.group(1)) if score_match else 5
        just = just_match.group(1) if just_match else "Evaluation completed."
        data = {"score": score, "justification": just}

    score = max(1, min(10, int(data.get("score", 0))))
    return {
        "score": score,
        "justification": data.get("justification", "No justification provided.")
    }

# ----------------- UI Layout -----------------
# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.3rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .candidate-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        border: 1px solid #E5E7EB;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .score-badge {
        font-size: 1.4rem;
        font-weight: bold;
        padding: 4px 12px;
        border-radius: 8px;
        display: inline-block;
    }
    .shortlisted {
        background-color: #DEF7EC;
        color: #03543F;
        border: 1px solid #31C48D;
    }
    .not-shortlisted {
        background-color: #FDE8E8;
        color: #9B1C1C;
        border: 1px solid #F98080;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar: Settings & API Key
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/resume.png", width=64)
    st.title("Settings")
    
    # Check secrets or env first
    env_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if hasattr(st, "secrets") and "GOOGLE_API_KEY" in st.secrets:
        env_key = st.secrets["GOOGLE_API_KEY"]

    user_api_key = st.text_input(
        "Google Gemini API Key",
        value=env_key or "",
        type="password",
        help="Get a free key at https://aistudio.google.com/apikey"
    )
    
    threshold = st.slider("Shortlist Threshold (Score >=)", min_value=1, max_value=10, value=7)
    
    st.divider()
    st.markdown("### About Smart Resume Screener")
    st.caption("Intelligently parses resumes, extracts candidate details, and uses Gemini AI to evaluate fit against job requirements with instant scoring and justifications.")
    st.markdown("[⭐ View on GitHub](https://github.com/SatyaRamDinkar/smart-resume-screener)")

# Header
st.markdown('<div class="main-header">Smart Resume Screener 📄🤖</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Automated candidate matching and semantic resume evaluation powered by Gemini AI.</div>', unsafe_allow_html=True)

col1, col2 = st.columns([1, 1], gap="medium")

with col1:
    st.subheader("1. Job Description")
    job_title = st.text_input("Job Title", placeholder="e.g. Senior Python / Data Engineer")
    job_description = st.text_area(
        "Job Description & Requirements",
        height=220,
        placeholder="Paste full job description including requirements, qualifications, and responsibilities..."
    )

with col2:
    st.subheader("2. Upload Resumes")
    uploaded_files = st.file_uploader(
        "Upload Candidate Resumes (.pdf or .txt)",
        type=["pdf", "txt"],
        accept_multiple_files=True,
        help="You can upload multiple resumes at once to screen candidates simultaneously."
    )
    if uploaded_files:
        st.success(f"{len(uploaded_files)} resume(s) uploaded successfully.")

st.divider()

# Action Button
if st.button("🚀 Analyze & Screen Candidates", type="primary", use_container_width=True):
    if not user_api_key:
        st.error("⚠️ Please provide a Google Gemini API Key in the sidebar or via secrets.")
    elif not job_description.strip():
        st.error("⚠️ Please enter a Job Description.")
    elif not uploaded_files:
        st.error("⚠️ Please upload at least one resume (PDF or TXT).")
    else:
        results = []
        progress_bar = st.progress(0, text="Starting candidate screening...")
        
        for idx, file in enumerate(uploaded_files):
            file_bytes = file.read()
            progress_bar.progress((idx) / len(uploaded_files), text=f"Parsing {file.name}...")
            
            parsed = parse_resume(file.name, file_bytes)
            
            progress_bar.progress((idx + 0.5) / len(uploaded_files), text=f"Evaluating {parsed['candidate_name']} with Gemini AI...")
            try:
                eval_res = score_with_gemini(user_api_key, parsed, job_title, job_description)
                score = eval_res["score"]
                justification = eval_res["justification"]
            except Exception as e:
                score = 0
                justification = f"Error evaluating: {str(e)}"

            results.append({
                "filename": file.name,
                "candidate_name": parsed["candidate_name"],
                "skills": parsed["skills"],
                "education": parsed["education"],
                "score": score,
                "justification": justification,
                "shortlisted": score >= threshold
            })

        progress_bar.progress(1.0, text="Screening Complete!")

        # Sort results descending by score
        results.sort(key=lambda x: x["score"], reverse=True)

        st.subheader("📊 Candidate Ranking & Screening Results")
        
        # Summary metrics
        total = len(results)
        shortlisted_count = sum(1 for r in results if r["shortlisted"])
        avg_score = sum(r["score"] for r in results) / total if total > 0 else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Candidates Screened", total)
        m2.metric("Shortlisted Candidates", shortlisted_count, delta=f"{int(shortlisted_count/total*100)}%" if total else "0%")
        m3.metric("Average Fit Score", f"{avg_score:.1f} / 10")

        st.write("")

        # Display Candidate Cards
        for c in results:
            badge_class = "shortlisted" if c["shortlisted"] else "not-shortlisted"
            status_text = "✅ Shortlisted" if c["shortlisted"] else "❌ Not Shortlisted"
            
            with st.container():
                st.markdown(f"""
                <div class="candidate-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div>
                            <h3 style="margin: 0; color: #111827;">{c['candidate_name']}</h3>
                            <span style="color: #6B7280; font-size: 0.9rem;">File: {c['filename']}</span>
                        </div>
                        <div class="score-badge {badge_class}">
                            {c['score']} / 10 &nbsp;•&nbsp; {status_text}
                        </div>
                    </div>
                    <div style="margin-top: 10px;">
                        <strong>💡 AI Justification:</strong> {c['justification']}
                    </div>
                    <div style="margin-top: 8px;">
                        <strong>🛠️ Extracted Skills:</strong> {", ".join(c['skills']) if c['skills'] else "None detected"}
                    </div>
                    <div style="margin-top: 6px;">
                        <strong>🎓 Education:</strong> {", ".join(c['education']) if c['education'] else "Not specified"}
                    </div>
                </div>
                """, unsafe_allow_html=True)
