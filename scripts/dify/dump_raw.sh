#!/usr/bin/env bash
# Dify raw PostgreSQL dump for MindGraph MindMate export.
# Bash only — no Python on the Dify host.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCK_FD=
STAGING_DIR=
LOCK_FILE=""
DUMP_MODE="execute"
CONTINUE_ON_TABLE_FAIL=0

DUMP_TABLES=(
  dify_setups tenants apps api_tokens workflows end_users conversations messages
  message_files message_feedbacks upload_files message_chains message_agent_thoughts
  dataset_retriever_resources workflow_runs workflow_conversation_variables workflow_app_logs
)
CORE_TABLES=(messages conversations end_users apps api_tokens)

log() {
  echo "$(date -u '+%Y-%m-%d %H:%M:%S') [INFO] $*" >&2
}

log_err() {
  echo "$(date -u '+%Y-%m-%d %H:%M:%S') [ERROR] $*" >&2
}

cleanup_on_exit() {
  local code=$?
  if [[ -n "${LOCK_FD:-}" ]] && [[ -n "${LOCK_FILE:-}" ]]; then
    flock -u "$LOCK_FD" 2>/dev/null || true
    exec {LOCK_FD}>&- 2>/dev/null || true
  fi
  if [[ $code -ne 0 ]] && [[ -n "${STAGING_DIR:-}" ]] && [[ -d "${STAGING_DIR:-}" ]]; then
    log_err "Interrupted or failed — staging kept at ${STAGING_DIR}"
  fi
}
trap cleanup_on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

resolve_compose_dir() {
  local tried=()
  local candidate=""
  if [[ -n "${DIFY_COMPOSE_DIR:-}" ]]; then
    tried+=("$DIFY_COMPOSE_DIR")
    if [[ -f "${DIFY_COMPOSE_DIR}/docker-compose.yaml" ]]; then
      echo "$DIFY_COMPOSE_DIR"
      return 0
    fi
  fi
  for candidate in \
    "${SCRIPT_DIR}/docker" \
    "/root/dify/docker" \
    "$(pwd)/docker" \
    "$(pwd)"; do
    tried+=("$candidate")
    if [[ -f "${candidate}/docker-compose.yaml" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  log_err "Compose directory not found. Tried:"
  printf '  - %s\n' "${tried[@]}" >&2
  log_err "Expected /root/dify/docker with docker-compose.yaml"
  exit 2
}

load_env_files() {
  local compose_dir="$1"
  set -a
  if [[ -d "${compose_dir}/envs" ]]; then
    local env_file=""
    shopt -s nullglob
    for env_file in "${compose_dir}"/envs/*.env; do
      # shellcheck disable=SC1090
      source "$env_file"
    done
    shopt -u nullglob
  fi
  if [[ -f "${compose_dir}/.env" ]]; then
    # shellcheck disable=SC1091
    source "${compose_dir}/.env"
  elif [[ -f "${compose_dir}/middleware.env" ]]; then
    # shellcheck disable=SC1091
    source "${compose_dir}/middleware.env"
  else
    log_err "No .env found under ${compose_dir}"
    exit 2
  fi
  if [[ -z "${DB_USERNAME:-}" ]] && [[ -n "${POSTGRES_USER:-}" ]]; then
    DB_USERNAME="$POSTGRES_USER"
  fi
  if [[ -z "${DB_PASSWORD:-}" ]] && [[ -n "${POSTGRES_PASSWORD:-}" ]]; then
    DB_PASSWORD="$POSTGRES_PASSWORD"
  fi
  if [[ -z "${DB_DATABASE:-}" ]] && [[ -n "${POSTGRES_DB:-}" ]]; then
    DB_DATABASE="$POSTGRES_DB"
  fi
  set +a
  if [[ -z "${DB_USERNAME:-}" ]] || [[ -z "${DB_DATABASE:-}" ]]; then
    log_err "DB_USERNAME / DB_DATABASE not set after sourcing env"
    exit 2
  fi
  if [[ "${DB_TYPE:-postgresql}" == "mysql" ]]; then
    log_err "MySQL not supported for raw dump (MindGraph expects PostgreSQL schema)"
    exit 2
  fi
}

resolve_dump_root() {
  if [[ -n "${DIFY_DUMP_ROOT:-}" ]]; then
    echo "$DIFY_DUMP_ROOT"
    return 0
  fi
  if [[ -w /root ]] || [[ "$(id -u)" -eq 0 ]]; then
    echo "/root/dify-dump"
    return 0
  fi
  echo "${SCRIPT_DIR}/../dify-dump"
}

resolve_server_label() {
  if [[ -n "${DIFY_SERVER_LABEL:-}" ]]; then
    case "$DIFY_SERVER_LABEL" in
      dify|neodify) echo "$DIFY_SERVER_LABEL"; return 0 ;;
      *) log_err "DIFY_SERVER_LABEL must be dify or neodify"; exit 2 ;;
    esac
  fi
  if [[ ! -t 0 ]]; then
    log_err "Non-interactive run requires DIFY_SERVER_LABEL=dify or DIFY_SERVER_LABEL=neodify"
    exit 2
  fi
  echo "" >&2
  echo "Which Dify server is this dump from?" >&2
  echo "" >&2
  echo "  [1] dify     — original / legacy Dify (MindGraph Server 1)" >&2
  echo "  [2] neodify  — new NeoDify server (MindGraph Server 2)" >&2
  echo "" >&2
  local choice=""
  read -r -p "Choose [1/2]: " choice
  case "$choice" in
    1|dify) echo "dify" ;;
    2|neodify) echo "neodify" ;;
    *) log_err "Invalid server choice"; exit 2 ;;
  esac
}

mindgraph_slot_for_label() {
  case "$1" in
    dify) echo 1 ;;
    neodify) echo 2 ;;
    *) echo 0 ;;
  esac
}

utc_timestamp() {
  date -u '+%Y-%m-%d_%H%M%SZ'
}

docker_compose_cmd() {
  local compose_dir="$1"
  shift
  docker compose -f "${compose_dir}/docker-compose.yaml" --project-directory "$compose_dir" "$@"
}

acquire_lock() {
  local dump_root="$1"
  mkdir -p "$dump_root"
  LOCK_FILE="${dump_root}/.dump.lock"
  exec {LOCK_FD}>"$LOCK_FILE"
  if ! flock -n "$LOCK_FD"; then
    log_err "Another dump is running (lock: ${LOCK_FILE})"
    exit 8
  fi
}

prompt_menu() {
  local compose_dir="$1"
  local dump_root="$2"
  local server_label="$3"
  local ts="$4"
  local db_name="$5"
  if [[ ! -t 0 ]]; then
    DUMP_MODE="execute"
    return 0
  fi
  local staging="${dump_root}/${server_label}/staging/${ts}"
  local archive="${dump_root}/${server_label}/archives/dify-dump_${server_label}_${ts}.zip"
  echo "══════════════════════════════════════════════════" >&2
  echo " Dify raw dump" >&2
  echo " Compose:   ${compose_dir}" >&2
  echo " Dump root: ${dump_root}" >&2
  echo " Server:    ${server_label} (MindGraph Server $(mindgraph_slot_for_label "$server_label"))" >&2
  echo " Staging:   ${staging}/" >&2
  echo " Archive:   ${archive}" >&2
  echo " DB:        ${db_name} @ service db" >&2
  echo " Tables:    ${#DUMP_TABLES[@]}" >&2
  echo "══════════════════════════════════════════════════" >&2
  echo "" >&2
  echo "  [1] Dry run   — verify paths, Docker, DB; list tables; no files written" >&2
  echo "  [2] Execute   — full dump → zip → remove staging" >&2
  echo "  [3] Cancel" >&2
  echo "" >&2
  local choice=""
  read -r -p "Choose [1/2/3] (default 1): " choice
  choice="${choice:-1}"
  case "$choice" in
    1) DUMP_MODE="dry_run" ;;
    2) DUMP_MODE="execute" ;;
    3) DUMP_MODE="cancel" ;;
    *) log_err "Invalid menu choice"; exit 2 ;;
  esac
}

preflight_checks() {
  local compose_dir="$1"
  local dump_root="$2"
  if ! docker info >/dev/null 2>&1; then
    log_err "Docker daemon unreachable (run as root or add user to docker group)"
    exit 3
  fi
  local db_cid=""
  db_cid="$(docker_compose_cmd "$compose_dir" ps -q db 2>/dev/null || true)"
  if [[ -z "$db_cid" ]]; then
    log_err "DB container not running. Try: docker compose up -d db"
    docker_compose_cmd "$compose_dir" ps >&2 || true
    exit 4
  fi
  if [[ "$DUMP_MODE" == "execute" ]]; then
    df -h "$dump_root" >&2 || true
  fi
  local table=""
  for table in "${CORE_TABLES[@]}"; do
    local reg=""
    reg="$(docker_compose_cmd "$compose_dir" exec -T db psql -U "$DB_USERNAME" -d "$DB_DATABASE" -tAc \
      "SELECT to_regclass('public.${table}') IS NOT NULL;" 2>/dev/null || echo "f")"
    reg="$(echo "$reg" | tr -d '[:space:]')"
    if [[ "$reg" != "t" ]]; then
      log_err "Required table missing: ${table} (Dify schema drift?)"
      exit 5
    fi
  done
  log "Preflight OK — DB container ${db_cid:0:12}"
}

dump_table() {
  local compose_dir="$1"
  local table="$2"
  local out_file="$3"
  local sql="COPY (SELECT * FROM ${table}) TO STDOUT WITH (FORMAT csv, HEADER true)"
  docker_compose_cmd "$compose_dir" exec -T db \
    env PGPASSWORD="${DB_PASSWORD:-}" \
    psql -U "$DB_USERNAME" -d "$DB_DATABASE" -v ON_ERROR_STOP=1 -c "$sql" > "$out_file"
}

table_row_count() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    echo 0
    return 0
  fi
  local lines
  lines="$(wc -l < "$file" | tr -d ' ')"
  if [[ "$lines" -le 0 ]]; then
    echo 0
  else
    echo $((lines - 1))
  fi
}

write_manifest() {
  local path="$1"
  local status="$2"
  local server_label="$3"
  local started_at="$4"
  local finished_at="$5"
  local duration="$6"
  local staging="$7"
  local archive_path="${8:-}"
  local archive_bytes="${9:-0}"
  local archive_sha="${10:-}"
  local tables_json="$11"
  local errors_json="${12:-[]}"
  local slot
  slot="$(mindgraph_slot_for_label "$server_label")"
  cat > "$path" <<EOF
{
  "status": "${status}",
  "started_at": "${started_at}",
  "finished_at": "${finished_at}",
  "duration_seconds": ${duration},
  "server_label": "${server_label}",
  "mindgraph_server_slot": ${slot},
  "staging_dir": "${staging}",
  "archive_path": "${archive_path}",
  "archive_bytes": ${archive_bytes},
  "archive_sha256": "${archive_sha}",
  "dump_tables": $(printf '%s\n' "${DUMP_TABLES[@]}" | jq -R . | jq -s . 2>/dev/null || printf '%s' '[]'),
  "tables": ${tables_json},
  "errors": ${errors_json},
  "schema_ref": "langgenius/dify api/models/model.py + workflow.py"
}
EOF
}

run_dump() {
  local compose_dir="$1"
  local dump_root="$2"
  local server_label="$3"
  local ts="$4"
  local started_at
  started_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  local start_epoch
  start_epoch="$(date -u +%s)"

  STAGING_DIR="${dump_root}/${server_label}/staging/${ts}"
  local archives_dir="${dump_root}/${server_label}/archives"
  mkdir -p "$STAGING_DIR" "$archives_dir"

  local log_file="${STAGING_DIR}/dump.log"
  exec > >(tee -a "$log_file") 2>&1

  declare -A TABLE_STATUS=()
  declare -A TABLE_ROWS=()
  declare -A TABLE_BYTES=()
  local errors=()
  local idx=0
  local total="${#DUMP_TABLES[@]}"
  local table=""

  for table in "${DUMP_TABLES[@]}"; do
    idx=$((idx + 1))
    local out="${STAGING_DIR}/${table}.csv"
    log "[${idx}/${total}] Dumping ${table}…"
    if dump_table "$compose_dir" "$table" "$out"; then
      TABLE_STATUS["$table"]="done"
      TABLE_ROWS["$table"]="$(table_row_count "$out")"
      TABLE_BYTES["$table"]="$(stat -c%s "$out" 2>/dev/null || echo 0)"
      log "[${idx}/${total}] ${table} — ${TABLE_ROWS[$table]} rows, ${TABLE_BYTES[$table]} bytes"
    else
      rm -f "$out"
      TABLE_STATUS["$table"]="failed"
      errors+=("$table")
      log_err "Table ${table} failed"
      if [[ "$CONTINUE_ON_TABLE_FAIL" -eq 1 ]]; then
        continue
      fi
      if [[ -t 0 ]]; then
        local ans=""
        read -r -p "Table ${table} failed. Continue with remaining tables? [y/N] " ans
        if [[ "$ans" =~ ^[Yy]$ ]]; then
          CONTINUE_ON_TABLE_FAIL=1
          continue
        fi
      fi
      exit 6
    fi
  done

  local core_ok=1
  for table in "${CORE_TABLES[@]}"; do
    if [[ "${TABLE_STATUS[$table]:-}" != "done" ]]; then
      core_ok=0
      break
    fi
  done

  local status="complete"
  if [[ ${#errors[@]} -gt 0 ]]; then
    if [[ "$core_ok" -eq 1 ]]; then
      status="partial"
    else
      status="failed"
      log_err "Core tables missing — no archive produced"
      exit 6
    fi
  fi

  local finished_at duration tables_json
  finished_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  duration=$(( $(date -u +%s) - start_epoch ))

  tables_json="{"
  local first=1
  for table in "${DUMP_TABLES[@]}"; do
    [[ "$first" -eq 1 ]] || tables_json+=","
    first=0
    tables_json+="\"${table}\":{\"status\":\"${TABLE_STATUS[$table]:-skipped}\",\"rows\":${TABLE_ROWS[$table]:-0},\"bytes\":${TABLE_BYTES[$table]:-0}}"
  done
  tables_json+="}"

  local errors_json="[]"
  if [[ ${#errors[@]} -gt 0 ]]; then
    errors_json="$(printf '%s\n' "${errors[@]}" | jq -R . | jq -s .)"
  fi

  local archive_name="dify-dump_${server_label}_${ts}.zip"
  local archive_path="${archives_dir}/${archive_name}"
  write_manifest "${STAGING_DIR}/manifest.json" "$status" "$server_label" \
    "$started_at" "$finished_at" "$duration" "$STAGING_DIR" "" 0 "" \
    "$tables_json" "$errors_json"

  if [[ "$status" == "failed" ]]; then
    exit 6
  fi

  log "Creating archive ${archive_path}…"
  (cd "${dump_root}/${server_label}/staging" && zip -r -9 "$archive_path" "${ts}/")
  local archive_bytes archive_sha
  archive_bytes="$(stat -c%s "$archive_path")"
  archive_sha="$(sha256sum "$archive_path" | awk '{print $1}')"

  write_manifest "${STAGING_DIR}/manifest.json" "$status" "$server_label" \
    "$started_at" "$finished_at" "$duration" "$STAGING_DIR" "$archive_path" \
    "$archive_bytes" "$archive_sha" "$tables_json" "$errors_json"

  cp "${STAGING_DIR}/manifest.json" "${archive_path%.zip}.manifest.json"

  rm -rf "$STAGING_DIR"
  STAGING_DIR=""

  echo "══════════════════════════════════════════════════" >&2
  echo " Dify raw dump — ${status^^}" >&2
  echo " Archive:   ${archive_path}" >&2
  echo " Size:      ${archive_bytes} bytes  |  Duration: ${duration}s" >&2
  echo " Upload:    scp ${archive_path} user@host:…/MindGraph/data/dify-dumps/incoming/" >&2
  echo " Import:    bash scripts/dify/import_dump_zip.sh" >&2
  echo "══════════════════════════════════════════════════" >&2

  if [[ "$status" == "complete" ]]; then
    exit 0
  fi
  exit 1
}

main() {
  local compose_dir dump_root server_label ts
  compose_dir="$(resolve_compose_dir)"
  log "Resolved compose_dir=${compose_dir}"
  load_env_files "$compose_dir"
  dump_root="$(resolve_dump_root)"
  server_label="$(resolve_server_label)"
  ts="$(utc_timestamp)"
  log "Resolved dump_root=${dump_root} server_label=${server_label}"

  prompt_menu "$compose_dir" "$dump_root" "$server_label" "$ts" "$DB_DATABASE"
  if [[ "$DUMP_MODE" == "cancel" ]]; then
    exit 0
  fi

  preflight_checks "$compose_dir" "$dump_root"

  if [[ "$DUMP_MODE" == "dry_run" ]]; then
    log "Dry run complete — no files written"
    local idx=0
    for _ in "${DUMP_TABLES[@]}"; do
      idx=$((idx + 1))
      log "  [${idx}/${#DUMP_TABLES[@]}] would dump ${_}"
    done
    exit 0
  fi

  acquire_lock "$dump_root"
  run_dump "$compose_dir" "$dump_root" "$server_label" "$ts"
}

main "$@"
