# Cost Tracking & FinOps Standards

Keep your agent infrastructure cost-compliant by maintaining standardized tags across all cloud computing components.

## Labeling Schema

All projects and workloads associated with Agent deployments must maintain these metadata attributes:

### Mandatory Labels
| Label Key | Valid Values | Description |
|---|---|---|
| agent-id | ^[a-z0-9_-]{3,63}$ | The identifier of the deploying agent. |
| business-unit | engineering, finance, consulting | The department paying for resources. |
| environment | dev, staging, uat, prod | Deployment lifecycle tier. |

### Optional Labels
| Label Key | Valid Values | Description |
|---|---|---|
| cost-centre | ^cc-[a-z0-9_-]{3,10}$ | Billing code / cost center associated with the resources. |
| team | ^[a-z0-9_-]{2,63}$ | The specific team owning the agent resource. |

## Supported services for labels

finops_tagger.py only injects a labels block into resource types listed here — GCP resources not in this list either don't support labels or use a different mechanism (e.g. tags), and tagging them would produce invalid Terraform. Add a line to extend the list; do not remove the heading format.

- google_compute_instance
- google_container_cluster
- google_sql_database_instance
- google_storage_bucket
- google_bigquery_dataset
- google_pubsub_topic
- google_cloudfunctions_function
- google_cloudfunctions2_function
- google_cloud_run_service
- google_cloud_run_v2_service
- google_redis_instance
- google_spanner_instance
- google_artifact_registry_repository
- google_vertex_ai_endpoint
- google_notebooks_instance
- google_workflows_workflow
- google_secret_manager_secret

