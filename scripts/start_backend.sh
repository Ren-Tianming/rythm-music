#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv_python="${project_dir}/backend/.venv/bin/python"

if [[ ! -x "${venv_python}" ]]; then
  echo "backend/.venv is missing. Run ./scripts/setup_local.sh first." >&2
  exit 1
fi

cd "${project_dir}"
export PYTHONPATH="${project_dir}/backend"
"${venv_python}" -m alembic -c backend/alembic.ini upgrade head
exec "${venv_python}" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
