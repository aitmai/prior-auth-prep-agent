"""
Retention job — deletes cases (and their cascade-linked events, extracted
fields, policy check results, drafts, and denials) that have sat in a
terminal status past the retention window.

The --days default below is a PLACEHOLDER, not legal guidance. Actual
retention periods depend on applicable state medical-record-retention law
and payer contract terms and must be set by whoever owns compliance for
the deploying organization — see docs/compliance/data_retention_policy.md.

Usage:
    python db/retention_job.py --days 2555          # dry run (default)
    python db/retention_job.py --days 2555 --confirm  # actually deletes
"""
import argparse
import os
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
TERMINAL_STATUSES = ("approved", "denied", "closed")


def find_candidates(days):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT id, patient_name, status, updated_at FROM cases
           WHERE status = ANY(%s) AND updated_at < %s
           ORDER BY updated_at""",
        (list(TERMINAL_STATUSES), cutoff),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def delete_cases(case_ids):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    for cid in case_ids:
        # ON DELETE CASCADE on every child table takes care of case_events,
        # extracted_fields, policy_check_results, drafts, denials.
        cur.execute("DELETE FROM cases WHERE id = %s", (cid,))
    conn.commit()
    cur.close()
    conn.close()


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days", type=int, required=True,
        help="Retention window in days. Placeholder default intentionally omitted — "
             "set this from your organization's documented retention policy.",
    )
    parser.add_argument(
        "--confirm", action="store_true",
        help="Actually delete. Without this flag, only lists what would be deleted.",
    )
    args = parser.parse_args()

    candidates = find_candidates(args.days)
    if not candidates:
        print(f"No cases in a terminal status ({', '.join(TERMINAL_STATUSES)}) "
              f"older than {args.days} days.")
        return

    print(f"{len(candidates)} case(s) eligible for deletion "
          f"(status in {TERMINAL_STATUSES}, older than {args.days} days):")
    for c in candidates:
        print(f"  {c['id']}  {c['patient_name']!r}  {c['status']}  last updated {c['updated_at']}")

    if not args.confirm:
        print("\nDry run only — pass --confirm to actually delete these cases.")
        return

    delete_cases([c["id"] for c in candidates])
    print(f"\nDeleted {len(candidates)} case(s).")


if __name__ == "__main__":
    run()
