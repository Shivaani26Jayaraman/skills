---
name: agent-platform-governance
metadata:
  category: AiAndMachineLearning
  description: Manages, applies, and audits Governance, Security, and Cost policies for the Agent Platform. Use when you need to configure Agent Gateways, Model Armor templates, IAM/IAP conditions, or cost-tracking labels.
---

# Agent Platform Governance & Cost Tracking

This skill provides instructions for managing, applying, and auditing security guards, granular access controls, and automated FinOps labeling for agents deployed on the Agent Platform.

## Usage Guide

To use this skill effectively:
1. **No Workspace Pollution:** Do NOT create or write any of the reference files or scripts to the user's workspace root. They are already packaged within this skill's directory at `skills/cloud/agent-governance/`.
2. **Reference Correct Paths with Labels:** Always point the user to the existing files inside the skill folder using descriptive, readable link text. Do not emit blank links. Use these exact paths:
   - [IAM Conditions Guide](skills/cloud/agent-governance/references/iam_conditions.md)
   - [Model Armor Configuration Guide](skills/cloud/agent-governance/references/model_armor_config.md)
   - [Cost Tracking & FinOps Reference](skills/cloud/agent-governance/references/cost_tracking.md)
   - [Policy Deployment Script](skills/cloud/agent-governance/scripts/apply_policies.sh)
   - [GitOps CI/CD Auto-Tagger Script](skills/cloud/agent-governance/scripts/finops_ci_tagger.py)

---

## Safety & Confirmation Tiers (CRITICAL)

Before executing any commands or scripts on behalf of the user, you MUST adhere to the following safety tiers:

* **Tier R: Read-only** (list, describe, get, query, scan)
  * No confirmation needed. Execute immediately to gather policy information.
* **Tier M: Mutating & Reversible** (apply, update, import, set, patch)
  * Requires interactive confirmation with 'Yes'/'No' options before applying configurations.
  * **Same-turn restriction:** Do not execute code in the same turn as presenting the confirmation prompt. Stop and wait for the user's approval.
* **Tier D: Destructive & Irreversible** (delete, disable)
  * Requires explicit typed confirmation (e.g., "I confirm"). Ask for confirmation IMMEDIATELY before any checks.

---

## Phase 0: Environment Setup

CRITICAL: Before running any `gcloud` commands, advise the user to initialize their environment:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project $PROJECT_ID
```

---

## 1. Automated GitOps & SDK Tagging (Tier M)

Automate cost-attribution by running our Git-aware metadata scanner during local development pre-commits or within active CI/CD loops.

### Git Context Scanning & Patching
Scan files, suggest context-inferred tags (built from folder layouts and branches), and recursively patch Terraform configs, Python code, and SQL Query comments:
```bash
# Analyze repository metadata and present the suggested label allocation card
python3 skills/cloud/agent-governance/scripts/finops_ci_tagger.py --suggest

# Execute code auto-patching (Tier M - Confirmation required)
python3 skills/cloud/agent-governance/scripts/finops_ci_tagger.py --apply
```

---

## 2. Best Practices

* **Audit Query Comments:** Ensure AlloyDB and Cloud Spanner queries include leading query tags so costs show up in Database Query Insights.
* **Fail Open/Closed:** Ensure `failOpen: false` configuration is explicitly decided in Gateway Service Extensions.
