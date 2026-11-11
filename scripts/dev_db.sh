#!/usr/bin/env bash
# Manages a project-local PostgreSQL cluster for development (no Docker, no system service).
# The cluster lives in .local/pgdata and listens only on 127.0.0.1:$POSTGRES_PORT.
#
# Usage: scripts/dev_db.sh {init|start|stop|status|psql}
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"
[[ -f "$ENV_FILE" ]] || { echo "Missing .env — copy .env.example to .env first." >&2; exit 1; }
set -a; source "$ENV_FILE"; set +a

PGDATA_DIR="$ROOT/.local/pgdata"
LOG_FILE="$ROOT/.local/postgres.log"

# Prefer binaries on PATH; fall back to the Homebrew keg-only location.
if ! command -v pg_ctl >/dev/null 2>&1; then
  for candidate in /opt/homebrew/opt/postgresql@16/bin /usr/local/opt/postgresql@16/bin; do
    [[ -x "$candidate/pg_ctl" ]] && PATH="$candidate:$PATH" && break
  done
fi
command -v pg_ctl >/dev/null 2>&1 || { echo "PostgreSQL binaries not found (pg_ctl)." >&2; exit 1; }

is_running() { pg_ctl -D "$PGDATA_DIR" status >/dev/null 2>&1; }

start() {
  if is_running; then echo "PostgreSQL already running on port $POSTGRES_PORT."; return; fi
  pg_ctl -D "$PGDATA_DIR" -l "$LOG_FILE" -w \
    -o "-p $POSTGRES_PORT -c listen_addresses=127.0.0.1 -c unix_socket_directories=''" start >/dev/null
  echo "PostgreSQL started on 127.0.0.1:$POSTGRES_PORT."
}

case "${1:-}" in
  init)
    if [[ -d "$PGDATA_DIR" ]]; then
      echo "Cluster already initialised at $PGDATA_DIR."
    else
      mkdir -p "$ROOT/.local"
      pwfile="$(mktemp)"; trap 'rm -f "$pwfile"' EXIT
      printf '%s' "$POSTGRES_PASSWORD" > "$pwfile"
      initdb -D "$PGDATA_DIR" -U "$POSTGRES_USER" --pwfile="$pwfile" \
        --auth=scram-sha-256 --encoding=UTF8 --locale=C >/dev/null
      echo "Cluster initialised at $PGDATA_DIR."
    fi
    start
    export PGPASSWORD="$POSTGRES_PASSWORD"
    for db in "$POSTGRES_DB" "$POSTGRES_TEST_DB"; do
      exists="$(psql -h 127.0.0.1 -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d postgres -tAc \
        "SELECT 1 FROM pg_database WHERE datname = '$db'")"
      if [[ "$exists" != "1" ]]; then
        createdb -h 127.0.0.1 -p "$POSTGRES_PORT" -U "$POSTGRES_USER" "$db"
        echo "Database $db created."
      fi
    done
    ;;
  start) start ;;
  stop)
    if is_running; then pg_ctl -D "$PGDATA_DIR" -m fast -w stop >/dev/null; echo "PostgreSQL stopped."
    else echo "PostgreSQL is not running."; fi
    ;;
  status)
    if is_running; then echo "running on 127.0.0.1:$POSTGRES_PORT"; else echo "stopped"; exit 3; fi
    ;;
  psql)
    shift
    PGPASSWORD="$POSTGRES_PASSWORD" exec psql -h 127.0.0.1 -p "$POSTGRES_PORT" \
      -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"
    ;;
  *)
    echo "Usage: $0 {init|start|stop|status|psql}" >&2; exit 2 ;;
esac
