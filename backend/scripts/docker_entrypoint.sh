#!/bin/sh
# Seed the database on first start (empty volume), then serve the API.
set -e
python - <<'PY' || python -m finops.pipeline --source "${SEED_SOURCE:-simulator}"
import os, sqlite3, sys
c = sqlite3.connect(os.environ["FINOPS_DB_PATH"])
has = c.execute("select count(*) from sqlite_master where name='cost_allocations'").fetchone()[0]
sys.exit(0 if has and c.execute("select count(*) from cost_allocations").fetchone()[0] else 1)
PY
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
