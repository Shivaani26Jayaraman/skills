# Cost Tracking & FinOps Standards

Keep your agent infrastructure cost-compliant by maintaining standardized tags across all cloud computing components.

## Labeling Schema

All projects and workloads associated with Agent deployments must maintain these metadata attributes:

| Label Key | Valid Values | Description |
|---|---|---|
| agent-id | ^[a-z0-9_-]{3,63}$ | The identifier of the deploying agent. |
| business-unit | engineering, finance, consulting | The department paying for resources. |
| environment | dev, staging, uat, prod | Deployment lifecycle tier. |

## Labelable Resource Types

finops_tagger.py only injects a labels block into resource types listed here — GCP resources not in this list either don't support labels or use a different mechanism (e.g. tags), and tagging them would produce invalid Terraform. Add a line to extend the list; do not remove the heading format.

- google_compute_instance
- google_compute_instance_template
- google_compute_region_instance_template
- google_compute_disk
- google_compute_region_disk
- google_compute_image
- google_compute_snapshot
- google_compute_address
- google_compute_global_address
- google_compute_forwarding_rule
- google_compute_global_forwarding_rule
- google_container_cluster
- google_container_node_pool
- google_sql_database_instance
- google_storage_bucket
- google_bigquery_dataset
- google_bigquery_table
- google_pubsub_topic
- google_pubsub_subscription
- google_cloudfunctions_function
- google_cloudfunctions2_function
- google_cloud_run_service
- google_cloud_run_v2_service
- google_cloud_run_v2_job
- google_dataflow_job
- google_dataproc_cluster
- google_composer_environment
- google_redis_instance
- google_filestore_instance
- google_spanner_instance
- google_artifact_registry_repository
- google_vertex_ai_endpoint
- google_notebooks_instance
- google_workflows_workflow
- google_secret_manager_secret

## BigQuery Cost Analysis Queries

Use these in your Google Cloud Billing export dataset. All examples look at the past 7 days.

### Top 5 most expensive agents

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

### Cost by business unit (chargeback)

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

### Cost by environment (dev/staging/uat/prod)

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

### Untagged spend (governance gap check)

```sql
SELECT
  service.description AS service,
  SUM(cost) AS untagged_cost,
  currency
FROM `[YOUR_BILLING_DATASET].gcp_billing_export_v1_[BILLING_ID]` b
WHERE usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND NOT EXISTS (
    SELECT 1 FROM UNNEST(labels) AS l WHERE l.key = 'agent-id'
  )
GROUP BY 1, currency
ORDER BY untagged_cost DESC;
```
