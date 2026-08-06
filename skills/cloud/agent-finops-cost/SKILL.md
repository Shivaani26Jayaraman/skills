---
name: agent-finops-cost
category: AiAndMachineLearning
description: "Deploys, configures, and templates the Agent Cost & FinOps Monitoring Pipeline, BigQuery Cost Views, and Google Cloud Monitoring Dashboard for tracking agent resource allocation, Gemini token usage, and overall spend."
---

# Agent Cost & FinOps Dashboard Skill

## Instructions for AI Assistant

When the user requests to "deploy cost dashboard", "setup finops pipeline", or "render agent monitoring dashboard":

1. **Environment Setup:** Ensure essential variables are obtained or prompted:
   - `PROJECT_ID` (default: `olympus-475310`)
   - `REASONING_ENGINE_ID` (The Vertex AI Reasoning Engine ID)
   - `MODEL_ID` (default: `gemini-3.5-flash`)
   - `DASHBOARD_DISPLAY_NAME` (e.g., `Agent Cost & FinOps Monitor`)
2. **Execute Deployment:**
   - **Method A (Terraform):**
     1. Copy files from `cloud/agent-finops-cost/terraform/` to the target directory.
     2. Run `terraform init` and `terraform apply` injecting the variables.
   - **Method B (Scripted CLI):**
     1. Run `python3 cloud/agent-finops-cost/scripts/render_dashboard.py` to compile the Jinja2 template with user variables.
     2. Create the BigQuery Datamart SQL Views using `bq query` and `cloud/agent-finops-cost/references/datamart_cost_views.sql`.
     3. Deploy the dashboard using `gcloud monitoring dashboards create --config-from-file=...`.
