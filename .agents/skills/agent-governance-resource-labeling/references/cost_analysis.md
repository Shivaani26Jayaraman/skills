# FinOps Cost Analysis & Billing Queries

This reference guide explains how compliance labels are used to track cloud spend and how to configure queries in application code.

---

## Why We Add Compliance Labels
Standardizing metadata tags on all cloud resources ensures organizational cost visibility and financial governance:
*   **Infrastructure Spend**: Terraform resource labels (e.g. `google_compute_instance`, `google_storage_bucket`) map computing and storage costs directly to specific projects and environments.
*   **Transactional Actions**: BigQuery client query configuration labels (e.g. `QueryJobConfig(labels=...)` in Python client calls) map database scan execution costs directly to the responsible business unit and agent.

---

## How Cost Tracking Works
When tagged infrastructure runs or labeled queries execute, GCP records the associated labels alongside billing metrics in the Google Cloud Billing Export. 
You can run BigQuery analysis queries on your Billing Export dataset to analyze spend, calculate chargebacks, or find cost anomalies.

### Example Cost Analysis Queries (BigQuery)
Below are SQL examples (for query exports of the past 7 days) to track costs using the compliance labels:

#### 1. Top 5 Most Expensive Agents
```sql
SELECT
  labels.value AS agent_id,
  SUM(cost) AS total_cost,
  currency
FROM `[YOUR_BILLING_DATASET].gcp_billing_export_v1_[BILLING_ID]`
CROSS JOIN UNNEST(labels) AS labels
WHERE labels.key = 'agent-id'
  AND usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY 1, currency
ORDER BY total_cost DESC
LIMIT 5;
```

#### 2. Cost by Business Unit (Chargeback Allocation)
```sql
SELECT
  labels.value AS business_unit,
  SUM(cost) AS total_cost,
  currency
FROM `[YOUR_BILLING_DATASET].gcp_billing_export_v1_[BILLING_ID]`
CROSS JOIN UNNEST(labels) AS labels
WHERE labels.key = 'business-unit'
  AND usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY 1, currency
ORDER BY total_cost DESC;
```

#### 3. Spend by Environment (dev/staging/uat/prod)
```sql
SELECT
  labels.value AS environment,
  SUM(cost) AS total_cost,
  currency
FROM `[YOUR_BILLING_DATASET].gcp_billing_export_v1_[BILLING_ID]`
CROSS JOIN UNNEST(labels) AS labels
WHERE labels.key = 'environment'
  AND usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY 1, currency
ORDER BY total_cost DESC;
```

---

## BigQuery Query Labeling (Python)

Queries executed from application source code (such as Python) must configure standard labeling metadata on execution jobs. This is achieved by creating a `job_config.json` configuration file in the same directory as the Python code, loading it, and passing the labels to a `google.cloud.bigquery.QueryJobConfig`.

### Reusable Config (job_config.json)
Place a JSON configuration file containing standard compliance labels in the same directory as your Python files:
```json
{
  "labels": {
    "agent-id": "support-bot",
    "business-unit": "finance",
    "environment": "dev",
    "cost-centre": "cc-1234",
    "team": "ace"
  }
}
```

### Python Implementation Example
Load the `job_config.json` file dynamically (using directory-relative paths) and configure the `QueryJobConfig`:
```python
import os
import json
from google.cloud import bigquery

client = bigquery.Client()

# Load compliance labels from job_config.json in the same directory
config_path = os.path.join(os.path.dirname(__file__), "job_config.json")
with open(config_path, "r") as f:
    config_data = json.load(f)

job_config = bigquery.QueryJobConfig(labels=config_data.get("labels", {}))

# Run query with configured labels
query_job = client.query("SELECT 1", job_config=job_config)
```
