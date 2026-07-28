#!/usr/bin/env python3
import os
import sys
import re
import argparse
import json

def parse_args():
    parser = argparse.ArgumentParser(description="Autonomous GitOps & SDK FinOps Engine")
    parser.add_argument("--suggest", action="store_true", help="Scan Git metadata and suggest optimized tags.")
    parser.add_argument("--apply", action="store_true", help="Interactively confirm and patch codebase files.")
    parser.add_argument("--agent-id", type=str, help="Overridden agent-id.")
    parser.add_argument("--bu", type=str, help="Overridden business-unit.")
    parser.add_argument("--env", type=str, help="Overridden environment.")
    return parser.parse_args()

def infer_git_metadata():
    """Infers standardized billing metadata from directory, repo, and branch configurations."""
    # 1. Infer Environment from Branch
    branch_name = "dev"
    try:
        # Check standard CI/CD environment variables or execute Git command
        branch = os.environ.get("GITHUB_REF_NAME") or os.environ.get("CI_COMMIT_REF_NAME")
        if not branch:
            stream = os.popen("git rev-parse --abbrev-ref HEAD 2>/dev/null")
            branch = stream.read().strip()
        
        if branch in ["main", "master", "prod"]:
            branch_name = "prod"
        elif branch in ["staging", "qa"]:
            branch_name = "staging"
    except Exception:
        pass

    # 2. Infer Agent ID from project path
    agent_id = "default-agent"
    try:
        # Use current folder or directory name
        cwd = os.getcwd()
        agent_id = os.path.basename(cwd).lower()
        # Ensure it conforms to GCP regex constraints
        agent_id = re.sub(r'[^a-z0-9_-]', '', agent_id)[:63]
    except Exception:
        pass

    # 3. Infer Business Unit from git actor email domain or repository
    bu = "pso"
    try:
        stream = os.popen("git config user.email 2>/dev/null")
        email = stream.read().strip().lower()
        if "finance" in email:
            bu = "finance"
        elif "eng" in email or "dev" in email:
            bu = "engineering"
    except Exception:
        pass

    return {
        "agent-id": agent_id,
        "business-unit": bu,
        "environment": branch_name
    }

def scan_and_patch_terraform(values):
    """Recursively targets and updates Terraform config blocks with inferred tags."""
    target_resources = [
        "google_cloud_run_v2_service", 
        "google_storage_bucket", 
        "google_bigquery_dataset", 
        "google_vertex_ai_endpoint",
        "google_vertex_ai_reasoning_engine",
        "google_pubsub_topic"
    ]

    for root, _, files in os.walk("."):
        if ".git" in root or ".agents" in root:
            continue
        for file in files:
            if file.endswith(".tf"):
                filepath = os.path.join(root, file)
                with open(filepath, "r") as f:
                    content = f.read()

                modified = False
                new_lines = []
                lines = content.splitlines()

                for i, line in enumerate(lines):
                    new_lines.append(line)
                    if any(re.search(rf'resource\s+"{res}"', line) for res in target_resources):
                        # Ensure we don't double-tag
                        has_labels = False
                        for check_idx in range(i+1, min(i+40, len(lines))):
                            check_line = lines[check_idx]
                            if "labels =" in check_line or "labels {" in check_line:
                                has_labels = True
                                break
                            if "}" in check_line:
                                break

                        if not has_labels:
                            indent = "  "
                            labels_block = (
                                f"\n{indent}labels = {{\n"
                                f"{indent}  agent-id      = \"{values['agent-id']}\"\n"
                                f"{indent}  business-unit = \"{values['business-unit']}\"\n"
                                f"{indent}  environment   = \"{values['environment']}\"\n"
                                f"{indent}}}"
                            )
                            new_lines.append(labels_block)
                            modified = True

                if modified:
                    with open(filepath, "w") as f:
                        f.write("\n".join(new_lines) + "\n")
                    print(f"✅ Automatically patched Terraform resource manifests in {filepath}")

def scan_and_patch_code(values):
    """Finds unlabelled database / Model initialization blocks and alerts developers."""
    print("📝 Auditing API Query logic in codebase files...")
    extensions = [".py", ".js", ".java", ".go"]
    for root, _, files in os.walk("."):
        if ".git" in root or ".agents" in root:
            continue
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                filepath = os.path.join(root, file)
                with open(filepath, "r") as f:
                    lines = f.readlines()

                for idx, line in enumerate(lines):
                    # Check for DB calls missing Comment Tracing
                    if "execute(" in line and "SELECT" in line and "/*" not in line:
                        print(f"  ⚠️ Warning [Database]: {filepath}:{idx+1} -> Database execution missing comment trace metadata!")
                        print(f"     ↳ Fix Suggestion: Prepend /* {json.dumps(values)} */ to query string.")

if __name__ == "__main__":
    args = parse_args()
    
    # Generate metadata suggestions
    inferred = infer_git_metadata()
    
    # Apply CLI overrides if available
    final_values = {
        "agent-id": args.agent_id or inferred["agent-id"],
        "business-unit": args.bu or inferred["business-unit"],
        "environment": args.env or inferred["environment"]
    }

    if args.suggest:
        print("\n=======================================================")
        print("🔍 CI/CD FINOPS METADATA SUGGESTION CARD")
        print("=======================================================")
        print(f"Based on Git analysis, we recommend these deployment labels:")
        print(f"  * agent-id:      {final_values['agent-id']} (inferred from repository directory)")
        print(f"  * business-unit: {final_values['business-unit']} (inferred from git user context)")
        print(f"  * environment:   {final_values['environment']} (inferred from active branch)")
        print("=======================================================\n")
        sys.exit(0)

    if args.apply:
        print("\n=======================================================")
        print("🚀 EXECUTING GITOPS PATCh CODEBASE")
        print("=======================================================")
        print(f"Applying parameters:")
        print(f"  {json.dumps(final_values, indent=2)}")
        print("=======================================================\n")
        
        scan_and_patch_terraform(final_values)
        scan_and_patch_code(final_values)
