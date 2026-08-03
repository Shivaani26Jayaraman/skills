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

## 🧱 The 5 Core Pillars of the Script

### 1. Smart Resource Filtering (Resource Allowlist)
* **What it does**: Google Cloud allows labels on many resources (e.g., Virtual Machines, Storage Buckets, BigQuery Datasets), but not on all resources (e.g., Firewall Rules, IAM Policies). Attempting to inject labels into unsupported resources causes `terraform apply` to crash.
* **How it works**: The script maintains an allowlist of label-supported GCP resource types (`DEFAULT_LABELABLE_TYPES`) and dynamically reads additional types from a central rules file ([cost_tracking.md](file:///Users/shivaanij/skills/skills/cloud/agent-governance/references/cost_tracking.md#L15)).
* **Example**:
  - ❌ `google_compute_firewall` → Skipped (GCP does not support labels here)
  - ✅ `google_storage_bucket` → Tagged (GCP supports labels here)

### 2. Intelligent Code Parser (Safe Brace Matching)
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

### 3. Compliance Skipping (Cost & Speed Optimization)
* **What it does**: If a Terraform resource is already fully compliant with company labeling rules, editing it again is a waste of time and computational/API costs.
* **How it works**: The script inspects existing tags using `is_resource_compliant()`. If a resource already contains valid required keys (`agent-id`, `business-unit`, `environment`), it skips the resource completely (avoiding file writes and Gemini AI API calls) unless forced with `--force`.
* **Example**:
  If a BigQuery table already has:
  - `agent-id = "support-bot"`
  - `business-unit = "engineering"`
  - `environment = "staging"`
  *Action*: Script outputs `skipped 1 resource(s) already governance-compliant` and moves on.

### 4. Double-Layer Validation Guardrails
* **What it does**: Ensures every tag added adheres to both Google Cloud's hard technical limits and company FinOps rules.
* **How it works**:
  1. **Layer 1: GCP Rules (`validate_gcp_label`)**: Ensures keys and values use only lowercase letters, numbers, dashes, and underscores (max 63 chars). If a value fails (e.g. contains capitals), it throws a hard error and forces re-input.
  2. **Layer 2: Corporate Governance Rules (`validate_inputs`)**: Reads company rules from `cost_tracking.md` to enforce exact choices (e.g., environment must be `dev`, `staging`, `uat`, or `prod`).
* **Example**:
  Developer tries to input: `environment = "PROD_MAIN"`
  - ❌ GCP Violation: Uppercase letters are not allowed in GCP labels.
  - ❌ Governance Violation: `"PROD_MAIN"` is not in the allowed list `[dev, staging, uat, prod]`.
  - *Result*: Script catches and rejects the value before it touches production infrastructure.

### 5. Gemini AI Assistance & Safe Execution Modes
* **What it does**: Gives developers AI-assisted tag suggestions and complete preview control over code modifications.
* **How it works**:
  - **Vertex AI Gemini (`gemini-3.5-flash`)**: Reads the resource definition and suggests context-aware tags (e.g., suggesting custom tags like `tier = "database"` for a SQL instance).
  - **Dry-Run Mode (`--dry-run`)**: Generates a preview diff showing exactly what line additions will happen without touching any files on disk.
  - **Interactive Mode (`-i`)**: Interactively guides developers through prompting, offering Gemini suggestions for custom labels at the end of the required fields.

---

## 📊 Stakeholder Pitch Summary Table

| Feature / Logic | Why It Matters to Business / Leadership | How It Works Under the Hood |
| :--- | :--- | :--- |
| **Resource Allowlist** | **Prevents broken builds** by avoiding invalid label injection. | Ignores non-labelable GCP resource types. |
| **Safe Parser** | **Zero code corruption** in complex Terraform files. | String-, comment-, and heredoc-aware brace matcher. |
| **Compliance Skipping** | **Saves API costs & execution time** at enterprise scale. | Bypasses resources that are already valid. |
| **Validation Rules** | **Guarantees 100% compliant cloud billing data.** | Enforces GCP rules + dynamic rules from `cost_tracking.md`. |
| **Gemini AI Integration** | **Reduces manual toil** by auto-inferring metadata. | Analyzes resource code using Vertex AI to propose tags. |
| **Dry-Run Mode** | **Risk mitigation & safe previewing** before commit. | Output unified `diff`s without writing to disk. |

---

## 🚀 Execution Modes & Commands

Assuming your terminal is currently navigated to your target Terraform directory (e.g., `/Users/shivaanij/skills/governance-sandbox`):

### 1. Interactive Dry-Run (Gemini Enabled)
Set your location to a region supporting `gemini-3.5-flash` (e.g., `europe-west2` or `asia-south1`), and run:
```bash
export LOCATION_ID="europe-west2"
python3 /Users/shivaanij/skills/skills/cloud/agent-governance/scripts/finops_tagger.py --dry-run -i --force .
```

### 2. Quiet / Static Tagging (Automated CI/CD)
Tags files automatically using static values provided via arguments (no prompts, no Gemini AI):
```bash
python3 /Users/shivaanij/skills/skills/cloud/agent-governance/scripts/finops_tagger.py \
  --agent-id "customer-support-bot" \
  --business-unit "engineering" \
  --environment "prod" \
  --no-gemini .
```

### 3. Strict Compliance Checks
Errors out and halts (exit status 1) if existing resources fail standard choice checks or regex validation:
```bash
python3 /Users/shivaanij/skills/skills/cloud/agent-governance/scripts/finops_tagger.py --strict .
```

---

## 🎯 Skill Configuration (`SKILL.md`)

The [SKILL.md](file:///Users/shivaanij/skills/skills/cloud/agent-governance/SKILL.md) file registers this project as a specialized skill for Antigravity:
- **YAML Frontmatter**: Defines `name: agent-governance` and a short description used to match tasks that require auto-tagging or auditing Terraform directories.
- **Usage Reference**: Serves as a quick reference sheet for agent prompts on how to run scripts, supply defaults, and troubleshoot validation problems.
