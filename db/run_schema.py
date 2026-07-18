"""
Alternative to running schema.sql via the psql CLI.
Useful if psql isn't installed locally, or you'd rather not deal with
shell quoting around $DATABASE_URL.

Usage:
    python db/run_schema.py
Requires DATABASE_URL in the environment (loaded from .env).
"""
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def run():
    with open("db/schema.sql", "r") as f:
        schema_sql = f.read()

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(schema_sql)
    conn.commit()
    cur.close()
    conn.close()
    print("Schema created successfully.")


if __name__ == "__main__":
    run()
