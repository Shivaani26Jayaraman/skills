---
name: agent-mission-control
category: AiAndMachineLearning
description: "Deploys, configures, and audits the Mission Control Log Pipeline, BigQuery Data Mart, and Looker Studio views for AI Agent Governance (tracking blocked PII leaks, prompt injections, and runtime errors)."
---

# Agent Mission Control Skill

## Instructions for AI Assistant

When the user requests to "deploy mission control", "setup governance pipeline", or "generate test logs":

1. **Environment Setup:** Ensure `PROJECT_ID` is set (default: `olympus-475310`).
2. **Execute Deployment:**
   - Step 1: Run `cloud/agent-mission-control/scripts/1_generate_test_logs.sh` to produce test security events.
   - Step 2: Run `cloud/agent-mission-control/scripts/2_deploy_sink_and_datamart.sh` to provision BigQuery and Log Sinks.
   - Step 3: Run `cloud/agent-mission-control/scripts/3_verify_pipeline.py` to audit BigQuery data streams.
3. **Output Dashboard Guide:** Share instructions from `cloud/agent-mission-control/references/looker_dashboard_setup.md`.
