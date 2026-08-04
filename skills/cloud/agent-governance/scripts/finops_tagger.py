#!/usr/bin/env python3
import os
import sys
import re
import argparse

# Compliant Label Keys
MANDATORY_LABELS = ["agent-id", "business-unit", "environment"]

def parse_args():
    parser = argparse.ArgumentParser(description="GitOps & SDK Cost Tracking Compliance Engine")
    parser.add_argument("--scan", action="store_true", help="Recursively scan repository for tagging issues.")
    parser.add_argument("--apply", action="store_true", help="Inject/Patch missing labels inside Terraform files.")
    parser.add_argument("--agent-id", type=str, help="Value for 'agent-id' label.")
    parser.add_argument("--bu", type=str, help="Value for 'business-unit' label.")
    parser.add_argument("--env", type=str, help="Value for 'environment' label.")
    return parser.parse_args()

def scan_terraform(apply_mode, config_values=None):
    """Scan and patch Terraform files for compliance."""
    print("🤖 Scanning workspace for Terraform files (.tf)...")
    tf_files = []
    for root, _, files in os.walk("."):
        # Prevent checking inside hidden dirs or git directories
        if ".git" in root or ".agents" in root:
            continue
        for file in files:
            if file.endswith(".tf"):
                tf_files.append(os.path.join(root, file))

    if not tf_files:
        print("ℹ️  No Terraform files (.tf) found in this repository.")
        return

    target_resources = [
        "google_cloud_run_v2_service", 
        "google_storage_bucket", 
        "google_bigquery_dataset", 
        "google_vertex_ai_endpoint"
    ]

    for filepath in tf_files:
        print(f"Checking file: {filepath}")
        with open(filepath, "r") as f:
            content = f.read()

        modified = False
        # Regex to capture the resource block name and opening brace
        for res_type in target_resources:
            pattern = rf'(resource\s+"{res_type}"\s+"[^"]+"\s+{{)'
            matches = list(re.finditer(pattern, content))
            
            if not matches:
                continue

            print(f"  👉 Found resources of type '{res_type}'")
            
            # Simple line-by-line adjustment block
            lines = content.splitlines()
            new_lines = []
            skip = False

            for i, line in enumerate(lines):
                new_lines.append(line)
                # If we encounter the resource match, check if labels exist
                if any(re.search(rf'resource\s+"{res_type}"', line) for res_type in target_resources):
                    # Check next few lines for 'labels'
                    has_labels = False
                    block_depth = 0
                    for check_idx in range(i+1, min(i+40, len(lines))):
                        check_line = lines[check_idx]
                        if "labels =" in check_line or "labels {" in check_line:
                            has_labels = True
                            break
                        if "}" in check_line and block_depth == 0:
                            break

                    if not has_labels:
                        print(f"    ❌ MISSING FinOps Labels inside resource definition!")
                        if apply_mode and config_values:
                            # Inject labels map block immediately below opening block
                            indent = "  "
                            labels_block = (
                                f"\n{indent}labels = {{\n"
                                f"{indent}  agent-id      = \"{config_values['agent-id']}\"\n"
                                f"{indent}  business-unit = \"{config_values['bu']}\"\n"
                                f"{indent}  environment   = \"{config_values['env']}\"\n"
                                f"{indent}}}"
                            )
                            new_lines.append(labels_block)
                            modified = True
                            print("    ✅ Injected compliance labeling block.")

            if modified:
                content = "\n".join(new_lines)
                with open(filepath, "w") as f:
                    f.write(content)

def scan_application_code():
    """Scan codebases for API query paths to verify SDK labeling rules."""
    print("\n📝 Scanning codebase files for API invocations...")
    extensions = [".py", ".js", ".java", ".go"]
    code_files = []
    
    for root, _, files in os.walk("."):
        if ".git" in root or ".agents" in root:
            continue
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                code_files.append(os.path.join(root, file))

    for filepath in code_files:
        with open(filepath, "r") as f:
            lines = f.readlines()

        for idx, line in enumerate(lines):
            # Check for unlabelled BigQuery transactions
            if "bigquery.Client()" in line or ".query(" in line:
                # Check surrounding context for 'job_config' or 'labels' configuration
                has_labels_ctx = False
                for check_idx in range(max(0, idx-5), min(len(lines), idx+5)):
                    if "job_config" in lines[check_idx] or "labels" in lines[check_idx]:
                        has_labels_ctx = True
                        break
                
                if not has_labels_ctx:
                    print(f"  ⚠️ Warning [BQ API]: {filepath}:{idx+1} -> Potential unlabelled BQ Query invocation found.")
                    print("     ↳ Recommendation: Pass query configuration labels using 'QueryJobConfig' to map cost drivers.")

            # Check for unlabeled Vertex AI Client initializations
            if "GenerativeModel(" in line or "vertexai.init(" in line:
                has_labels_ctx = False
                for check_idx in range(max(0, idx-5), min(len(lines), idx+5)):
                    if "labels=" in lines[check_idx]:
                        has_labels_ctx = True
                        break
                
                if not has_labels_ctx:
                    print(f"  ⚠️ Warning [Vertex AI]: {filepath}:{idx+1} -> Potential unlabelled Vertex SDK instantiation.")
                    print("     ↳ Recommendation: Pass an initialized metadata dictionary with the model endpoint configuration.")

if __name__ == "__main__":
    args = parse_args()
    
    if not args.scan and not args.apply:
        print("❌ Please specify either --scan or --apply.")
        sys.exit(1)

    if args.scan:
        scan_terraform(apply_mode=False)
        scan_application_code()

    if args.apply:
        # Validate that values are passed for patching
        if not args.agent_id or not args.bu or not args.env:
            print("❌ Error: --apply requires --agent-id, --bu, and --env options to patch configurations.")
            sys.exit(1)
        
        config = {
            "agent-id": args.agent_id,
            "bu": args.bu,
            "env": args.env
        }
        scan_terraform(apply_mode=True, config_values=config)
        print("\n🎉 Auto-tagging complete! Run 'git diff' to review configuration updates.")
