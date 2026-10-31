#!/usr/bin/env bash
set -euo pipefail

# Resolve paths relative to this script, even when invoked outside the checkout.
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

for arg in "$@"; do
  case "$arg" in
    --help|-h)
      printf '%s\n' 'Usage: scripts/setup_local.sh [--no-input] [--skip-superuser]' \
        'Requires Python 3.10–3.12 and a running PostgreSQL server.' \
        'Creates .venv and .env, installs dependencies, creates the database if needed,' \
        'runs migrations and Django checks, and optionally creates a superuser.' \
        'Set PYTHON to select an interpreter or VENV_DIR to choose a virtualenv.' \
        '--no-input uses DB_* / DATABASE_URL environment values or local defaults' \
        'for a new .env, creates a missing database, and skips superuser creation.'
      exit 0 ;;
    --no-input|--skip-superuser) ;;
    *) printf 'Unknown option: %s (use --help)\n' "$arg" >&2; exit 1 ;;
  esac
done

compatible_python() {
  "$1" -c 'import sys; sys.exit(not ((3, 10) <= sys.version_info[:2] <= (3, 12)))' >/dev/null 2>&1
}

VENV_DIR="${VENV_DIR:-.venv}"
if [[ "$VENV_DIR" != /* ]]; then
  VENV_DIR="$PROJECT_ROOT/$VENV_DIR"
fi
PY_BIN="$VENV_DIR/bin/python"
if [[ -e "$VENV_DIR" ]]; then
  if [[ ! -x "$PY_BIN" ]] || ! compatible_python "$PY_BIN"; then
    printf 'Existing virtualenv %s is broken or requires Python 3.10–3.12.\n' "$VENV_DIR" >&2
    printf '%s\n' 'Choose a new location with VENV_DIR=.venv-new; the existing environment was preserved.' >&2
    exit 1
  fi
else
  if [[ -n "${PYTHON:-}" ]]; then
    if ! compatible_python "$PYTHON"; then
      printf 'PYTHON must point to a working Python 3.10–3.12 interpreter.\n' >&2
      exit 1
    fi
  else
    PYTHON=""
    for candidate in python3.12 python3.11 python3.10 python3; do
      if command -v "$candidate" >/dev/null 2>&1 && compatible_python "$candidate"; then
        PYTHON="$candidate"
        break
      fi
    done
    if [[ -z "$PYTHON" ]]; then
      printf '%s\n' 'Install Python 3.10–3.12, then rerun (macOS: brew install python@3.12).' >&2
      exit 1
    fi
  fi
  "$PYTHON" -m venv "$VENV_DIR"
fi

printf '\n=== WolfKey Local Setup ===\n'
"$PY_BIN" --version
# Use the environment's interpreter, not a pip script with a potentially stale shebang.
"$PY_BIN" -m pip install --disable-pip-version-check --upgrade pip wheel
"$PY_BIN" -m pip install --disable-pip-version-check -r requirements.txt
"$PY_BIN" -m pip check
"$PY_BIN" scripts/setup_local.py "$@"
printf '\nActivate the environment: source "%s/bin/activate"\n' "$VENV_DIR"
