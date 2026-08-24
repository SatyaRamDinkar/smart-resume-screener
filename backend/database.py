"""
database.py
------------
Minimal SQLite persistence layer for the Smart Resume Screener.
We use the Python standard-library `sqlite3` module directly (no ORM)
to keep dependencies minimal, per the assignment's packaging guidance.
"""

import sqlite3
import os
import json
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "resume_screener.db")


def init_db():
    """Create tables if they do not already exist."""
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                candidate_name TEXT,
                skills TEXT,           -- JSON list
                education TEXT,        -- JSON list
                experience TEXT,       -- JSON list
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_descriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                raw_text TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_id INTEGER NOT NULL,
                job_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                justification TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (resume_id) REFERENCES resumes (id),
                FOREIGN KEY (job_id) REFERENCES job_descriptions (id)
            )
            """
        )
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def insert_resume(filename, raw_text, candidate_name, skills, education, experience):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO resumes
               (filename, raw_text, candidate_name, skills, education, experience)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                filename,
                raw_text,
                candidate_name,
                json.dumps(skills),
                json.dumps(education),
                json.dumps(experience),
            ),
        )
        conn.commit()
        return cur.lastrowid


def insert_job_description(title, raw_text):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO job_descriptions (title, raw_text) VALUES (?, ?)",
            (title, raw_text),
        )
        conn.commit()
        return cur.lastrowid


def insert_match(resume_id, job_id, score, justification):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO matches (resume_id, job_id, score, justification)
               VALUES (?, ?, ?, ?)""",
            (resume_id, job_id, score, justification),
        )
        conn.commit()
        return cur.lastrowid


def get_resume(resume_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
        return dict(row) if row else None


def get_job(job_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM job_descriptions WHERE id = ?", (job_id,)
        ).fetchone()
        return dict(row) if row else None


def list_matches_for_job(job_id):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.score, m.justification, m.created_at,
                   r.id AS resume_id, r.filename, r.candidate_name, r.skills
            FROM matches m
            JOIN resumes r ON r.id = m.resume_id
            WHERE m.job_id = ?
            ORDER BY m.score DESC
            """,
            (job_id,),
        ).fetchall()
        return [dict(r) for r in rows]
