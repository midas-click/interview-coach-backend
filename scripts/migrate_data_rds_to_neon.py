"""One-off data migration: RDS -> Neon (same schema, data-only COPY).

Usage: RDS_PWD=... NEON_URL=... python scripts/migrate_data_rds_to_neon.py
"""

from __future__ import annotations

import os
import sys

import psycopg

# FK-safe insert order (parents before children).
TABLE_ORDER = [
    "users",
    "interviews",
    "transcripts",
    "questions",
    "answers",
    "interview_analyses",
    "english_analyses",
    "vocabulary_items",
    "question_reviews",
    "transcript_corrections",
    "recommendations",
    "metrics",
    "learning_topics",
]

RDS_URL = (
    "postgresql://interview_admin:{pwd}"
    "@interview-intelligence.c9cwso4yqgf5.us-east-2.rds.amazonaws.com:5432/interview_intelligence"
)


def main() -> int:
    rds_pwd = os.environ.get("RDS_PWD")
    neon_url = os.environ.get("NEON_URL")
    if not rds_pwd or not neon_url:
        print("usage: RDS_PWD=... NEON_URL=... python scripts/migrate_data_rds_to_neon.py")
        return 1

    src = psycopg.connect(RDS_URL.format(pwd=rds_pwd), autocommit=True)
    # Neon URL is stored in SQLAlchemy form (postgresql+psycopg://); psycopg
    # needs the plain postgresql:// scheme.
    neon_url = neon_url.replace("postgresql+psycopg://", "postgresql://", 1)
    dst = psycopg.connect(neon_url, autocommit=True)

    with src.cursor() as s, dst.cursor() as d:
        src_tables = {
            r[0]
            for r in s.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            )
        }
        dst_tables = {
            r[0]
            for r in d.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            )
        }
        tables = [t for t in TABLE_ORDER if t in src_tables and t in dst_tables]
        missing = (src_tables ^ dst_tables) - {"alembic_version"}
        if missing:
            print(f"WARNING: schema differs — {sorted(missing)}")

        # Clear Neon (removes the seeded admin + any test rows).
        d.execute("TRUNCATE users, interviews CASCADE")

        for t in tables:
            src_count = s.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
            if src_count == 0:
                print(f"{t}: 0 rows (skip)")
                continue
            with s.copy(f'COPY (SELECT * FROM "{t}") TO STDOUT') as out, \
                 d.copy(f'COPY "{t}" FROM STDIN') as inp:
                while (chunk := out.read()) != b"":
                    inp.write(chunk)
            dst_count = d.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
            status = "OK" if src_count == dst_count else "MISMATCH!"
            print(f"{t}: {src_count} -> {dst_count} rows {status}")

    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
