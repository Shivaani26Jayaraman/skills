# Agent Cost & FinOps Dashboard Skill

Deploys, configures, and templates the **Agent Cost & FinOps Monitoring Pipeline**, **BigQuery Cost Views**, and **Google Cloud Monitoring Dashboard** for tracking agent resource allocation, Gemini token usage, and overall spend.

---

## Directory Structure

```
cloud/agent-finops-cost/
├── SKILL.md                 # AI Agent Instructions
├── README.md                # Project documentation (this file)
├── references/
│   ├── dashboard.json.j2    # Jinja2 parameterized Monitoring Dashboard JSON
│   └── datamart_cost_views.sql # SQL views definition for BigQuery Datamart
└── scripts/
    ├── render_dashboard.py  # Compiles Jinja2 template into static JSON
    └── discover_and_label_fleet.py # Discovers and labels Reasoning Engines in us-central1 & global
```

---

## Step-by-Step Execution Guide

### Step 1: Discover & Label Your Agent Fleet
Run the script to list your Reasoning Engines in `us-central1` and `global`, and automatically apply `agent-id`, `business-unit`, and `environment` labels:
```bash
python3 cloud/agent-finops-cost/scripts/discover_and_label_fleet.py
```

### Step 2: Deploy BigQuery Cost Views
Run the SQL script to create the views joining your Agent Registry, GCP Billing Export, and token usage logs:
```bash
bq query --use_legacy_sql=false --project_id=olympus-475310 < cloud/agent-finops-cost/references/datamart_cost_views.sql
```

### Step 3: Render and Deploy the Cloud Monitoring Dashboard
Compile the JSON dashboard using your variables and apply it:
```bash
# Render template
python3 cloud/agent-finops-cost/scripts/render_dashboard.py \
  --project-id="olympus-475310" \
  --reasoning-engine-id="your-engine-id" \
  --model-id="gemini-3.5-flash" \
  --dashboard-display-name="Agent Cost & FinOps Monitor"

# Deploy to Cloud Monitoring
gcloud monitoring dashboards create --config-from-file=cloud/agent-finops-cost/rendered_dashboard.json
```
