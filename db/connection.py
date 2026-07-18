import os

import psycopg2
import psycopg2.extras


def get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def query(sql, params=None, fetch=True):
    """Small helper — opens, executes, optionally fetches as dicts, closes.
    Fine for a demo's request volume; swap for a pooled connection
    (e.g. psycopg2.pool or SQLAlchemy) before any real production load."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params or ())
    result = cur.fetchall() if fetch else None
    conn.commit()
    cur.close()
    conn.close()
    return result
