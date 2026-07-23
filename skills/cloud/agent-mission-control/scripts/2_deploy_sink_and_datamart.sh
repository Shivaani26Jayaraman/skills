#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-olympus-475310}"
LOCATION_ID="${LOCATION_ID:-US}"

echo "🛠️ Deploying Mission Control Log Sink & BigQuery Data Mart for $PROJECT_ID..."

# Create BigQuery Dataset
bq mk --location="$LOCATION_ID" \
    --project_id="$PROJECT_ID" agent_governance_datamart 2>/dev/null || echo "Dataset already exists."

# Create Log Sink
gcloud logging sinks create agent-security-sink \
    bigquery.googleapis.com/projects/$PROJECT_ID/datasets/agent_governance_datamart \
    --log-filter='severity>=ERROR OR jsonPayload.action_taken="BLOCK"' \
    --project="$PROJECT_ID" 2>/dev/null || echo "Log Sink already exists."

# Grant IAM Permissions
SINK_WRITER=$(gcloud logging sinks describe agent-security-sink --project=$PROJECT_ID --format="value(writerIdentity)")
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="$SINK_WRITER" \
    --role="roles/bigquery.dataEditor" >/dev/null

echo "⏳ Waiting 20 seconds for logs to stream into BigQuery..."
sleep 20

# Create BigQuery View
bq query --use_legacy_sql=false --project_id=$PROJECT_ID < cloud/agent-mission-control/references/datamart_views.sql

echo "✅ BigQuery Data Mart deployment complete!"
