#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-olympus-475310}"

echo "📡 Emitting simulated security logs for project: $PROJECT_ID..."

gcloud logging write agent-security-log \
    '{"agent_id": "support-bot", "action_taken": "BLOCK", "reason": "PII_LEAK_PREVENTED", "business_unit": "pso", "environment": "staging"}' \
    --severity=ERROR --payload-type=json --project="$PROJECT_ID"

gcloud logging write agent-security-log \
    '{"agent_id": "finance-agent", "action_taken": "BLOCK", "reason": "PROMPT_INJECTION_DETECTED", "business_unit": "finance", "environment": "prod"}' \
    --severity=ERROR --payload-type=json --project="$PROJECT_ID"

echo "✅ Test logs written to Cloud Logging!"
