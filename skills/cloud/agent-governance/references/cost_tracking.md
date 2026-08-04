# Cost Tracking & FinOps Standards

Keep your agent infrastructure cost-compliant by maintaining standardized tags across all cloud computing components, infrastructure-as-code definitions, and in-flight API requests.

## Labeling Schema

All projects and workloads associated with Agent deployments must maintain these metadata attributes:

| Label Key | Valid Values | Description |
|---|---|---|
| `agent-id` | `[a-z0-9_-]{3,63}` | The identifier of the deploying agent. |
| `business-unit` | `engineering`, `finance`, `pso` | The department paying for resources. |
| `environment` | `dev`, `staging`, `prod` | Deployment lifecycle tier. |

---

## Expanded Terraform Declarative Labeling (GitOps)

### 1. Vertex AI Reasoning Engine (Agent Engine)
```hcl
resource "google_vertex_ai_reasoning_engine" "agent_engine" {
  display_name = "customer-retention-agent"
  location     = "us-central1"

  # Enforce FinOps Metadata tag boundaries
  labels = {
    agent-id      = "customer-retention"
    business-unit = "pso"
    environment   = "prod"
  }
}
```

### 2. Google Kubernetes Engine (GKE Workload Pods)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-orchestrator
  labels:
    agent-id: "customer-retention"
    business-unit: "pso"
    environment: "prod"
spec:
  template:
    metadata:
      labels:
        agent-id: "customer-retention"
        business-unit: "pso"
        environment: "prod"
```

### 3. Pub/Sub Messaging Topics (Event-Driven Tools)
```hcl
resource "google_pubsub_topic" "agent_tool_trigger" {
  name = "agent-tool-invocations"

  labels = {
    agent-id      = "customer-retention"
    business-unit = "pso"
    environment   = "prod"
  }
}
```

---

## Advanced Application SDK & SQL Tracing

### 1. Database Query Comment Tagging (AlloyDB / Cloud Spanner)
Google Cloud Database **Query Insights** scans and aggregates comment blocks within incoming SQL packets. Format them as JSON comment headers to trace database cost drivers.

```python
import psycopg2

conn = psycopg2.connect("host=alloydb-instance-ip dbname=agent_db")
cursor = conn.cursor()

# Prepend tracing metadata JSON structure to the query
sql_query = """
/* {"agent-id": "customer-retention", "business-unit": "pso", "environment": "prod"} */
SELECT * FROM agent_memory_store WHERE session_id = %s;
"""

cursor.execute(sql_query, ("session-abc-123",))
```

### 2. Pub/Sub In-Flight Message Attribute Tagging
Tag dynamic payloads when publishing cross-agent communications.

```python
from google.cloud import pubsub_v1

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path("PROJECT_ID", "agent-tool-invocations")

data = b"Trigger tool execution details"
future = publisher.publish(
    topic_path, 
    data,
    # Inject FinOps tracing attributes
    agent_id="customer-retention",
    business_unit="pso",
    environment="prod"
)
```
