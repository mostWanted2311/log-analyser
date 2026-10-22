import json
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("DATABASE_PATH", "backend/data/infraguide.db"))


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize():
    with _connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS incidents (id TEXT PRIMARY KEY, filename TEXT NOT NULL, status TEXT NOT NULL, category TEXT NOT NULL, analysis TEXT NOT NULL, events TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS feedback (id TEXT PRIMARY KEY, incident_id TEXT NOT NULL, action_id TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS knowledge_chunks (chunk_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, title TEXT NOT NULL, publisher TEXT NOT NULL, url TEXT NOT NULL, product_family TEXT NOT NULL, product_version TEXT NOT NULL, retrieved_at TEXT NOT NULL, content TEXT NOT NULL);
        """)


def save_incident(incident_id, filename, category, analysis, events, created_at):
    with _connect() as db:
        db.execute("INSERT INTO incidents VALUES (?, ?, ?, ?, ?, ?, ?)", (incident_id, filename, "complete", category, analysis.model_dump_json(), json.dumps(events), created_at))


def get_incident(incident_id):
    with _connect() as db:
        row = db.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
    return dict(row) if row else None


def add_message(incident_id, role, content, created_at):
    with _connect() as db:
        db.execute("INSERT INTO conversations (incident_id, role, content, created_at) VALUES (?, ?, ?, ?)", (incident_id, role, content, created_at))
        rows = db.execute("SELECT role, content, created_at FROM conversations WHERE incident_id=? ORDER BY id DESC LIMIT 20", (incident_id,)).fetchall()
    return [dict(row) for row in reversed(rows)]


def get_messages(incident_id):
    with _connect() as db:
        rows = db.execute("SELECT role, content, created_at FROM conversations WHERE incident_id=? ORDER BY id DESC LIMIT 20", (incident_id,)).fetchall()
    return [dict(row) for row in reversed(rows)]


def save_feedback(feedback_id, incident_id, action_id, payload, created_at):
    with _connect() as db:
        db.execute("INSERT INTO feedback VALUES (?, ?, ?, ?, ?)", (feedback_id, incident_id, action_id, json.dumps(payload), created_at))

def get_feedback(incident_id):
    with _connect() as db:
        rows = db.execute("SELECT action_id, payload, created_at FROM feedback WHERE incident_id=? ORDER BY created_at", (incident_id,)).fetchall()
    return [{"action_id": row["action_id"], **json.loads(row["payload"]), "created_at": row["created_at"]} for row in rows]

def save_knowledge_chunks(chunks):
    with _connect() as db:
        db.executemany("INSERT OR REPLACE INTO knowledge_chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", chunks)


def search_knowledge_chunks(terms, count=12):
    if not terms:
        return []
    predicates = " OR ".join("lower(content) LIKE ? OR lower(title) LIKE ?" for _ in terms)
    parameters = []
    for term in terms:
        pattern = f"%{term.lower()}%"
        parameters.extend([pattern, pattern])
    with _connect() as db:
        rows = db.execute(f"SELECT * FROM knowledge_chunks WHERE {predicates} LIMIT ?", (*parameters, count * 4)).fetchall()
    return [dict(row) for row in rows]