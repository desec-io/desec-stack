#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="docker compose -f ${ROOT_DIR}/docker-compose.yml -f ${ROOT_DIR}/docker-compose.test-api.yml"
BUILD_IMAGES_DB=(dbapi)
BUILD=1
PROD_DB=0
PROD_USER="root"
PROD_HOST="digga.desec.io"
PROD_REFRESH=0
CACHE_DIR="${ROOT_DIR}/.cache/prod-db"
CACHE_FILE="${CACHE_DIR}/dbapi.sql.gz"

usage() {
  cat <<'EOF'
Usage: ./run-api-tests-stack.sh [--no-build] [--prod-db] [--prod-user USER] [--prod-host HOST] [--refresh-prod-db]
  --no-build  Skip docker image build step
  --prod-db   Download a logical dbapi dump from production and load it locally
  --prod-user SSH username for prod (default: root)
  --prod-host SSH hostname for prod (default: desec.io)
  --refresh-prod-db  Re-download prod db dump even if cache exists
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-build) BUILD=0 ;;
    --prod-db) PROD_DB=1 ;;
    --prod-user)
      shift
      PROD_USER="${1:-}"
      [[ -n "$PROD_USER" ]] || { echo "Missing value for --prod-user" >&2; exit 1; }
      ;;
    --prod-host)
      shift
      PROD_HOST="${1:-}"
      [[ -n "$PROD_HOST" ]] || { echo "Missing value for --prod-host" >&2; exit 1; }
      ;;
    --refresh-prod-db) PROD_REFRESH=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

prod_remote_script() {
  cat <<'EOF'
set -euo pipefail
cd /root/desec-stack
docker compose -f docker-compose.yml exec -T dbapi pg_dump -Fc -U desec desec | gzip -c
EOF
}

download_prod_dbapi() {
  mkdir -p "$CACHE_DIR"
  if [[ "$PROD_REFRESH" -eq 0 && -f "$CACHE_FILE" ]]; then
    echo "Using cached prod db dump at ${CACHE_FILE}"
    return
  fi

  local prod_ssh="${PROD_USER}@${PROD_HOST}"
  echo "About to run the following read-only commands on ${prod_ssh}:"
  prod_remote_script
  read -r -p "Continue? [y/N] " reply
  case "$reply" in
    y|Y|yes|YES) ;;
    *) echo "Aborted." >&2; exit 1 ;;
  esac

  local tmp_file
  local old_umask
  old_umask="$(umask)"
  umask 077
  tmp_file="$(mktemp "${CACHE_FILE}.tmp.XXXXXX")"
  umask "$old_umask"
  if prod_remote_script | ssh -4 "$prod_ssh" "bash -s" > "$tmp_file"; then
    mv "$tmp_file" "$CACHE_FILE"
    echo "Saved prod db dump to ${CACHE_FILE}"
  else
    rm -f "$tmp_file"
    echo "Failed to download prod db dump; cache not updated." >&2
    exit 1
  fi
}

restore_dbapi_from_cache() {
  if [[ ! -f "$CACHE_FILE" ]]; then
    echo "Missing cache file: ${CACHE_FILE}" >&2
    exit 1
  fi
  $COMPOSE exec -T dbapi sh -c "psql -U postgres -d postgres -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='desec' AND pid <> pg_backend_pid();\""
  $COMPOSE exec -T dbapi sh -c "psql -U postgres -d postgres -c \"DROP DATABASE IF EXISTS desec;\""
  $COMPOSE exec -T dbapi sh -c "psql -U postgres -d postgres -c \"CREATE DATABASE desec OWNER desec;\""
  gunzip -c "$CACHE_FILE" | $COMPOSE exec -T dbapi sh -c "pg_restore -U desec -d desec --no-owner --no-acl --role=desec"
}

cleanup() {
  $COMPOSE ps || true
  $COMPOSE down || true
}

trap cleanup EXIT

if [[ "$BUILD" -eq 1 ]]; then
  $COMPOSE build "${BUILD_IMAGES_DB[@]}"
fi
$COMPOSE up -d dbapi
(
  set -a
  source "${ROOT_DIR}/.env"
  set +a
  export DJANGO_SETTINGS_MODULE=api.settings_quick_test
  export DESECSTACK_DJANGO_TEST=1
  cd "${ROOT_DIR}/api"
  if [[ -x "./venv/bin/python" ]]; then
    # Use project venv when present.
    source "./venv/bin/activate"
  else
    echo "Missing venv at ${ROOT_DIR}/api/venv. Create it with: cd api && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt" >&2
    exit 1
  fi
  # Avoid local psql dependency by checking readiness inside the DB container.
  wait_seconds=120
  start_ts=$(date +%s)
  while true; do
    if $COMPOSE exec -T dbapi pg_isready >/dev/null 2>&1; then
      break
    fi

    now_ts=$(date +%s)
    if (( now_ts - start_ts > wait_seconds )); then
      echo "Timed out waiting for Postgres to become ready."
      $COMPOSE ps
      $COMPOSE logs --tail 80 dbapi || true
      exit 1
    fi
    echo "Postgres is unavailable - sleeping"
    sleep 2
  done
  test_args=()
  if [[ "$PROD_DB" -eq 1 ]]; then
    download_prod_dbapi
    restore_dbapi_from_cache
    test_args+=(--keepdb)
  fi
  python3 manage.py test "${test_args[@]}"
)
