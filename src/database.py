import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "tasks.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    # Enable WAL mode for concurrent reads/writes
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                pdf_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                error_msg TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        # One row per chunk we actually inserted into Vectorize.
        # (pdf_id, page_number, chunk_index) are exactly the three pieces
        # that build a vector ID — so this table lets us rebuild every ID
        # for a PDF at delete time without re-downloading/re-chunking it.
        conn.execute('''
            CREATE TABLE IF NOT EXISTS chunks (
                pdf_id TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                PRIMARY KEY (pdf_id, page_number, chunk_index)
            )
        ''')
        conn.commit()
    finally:
        conn.close()

def create_task(pdf_id: str, filename: str):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO tasks (pdf_id, filename, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (pdf_id, filename, 'UPLOADED', now, now))
        conn.commit()
    finally:
        conn.close()

def update_task_status(pdf_id: str, status: str, error_msg: str = None):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        if error_msg is not None:
            conn.execute('''
                UPDATE tasks 
                SET status = ?, updated_at = ?, error_msg = ?
                WHERE pdf_id = ?
            ''', (status, now, error_msg, pdf_id))
        else:
            conn.execute('''
                UPDATE tasks 
                SET status = ?, updated_at = ?
                WHERE pdf_id = ?
            ''', (status, now, pdf_id))
        conn.commit()
    finally:
        conn.close()

def increment_task_attempts(pdf_id: str):
    conn = get_db_connection()
    try:
        conn.execute('''
            UPDATE tasks 
            SET attempts = attempts + 1
            WHERE pdf_id = ?
        ''', (pdf_id,))
        conn.commit()
        
        # Return the new attempts count
        cursor = conn.execute('SELECT attempts FROM tasks WHERE pdf_id = ?', (pdf_id,))
        row = cursor.fetchone()
        return row['attempts'] if row else 0
    finally:
        conn.close()

def get_task(pdf_id: str):
    conn = get_db_connection()
    try:
        cursor = conn.execute('SELECT * FROM tasks WHERE pdf_id = ?', (pdf_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def list_tasks():
    conn = get_db_connection()
    try:
        cursor = conn.execute('SELECT * FROM tasks ORDER BY created_at DESC')
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def delete_task(pdf_id: str):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM tasks WHERE pdf_id = ?', (pdf_id,))
        conn.commit()
    finally:
        conn.close()

def save_chunks(pdf_id: str, chunks: list[dict]):
    # Record one row per chunk after a successful Vectorize insert.
    # executemany runs the same INSERT for every row in the list.
    # INSERT OR REPLACE keeps this idempotent — re-processing the same PDF
    # just overwrites the identical rows instead of erroring on the primary key.
    rows = [(pdf_id, c["page_number"], c["chunk_index"]) for c in chunks]
    conn = get_db_connection()
    try:
        conn.executemany('''
            INSERT OR REPLACE INTO chunks (pdf_id, page_number, chunk_index)
            VALUES (?, ?, ?)
        ''', rows)
        conn.commit()
    finally:
        conn.close()

def get_chunks(pdf_id: str) -> list[dict]:
    # Returns [{page_number, chunk_index}, ...] for a PDF — used to rebuild vector IDs.
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            'SELECT page_number, chunk_index FROM chunks WHERE pdf_id = ?',
            (pdf_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def delete_chunks(pdf_id: str):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM chunks WHERE pdf_id = ?', (pdf_id,))
        conn.commit()
    finally:
        conn.close()

# Initialize the database table when this module is imported
init_db()
