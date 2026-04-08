#!/usr/bin/env bash
# check-workflows.sh - 全ワークフローの直近実行ステータスを確認する
#
# Usage:
#   ./check-workflows.sh [API_BASE_URL] [API_KEY]
#

set -euo pipefail

API_BASE="${1:-http://localhost:8001}"
API_KEY="${2:-}"

if [[ -z "$API_KEY" ]]; then
  echo "Error: API_KEY is required."
  echo "Usage: $0 [API_BASE_URL] [API_KEY]"
  echo "  or:  export PIPELINES_API_KEY=xxx && $0 [API_BASE_URL]"
  exit 1
fi

# 確認対象のワークフロー一覧
WORKFLOWS=(
  "spotify_ingest_workflow"
  "github_ingest_workflow"
  "google_activity_ingest_workflow"
  "local_mirror_sync_workflow"
  "browser_history_compact_workflow"
  "browser_history_compact_maintenance_workflow"
)

API_OPTS=(-s -H "X-API-Key: ${API_KEY}")

echo "============================================"
echo " Pipeline Workflows Status Check"
echo " API: ${API_BASE}"
echo "============================================"
echo ""

FAIL_COUNT=0
TOTAL_COUNT=0

for wf in "${WORKFLOWS[@]}"; do
  TOTAL_COUNT=$((TOTAL_COUNT + 1))

  # 直近の run を1件取得
  response=$(curl "${API_OPTS[@]}" "${API_BASE}/v1/workflows/${wf}/runs")
  latest=$(echo "$response" | python3 -c "
import sys, json
runs = json.load(sys.stdin)
if not runs:
    print('NO_RUNS')
    sys.exit(0)
r = runs[0]
print(f\"{r['status']}|{r.get('trigger_type','?')}|{r.get('started_at','N/A')}|{r.get('finished_at','N/A')}|{r.get('last_error_message','')}\")
" 2>/dev/null)

  if [[ "$latest" == "NO_RUNS" ]]; then
    echo "[$wf]"
    echo "  Status:  NO_RUNS (never executed)"
    echo ""
    continue
  fi

  IFS='|' read -r status trigger started finished error_msg <<< "$latest"

  # ステータスに応じてアイコン設定
  case "$status" in
    succeeded) icon="✅" ;;
    running)   icon="🔄" ;;
    failed)    icon="❌"; FAIL_COUNT=$((FAIL_COUNT + 1)) ;;
    queued)    icon="⏳" ;;
    canceled)  icon="⛔" ;;
    *)         icon="❓"; FAIL_COUNT=$((FAIL_COUNT + 1)) ;;
  esac

  echo "${icon} [${wf}]"
  echo "  Status:    ${status}"
  echo "  Trigger:   ${trigger}"
  echo "  Started:   ${started}"
  echo "  Finished:  ${finished}"
  if [[ -n "$error_msg" && "$error_msg" != "None" ]]; then
    echo "  Error:     ${error_msg}"
  fi
  echo ""
done

echo "============================================"
echo " Result: ${TOTAL_COUNT} workflows checked"
if [[ $FAIL_COUNT -gt 0 ]]; then
  echo " ⚠️  ${FAIL_COUNT} workflow(s) have issues"
  exit 1
else
  echo " ✅ All workflows OK"
  exit 0
fi
