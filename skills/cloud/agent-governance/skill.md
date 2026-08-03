---
name: agent-governance
description: Enforce Cloud FinOps cost-tracking compliance by auto-tagging GCP Terraform resources with standard metadata.
---

# Agent Governance: FinOps Cost-Tracking & Compliance

This skill helps maintain organizational cost compliance for all agent infrastructure resources by enforcing standard metadata tags across GCP Terraform resource definitions.

## Key Features

1. **Auto-Tagging**: Scan and update GCP resource blocks in `.tf` files with cost-tracking labels.
2. **Governance Check**: Validate existing or proposed labels against the defined schema in [cost_tracking.md](file:///Users/shivaanij/skills/skills/cloud/agent-governance/references/cost_tracking.md).
3. **Smart Labeling**: Leverage Vertex AI Gemini to analyze HCL blocks and suggest contextual metadata labels.
4. **Validation Modes**: Supports Interactive, Dry-Run, and Strict validation compliance checks.

---

## 📋 Labeling Standards

The labeling standards are loaded dynamically from [cost_tracking.md](file:///Users/shivaanij/skills/skills/cloud/agent-governance/references/cost_tracking.md). The required metadata tags are:

| Label Key | Valid Values | Description |
| :--- | :--- | :--- |
| **`agent-id`** | `[a-z0-9_-]{3,63}` | Unique identifier of the deploying agent. |
| **`business-unit`** | `engineering`, `finance`, `consulting` | The department paying for resources. |
| **`environment`** | `dev`, `staging`, `uat`, `prod` | Deployment lifecycle tier. |

### Allowed Resource Types
Only GCP resource types supporting a `labels` block are tagged (e.g., `google_compute_instance`, `google_storage_bucket`). An allowlist of supported types is defined in [cost_tracking.md](file:///Users/shivaanij/skills/skills/cloud/agent-governance/references/cost_tracking.md#L15).

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
