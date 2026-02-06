#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE="docker compose -f ${ROOT_DIR}/docker-compose.yml -f ${ROOT_DIR}/docker-compose.test-e2e2.yml"
LOG_DIR="${ROOT_DIR}/.cache/knot-eof-check"
RUNS=5
MARKER_PATTERN="KNOT_EOF_MARKER|E2E2_EOF_MARKER|E2E2_JSON_DECODE_MARKER"

rm -rf "${LOG_DIR}"
mkdir -p "${LOG_DIR}"

had_marker=0

for run in $(seq 1 "${RUNS}"); do
  log_file="${LOG_DIR}/run-${run}.log"
  echo "=== Knot EOF check run ${run}/${RUNS} ==="
  set +e
  {
    ${COMPOSE} down -v --remove-orphans
    ${COMPOSE} build api nslord_knot test-e2e2
    ${COMPOSE} run --rm -T test-e2e2 sh -c "./apiwait 300 && ./knotwait 300 && python3 -m pytest -vv --maxfail=10 --skip-performance-tests -k 'knot' ."
    ${COMPOSE} down -v --remove-orphans
  } 2>&1 | tee "${log_file}"
  run_status=${PIPESTATUS[0]}
  set -e

  if ! rg -n "test session starts" "${log_file}" >/dev/null; then
    echo "Run ${run} did not start pytest; marking as failed run."
    tail -n 50 "${log_file}" || true
    had_marker=1
  fi

  if rg -n "${MARKER_PATTERN}" "${log_file}" >/dev/null; then
    echo "Run ${run} found EOF/JSON markers."
    had_marker=1
  fi

  if [[ ${run_status} -ne 0 ]]; then
    echo "Run ${run} finished with non-zero status ${run_status} (ignored for EOF check)."
  fi
done

if [[ ${had_marker} -eq 0 ]]; then
  echo "EOF check result: no EOF/JSON markers in ${RUNS} runs. Consider EOF problem gone."
  exit 0
fi

echo "EOF check result: EOF/JSON markers found in ${RUNS} runs. EOF problem still present."
exit 1
