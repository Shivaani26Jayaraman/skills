# Agent Governance & Cloud FinOps Compliance Tooling

This directory provides automated compliance checks and auto-tagging for GCP resources defined in Terraform files. It ensures that all cloud infrastructure deployed for agents is cost-compliant and conforms to corporate FinOps standards.

---

## 🎯 The Elevator Pitch

* **The Problem**: Cloud cost tracking fails when developers deploy GCP resources without proper labels (tags). Unlabelled or mislabelled resources make cloud bills a black hole, making it impossible to attribute costs to teams, projects, or AI agents.
* **The Solution**: `finops_tagger.py` is an automated governance script. It scans Google Cloud Infrastructure-as-Code (Terraform files), validates resource labels against company policy, and automatically injects missing cost-tracking tags without breaking infrastructure deployments.

---

## 📂 Directory Layout

```
agent-governance/
├── SKILL.md                 # Agent-facing skill metadata and behavior triggers
├── README.md                # General introduction and technical workflow guide
├── references/
│   └── cost_tracking.md     # Governance standard defining schema rules, allowlist, and BigQuery analytics
└── scripts/
    └── finops_tagger.py     # Core Python auto-tagger and validator script
```

---

## 🏷️ Labeling Standards

The compliance engine enforces the following metadata attributes:

### Mandatory Labels
| Label Key | Valid Values | Description |
| :--- | :--- | :--- |
| **`agent-id`** | `[a-z0-9_-]{3,63}` | Unique identifier of the deploying agent. |
| **`business-unit`** | `engineering`, `finance`, `consulting` | The department paying for resources. |
| **`environment`** | `dev`, `staging`, `uat`, `prod` | Deployment lifecycle tier. |

### Optional Labels
| Label Key | Valid Values | Description |
| :--- | :--- | :--- |
| **`cost-centre`** | `cc-[a-z0-9_-]{3,10}` | Billing code / cost center associated with the resources. |
| **`team`** | `[a-z0-9_-]{2,63}` | The specific team owning the agent resource. |

### Supported GCP Services
The compliance engine targets and validates labels for all GCP services officially supporting resource-level labels. These include:

* **AI Platform & Vertex AI** (e.g., `google_vertex_ai_endpoint`, notebooks, models)
* **App Engine** (Flexible and Standard environments)
* **Artifact Registry** (e.g., `google_artifact_registry_repository`)
* **Batch** (batch jobs and VMs)
* **BigQuery** (e.g., `google_bigquery_dataset`, `google_bigquery_table`)
* **Certificate Authority Service**
* **Cloud Bigtable**
* **Cloud Composer / Apache Airflow** (e.g., `google_composer_environment`)
* **Cloud Deployment Manager**
* **Cloud Functions / Cloud Run functions** (e.g., `google_cloudfunctions_function`, `google_cloudfunctions2_function`)
* **Cloud Healthcare API**
* **Cloud Key Management Service (KMS)**
* **Cloud Run** (e.g., `google_cloud_run_service`, `google_cloud_run_v2_service`, jobs)
* **Cloud Spanner** (e.g., `google_spanner_instance`)
* **Cloud SQL** (e.g., `google_sql_database_instance`)
* **Cloud Storage (GCS)** (e.g., `google_storage_bucket`)
* **Cloud Translation**
* **Compute Engine** (e.g., `google_compute_instance`, template, disk, image, snapshot, IP addresses)
* **Dataflow** (e.g., `google_dataflow_job`)
* **Dataproc / Apache Spark** (e.g., `google_dataproc_cluster`)
* **Filestore** (e.g., `google_filestore_instance`)
* **Google Kubernetes Engine (GKE)** (e.g., `google_container_cluster`, node pools)
* **Memorystore / Redis** (e.g., `google_redis_instance`)
* **Networking** (e.g., global forwarding rules, load balancer IP allocations)
* **Pub/Sub** (e.g., `google_pubsub_topic`, `google_pubsub_subscription`)
* **reCAPTCHA Enterprise**
* **Resource Manager** (projects level metadata)
* **Secret Manager** (e.g., `google_secret_manager_secret`)
* **Transcoder API**
* **Workflows** (e.g., `google_workflows_workflow`)

---

---

## ⚙️ CI/CD Workflow Integration

The governance check runs automatically on pull requests and pushes targeting the `main` branch to guarantee that no unlabelled or non-compliant infrastructure reaches production:
1. **Trigger**: Pull requests or pushes trigger the [FinOps Compliance Audit](file:///.github/workflows/finops-compliance.yml) workflow.
2. **Execution Script**: The pipeline executes the `finops_tagger.py` script in check-and-strict mode:
   ```bash
   python3 .agents/skills/agent-governance-resource-labeling/scripts/finops_tagger.py --check --strict skills/governance-sandbox/
   ```
3. **Guardrail**: If any non-compliant Terraform resource, provider, or BigQuery Python query is found, the script prints the offending files and exits with status `1`, blocking the build or PR merge.

---

## 🛠️ The Compliance Script (`finops_tagger.py`)

Under the hood, compliance auditing and auto-tagging are handled by the `scripts/finops_tagger.py` Python engine. This section details its core pillars, execution commands, and language-specific features.

### 🧱 The 5 Core Pillars of the Script

#### 1. Smart Resource Filtering (Resource Allowlist)
* **What it does**: Google Cloud allows labels on many resources (e.g., Virtual Machines, Storage Buckets, BigQuery Datasets), but not on all resources (e.g., Firewall Rules, IAM Policies). Attempting to inject labels into unsupported resources causes `terraform apply` to crash.
* **How it works**: The script maintains an allowlist of label-supported GCP resource types (`DEFAULT_LABELABLE_TYPES`) and dynamically reads additional types from a central rules file ([cost_tracking.md](file:///Users/shivaanij/skills/skills/cloud/agent-governance/references/cost_tracking.md#L15)).
* **Example**:
  - ❌ `google_compute_firewall` → Skipped (GCP does not support labels here)
  - ✅ `google_storage_bucket` → Tagged (GCP supports labels here)

#### 2. Intelligent Code Parser (Safe Brace Matching)
* **What it does**: Terraform blocks use curly braces `{ }`. However, scripts, strings, heredocs (`<<-EOT`), and comments inside Terraform code also use curly braces. Simple search-and-replace scripts break Terraform code when they mistake internal braces for block boundaries.
* **How it works**: The script includes a custom parser (`find_block_end()`) that understands Terraform syntax. It safely skips over comments, strings, `${}` variable interpolations, and bash script blocks.
* **Example**:
  ```hcl
  resource "google_compute_instance" "app_server" {
    name = "web-vm"
    startup_script = <<-EOT
      if [ $STATUS == "OK" ]; { echo "Ready"; } # <-- Internal script braces
    EOT
  }
  ```
  *Result*: The parser safely ignores the bash `{ echo "Ready"; }` and adds the `labels = { ... }` block at the correct position without syntax corruption.

#### 3. Compliance Skipping (Cost & Speed Optimization)
* **What it does**: If a Terraform resource is already fully compliant with company labeling rules, editing it again is a waste of time and computational/API costs.
* **How it works**: The script inspects existing tags using `is_resource_compliant()`. If a resource already contains valid required keys (`agent-id`, `business-unit`, `environment`), it skips the resource completely (avoiding file writes and Gemini AI API calls) unless forced with `--force`.
* **Example**:
  If a BigQuery table already has:
  - `agent-id = "support-bot"`
  - `business-unit = "engineering"`
  - `environment = "staging"`
  *Action*: Script outputs `skipped 1 resource(s) already governance-compliant` and moves on.

#### 4. Double-Layer Validation Guardrails
* **What it does**: Ensures every tag added adheres to both Google Cloud's hard technical limits and company FinOps rules.
* **How it works**:
  1. **Layer 1: GCP Rules (`validate_gcp_label`)**: Ensures keys and values use only lowercase letters, numbers, dashes, and underscores (max 63 chars). If a value fails (e.g. contains capitals), it throws a hard error and forces re-input.
  2. **Layer 2: Corporate Governance Rules (`validate_inputs`)**: Reads company rules from `cost_tracking.md` to enforce exact choices (e.g., environment must be `dev`, `staging`, `uat`, or `prod`).
* **Example**:
  Developer tries to input: `environment = "PROD_MAIN"`
  - ❌ GCP Violation: Uppercase letters are not allowed in GCP labels.
  - ❌ Governance Violation: `"PROD_MAIN"` is not in the allowed list `[dev, staging, uat, prod]`.
  - *Result*: Script catches and rejects the value before it touches production infrastructure.

#### 5. Gemini AI Assistance & Safe Execution Modes
* **What it does**: Gives developers AI-assisted tag suggestions and complete preview control over code modifications.
* **How it works**:
  - **Vertex AI Gemini (`gemini-3.5-flash`)**: Reads the resource definition and suggests context-aware tags (e.g., suggesting custom tags like `tier = "database"` for a SQL instance).
  - **Dry-Run Mode (`--dry-run`)**: Generates a preview diff showing exactly what line additions will happen without touching any files on disk.
  - **Interactive Mode (`-i`)**: Interactively guides developers through prompting, offering Gemini suggestions for custom labels at the end of the required fields.

---

### 📊 Stakeholder Pitch Summary Table

| Feature / Logic | Why It Matters to Business / Leadership | How It Works Under the Hood |
| :--- | :--- | :--- |
| **Resource Allowlist** | **Prevents broken builds** by avoiding invalid label injection. | Ignores non-labelable GCP resource types. |
| **Safe Parser** | **Zero code corruption** in complex Terraform files. | String-, comment-, and heredoc-aware brace matcher. |
| **Compliance Skipping** | **Saves API costs & execution time** at enterprise scale. | Bypasses resources that are already valid. |
| **Validation Rules** | **Guarantees 100% compliant cloud billing data.** | Enforces GCP rules + dynamic rules from `cost_tracking.md`. |
| **Gemini AI Integration** | **Reduces manual toil** by auto-inferring metadata. | Analyzes resource code using Vertex AI to propose tags. |
| **Dry-Run Mode** | **Risk mitigation & safe previewing** before commit. | Output unified `diff`s without writing to disk. |

---

### 🚀 Execution Modes & Commands

Below are the supported command-line flags and execution modes for running `scripts/finops_tagger.py` manually:

Assuming your terminal is currently navigated to your target Terraform directory (e.g., `/Users/shivaanij/skills/governance-sandbox`):

#### A. Interactive Dry-Run (Gemini Enabled)
Set your location to a region supporting `gemini-3.5-flash` (e.g., `europe-west2` or `asia-south1`), and run:
```bash
export LOCATION_ID="europe-west2"
python3 /Users/shivaanij/skills/skills/cloud/agent-governance/scripts/finops_tagger.py --dry-run -i --force .
```

#### B. Quiet / Static Tagging (Automated CI/CD)
Tags files automatically using static values provided via arguments (no prompts, no Gemini AI):
```bash
python3 /Users/shivaanij/skills/skills/cloud/agent-governance/scripts/finops_tagger.py \
  --agent-id "customer-support-bot" \
  --business-unit "engineering" \
  --environment "prod" \
  --no-gemini .
```

#### C. Strict Compliance Checks
Errors out and halts (exit status 1) if existing resources fail standard choice checks or regex validation:
```bash
python3 /Users/shivaanij/skills/skills/cloud/agent-governance/scripts/finops_tagger.py --strict .
```

---

## 💡 How the AI Skill Works

The compliance system acts as an agentic AI Skill matching user requests related to cost-tracking and metadata governance:
1. **Matching**: When you ask Antigravity to check compliance or tag resources, the agent triggers the `agent-governance` skill.
2. **Behind-the-Scenes Execution**: The agent automatically handles the script execution, directory scanning, and rule parsing behind the scenes.
3. **Interactive Label-Level Confirmation**: Rather than executing changes blindly, the agent guides you through a safety-first workflow:
   * It queries you in the chat interface iteratively for each label key value (offering defaults or Gemini suggestions).
   * It presents a preview summary of the proposed tags and planned command.
   * It requests explicit confirmation (`Yes/No` prompt) in a separate turn before running any mutating command.

---

## 🎯 Skill Configuration (`SKILL.md`)

The [SKILL.md](file:///Users/shivaanij/skills/skills/cloud/agent-governance/SKILL.md) file registers this project as a specialized skill for Antigravity:
- **YAML Frontmatter**: Defines `name: agent-governance` and a short description used to match tasks that require auto-tagging or auditing Terraform directories.
- **Usage Reference**: Serves as a quick reference sheet for agent prompts on how to run scripts, supply defaults, and troubleshoot validation problems.



