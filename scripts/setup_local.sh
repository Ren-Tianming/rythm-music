#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv_dir="${project_dir}/backend/.venv"
python_bin="${RYTHM_PYTHON:-python3}"

if ! "${python_bin}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "[RyThM Music] Python 3.11 or newer is required. Set RYTHM_PYTHON to a compatible interpreter." >&2
  exit 1
fi

echo "[RyThM Music] Creating Python virtual environment"
"${python_bin}" -m venv "${venv_dir}"

echo "[RyThM Music] Installing backend dependencies into backend/.venv"
"${venv_dir}/bin/python" -m pip install --upgrade pip
"${venv_dir}/bin/python" -m pip install -r "${project_dir}/backend/requirements-dev.txt"

echo "[RyThM Music] Installing frontend dependencies"
npm --cache "${project_dir}/frontend/.npm-cache" --prefix "${project_dir}/frontend" ci

if [[ ! -f "${project_dir}/.env" ]]; then
  cp "${project_dir}/.env.example" "${project_dir}/.env"
fi

echo "[RyThM Music] Setup complete"
echo "Backend venv: ${venv_dir}"
