---
name: agent-governance
description: Enforce Cloud FinOps cost-tracking compliance by auto-tagging GCP Terraform resources and BigQuery Python queries with standard metadata.
---

# Agent Governance: FinOps Cost-Tracking & Compliance

This skill helps maintain organizational cost compliance for all agent infrastructure resources by enforcing standard metadata tags across GCP Terraform resource definitions and BigQuery Python client queries.

## Key Features

1. **Auto-Tagging (Terraform)**: Scan and update GCP resource blocks in `.tf` files with cost-tracking labels.
2. **Auto-Tagging (Python)**: Scan Python source files (`.py`) for BigQuery client `.query()` calls and refactor them to use a `QueryJobConfig` containing the compliant labels.
3. **Governance Check**: Validate existing or proposed labels against the defined schema in [cost_tracking.md](file:///Users/shivaanij/skills/.agents/skills/agent-governance-resource-labeling/references/cost_tracking.md) (refer to [cost_analysis.md](file:///Users/shivaanij/skills/.agents/skills/agent-governance-resource-labeling/references/cost_analysis.md) for billing analysis queries and Python implementation guidelines).
4. **Smart Labeling & Refactoring**: Leverage Vertex AI Gemini to analyze HCL blocks and Python scripts to suggest and inject contextual labels.
5. **Validation Modes**: Supports Interactive, Dry-Run, and Strict validation compliance checks.

---

## 📋 Labeling Standards

The labeling standards are loaded dynamically from [cost_tracking.md](file:///Users/shivaanij/skills/.agents/skills/agent-governance-resource-labeling/references/cost_tracking.md). The metadata tags are:

### Mandatory Labels
| Label Key | Valid Values | Description |
| :--- | :--- | :--- |
| **`agent-id`** | `[a-z0-9_-]{3,63}` | Unique identifier of the deploying agent. |
| **`business-unit`** | `engineering`, `finance`, `consulting` | The department paying for resources. |
| **`environment`** | `dev`, `staging`, `uat`, `prod` | Deployment lifecycle tier. |

### Optional Labels
| Label Key | Valid Values | Description |
| :--- | :--- | :--- |
| **`cost-centre`** | `cc-[a-z0-9_-]{3,10}` | Billing code / cost center associated with the resources (user-defined or suggested by Gemini). |
| **`team`** | `[a-z0-9_-]{2,63}` | The specific team owning the agent resource (user-defined or suggested by Gemini). |

### Supported Services for Labels
Only GCP resource types supporting a `labels` block are tagged (e.g., `google_compute_instance`, `google_storage_bucket`). The list of supported services is defined in [cost_tracking.md](file:///Users/shivaanij/skills/.agents/skills/agent-governance-resource-labeling/references/cost_tracking.md#L15).

---

## 🚀 Running the Tagger Script

Execute the compliance tagger using `scripts/finops_tagger.py`.

### 1. Interactive Tagging (Recommended)
Prompts for each required label with defaults, allowing you to reject, override, or ask Gemini for suggestions.
```bash
python3 scripts/finops_tagger.py -i /path/to/terraform/dir
```

### 2. Quiet / Static Tagging (CI/CD)
Tags files automatically using static values provided via arguments (useful for CI scripts).
```bash
python3 scripts/finops_tagger.py \
  --agent-id "customer-support-bot" \
  --business-unit "engineering" \
  --environment "staging" \
  /path/to/terraform/dir
```

### 3. Dry-Run (Preview Changes)
Displays a unified diff of proposed HCL updates without writing to disk.
```bash
python3 scripts/finops_tagger.py --dry-run /path/to/terraform/dir
```

### 4. Strict Enforcement
Errors out and halts (exit status 1) if existing resources fail standard choice checks or regex validation.
```bash
python3 scripts/finops_tagger.py --strict /path/to/terraform/dir
```

### 5. Force Re-Tagging
Re-evaluate and update labels even if resources already carry valid compliant tags.
```bash
python3 scripts/finops_tagger.py --force /path/to/terraform/dir
```

---

## 🛠️ Gemini Integration Setup

To enable Gemini-suggested label recommendations:
1. Ensure the Google Cloud AI Platform package is installed:
   ```bash
   pip install google-cloud-aiplatform
   ```
2. Define the project and location environment variables:
   ```bash
   export PROJECT_ID="your-gcp-project-id"
   export LOCATION_ID="us-central1"
   ```
If environment variables are not set, the tagger will print a warning and fallback to standard static defaults.

## 🐍 BigQuery Python Query Tagging

The script automatically scans for Google Cloud BigQuery client `.query(...)` calls in `.py` source files. If queries are missing execution configurations, it flags them as non-compliant.

For coding implementations, config structures, and details on how these tags are used to run billing analysis queries, please refer to [cost_analysis.md](file:///Users/shivaanij/skills/.agents/skills/agent-governance-resource-labeling/references/cost_analysis.md).

---

## 🧠 Agent Interaction Rules

When a user asks "Show me how to track agent usage costs" or similar tracking queries, the assistant must:
1. Clearly explain the standard labeling rules (mandatory vs optional labels).
2. Display a sample BigQuery SQL query to analyze spend.
3. Do not write any files to the system or desktop, nor run terminal commands.
4. Provide clickable markdown links pointing directly to [cost_tracking.md](file:///Users/shivaanij/skills/.agents/skills/agent-governance-resource-labeling/references/cost_tracking.md) and [cost_analysis.md](file:///Users/shivaanij/skills/.agents/skills/agent-governance-resource-labeling/references/cost_analysis.md).
