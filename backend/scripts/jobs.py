"""Inspect background job runs and replay dead letters (S4.1). Operator tool.

Usage (from backend/):
    python -m scripts.jobs [--status dead_letter|all|...] [--limit 20]
    python -m scripts.jobs --retry <job_run_id>
"""
from __future__ import annotations

import argparse
import sys

from app.database import SessionLocal
from app.db_models import JobRun


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", default="dead_letter", help="filter by status, or 'all'")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--retry", metavar="ID", help="re-enqueue a dead-lettered run with its original args")
    args = ap.parse_args(argv)
    with SessionLocal() as db:
        db.info["rls_bypass"] = True  # job_runs is not tenant-scoped, but stay explicit
        if args.retry:
            run = db.get(JobRun, args.retry)
            if run is None or run.status != "dead_letter":
                print(f"no dead-lettered run {args.retry}")
                return 1
            from app.worker.celery_app import app

            stored = run.args if isinstance(run.args, dict) else {}
            result = app.send_task(run.task, args=stored.get("args", []), kwargs=stored.get("kwargs", {}))
            print(f"re-enqueued {run.task} {stored} as {result.id}")
            return 0
        query = db.query(JobRun).order_by(JobRun.started_at.desc())
        if args.status != "all":
            query = query.filter(JobRun.status == args.status)
        runs = query.limit(args.limit).all()
        for r in runs:
            error = (r.last_error or "").splitlines()[-1:] or [""]
            print(f"{r.started_at:%Y-%m-%d %H:%M:%S}  {r.status:11}  {r.attempts}x  {r.task:40}  {r.id}  {error[0][:80]}")
        print(f"{len(runs)} run(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
