#!/usr/bin/env bash
# Run the same checks as .github/workflows/ci.yml (backend + frontend).
# Usage (WSL): ./scripts/ci-local.sh
# Optional:   ./scripts/ci-local.sh --backend-only | --frontend-only
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

RUN_BACKEND=1
RUN_FRONTEND=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-only)
      RUN_FRONTEND=0
      shift
      ;;
    --frontend-only)
      RUN_BACKEND=0
      shift
      ;;
    -h | --help)
      echo "Usage: $0 [--backend-only | --frontend-only]"
      echo "Mirrors .github/workflows/ci.yml locally (conda python313 + frontend npm)."
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

log() {
  echo "[ci-local] $*"
}

activate_python313() {
  if [[ -n "${CONDA_DEFAULT_ENV:-}" ]] && [[ "${CONDA_DEFAULT_ENV}" == "python313" || "${CONDA_DEFAULT_ENV}" == "mindgraph" ]]; then
    return 0
  fi
  for conda_sh in \
    "${HOME}/miniconda3/etc/profile.d/conda.sh" \
    "${HOME}/anaconda3/etc/profile.d/conda.sh" \
    "/opt/conda/etc/profile.d/conda.sh"; do
    if [[ -f "${conda_sh}" ]]; then
      # shellcheck source=/dev/null
      source "${conda_sh}"
      for env_name in python313 mindgraph; do
        if conda activate "${env_name}" 2>/dev/null; then
          return 0
        fi
      done
    fi
  done
  echo "[ci-local] ERROR: conda env python313 or mindgraph not found. Activate manually and re-run." >&2
  exit 1
}

activate_frontend_node() {
  if [[ -f "${HOME}/.nvm/nvm.sh" ]]; then
    # shellcheck source=/dev/null
    source "${HOME}/.nvm/nvm.sh"
    (
      cd "${REPO_ROOT}/frontend"
      nvm use
    )
    return 0
  fi
  local nvmrc_version
  nvmrc_version="$(tr -d '[:space:]' < "${REPO_ROOT}/frontend/.nvmrc")"
  local node_bin="${HOME}/.nvm/versions/node/v${nvmrc_version}/bin"
  if [[ -x "${node_bin}/npm" ]]; then
    export PATH="${node_bin}:${PATH}"
    return 0
  fi
  if command -v npm >/dev/null 2>&1; then
    log "WARN: using npm on PATH (nvm not found); prefer Node from frontend/.nvmrc"
    return 0
  fi
  echo "[ci-local] ERROR: npm not found. Install Node $(cat "${REPO_ROOT}/frontend/.nvmrc") via nvm." >&2
  exit 1
}

warn_missing_libzbar() {
  if command -v dpkg-query >/dev/null 2>&1; then
    if ! dpkg-query -W -f='${Status}' libzbar0 2>/dev/null | grep -q "install ok installed"; then
      log "WARN: libzbar0 not installed (CI installs it). Run: sudo apt-get install -y libzbar0"
    fi
    return 0
  fi
  if ! ldconfig -p 2>/dev/null | grep -q libzbar; then
    log "WARN: libzbar may be missing (CI: sudo apt-get install -y libzbar0)"
  fi
}

run_backend() {
  log "=== backend (matches ci.yml backend job) ==="
  cd "${REPO_ROOT}"
  activate_python313
  warn_missing_libzbar

  log "Ruff (lint + format)"
  ruff check .
  ruff format --check .

  log "No inline lint suppressions"
  python scripts/lint/lint_no_inline_disables.py

  log "RLS session and dependency-order guards"
  python scripts/lint/lint_rls_session.py
  python scripts/lint/lint_rls_dep_order.py
  python scripts/lint/lint_admin_panel_access.py

  log "Redis async connection options guard"
  python scripts/lint/lint_redis_connection_options.py

  log "Pylint four-rule audit (AST baseline)"
  python scripts/lint/audit_pylint_four_rules.py --fail

  log "basedpyright (strict; see pyproject.toml)"
  python -m basedpyright .

  log "App import smoke"
  python -c "from main import app; assert app.title"

  log "Privacy policy (static HTML for Chrome Web Store crawlers)"
  PYTHONPATH=. python scripts/render_privacy_policy_html.py
  PYTHONPATH=. python scripts/check_privacy_policy_crawlable.py

  log "Pylint (full Python tree; minimal policy disables)"
  python -m pylint services routers agents clients config utils scripts tests loadtests tasks alembic/env.py \
    --fail-under=10.0

  log "Pytest (focused + collab)"
  pytest -q \
    tests/test_redis_connection_options.py \
    tests/test_collab_ws_json_limits.py \
    tests/test_workshop_update_flush_gate.py \
    tests/test_workshop_ws_integration.py \
    tests/test_online_collab_phase8.py \
    tests/test_workshop_collab_backend.py \
    tests/test_collab_palette_sync.py \
    tests/test_workshop_editor_redis_merge.py \
    tests/test_ws_fanout.py \
    tests/test_collab_synthetic_probe.py \
    tests/test_workshop_join_resume_tokens.py \
    tests/test_organization_mindmate_avatar.py \
    tests/test_org_subscription.py \
    tests/test_school_tier.py \
    tests/test_dify_user_key.py \
    tests/test_mindbot_bind_messages.py \
    tests/test_dingtalk_bind_imports.py \
    tests/test_mindbot_pair_code_handler.py \
    tests/test_bind_code_parse.py \
    tests/test_generate_dingtalk_identity.py \
    tests/test_library_save_user_notices.py \
    tests/test_generation_skip_registry.py \
    tests/test_mindbot_library_save_reply.py \
    tests/test_assistant_markdown.py \
    tests/test_mindbot_dingtalk_diagram_display.py \
    tests/test_user_daily_token_quota.py \
    tests/test_llm_daily_token_cap.py \
    tests/test_get_client_ip.py \
    tests/test_gewe_webhook_auth.py \
    tests/test_refresh_token_reuse.py \
    tests/test_security_production_hardening.py \
    tests/test_csrf_protection.py \
    tests/test_privacy_policy_static.py \
    tests/test_privacy_policy_http.py \
    tests/test_workshop_chat_file_service.py \
    tests/test_dingtalk_bind_service.py \
    tests/test_showcase_helpers.py \
    tests/test_showcase_create_response.py \
    tests/test_showcase_storage_cos.py \
    tests/test_showcase_e2e_smoke.py \
    tests/test_diagram_folders_api.py
}

run_frontend() {
  log "=== frontend (matches ci.yml frontend job) ==="
  activate_frontend_node
  cd "${REPO_ROOT}/frontend"

  log "npm ci"
  npm ci

  log "VueUse PURE annotations (Rolldown build hygiene)"
  npm run check:vueuse-pure

  log "DEP0205 regression (Node module hooks)"
  npm run check:dep0205

  log "CLI script smoke (native Node type stripping)"
  npm run check:scripts

  log "npm audit (high severity)"
  npm audit --audit-level=high

  log "Vitest (workshop reconnect + diagram meta)"
  npx vitest run tests/useWorkshopReconnect.spec.ts tests/mindmateDiagramMeta.spec.ts
}

run_chrome_extension() {
  log "=== chrome-extension (vitest unit tests) ==="
  activate_frontend_node
  cd "${REPO_ROOT}/chrome-extension"

  log "npm ci"
  npm ci

  log "Vitest (doc-extract + mindmate)"
  npm test
}

if [[ "${RUN_BACKEND}" -eq 1 ]]; then
  run_backend
fi

if [[ "${RUN_FRONTEND}" -eq 1 ]]; then
  run_frontend
  run_chrome_extension
fi

log "OK — local CI passed (same steps as .github/workflows/ci.yml)"
