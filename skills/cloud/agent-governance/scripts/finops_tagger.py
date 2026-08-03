#!/usr/bin/env python3
"""
finops_tagger.py — Auto-tag GCP Terraform resources with FinOps cost-tracking labels.

Key production hardening over the original version:
  1. Resource-type allowlist: only tags resource types that actually support a
     `labels` attribute in GCP, so it never injects invalid HCL.
  2. String/comment/heredoc-aware brace matching: won't miscompute block
     boundaries because of "{" or "}" inside string literals, ${} interpolation,
     comments, or heredocs.
  3. Compliance skip: resources that already carry valid labels are skipped
     entirely (no file rewrite, no Gemini call) unless --force is passed —
     this is what keeps Gemini API cost/latency down at scale.
  4. --dry-run: preview a unified diff without touching any file.
  5. Gemini is offered as a fallback whenever the user rejects an existing/
     default label value in interactive mode, not just for "extra" labels.
"""
import os
import sys
import re
import json
import difflib
import argparse

# ---------------------------------------------------------------------------
# Default allowlist of GCP resource types known to support a `labels` block.
# This can be extended (not replaced) via a "## Labelable Resource Types"
# section in cost_tracking.md — see load_governance_rules().
# ---------------------------------------------------------------------------
DEFAULT_LABELABLE_TYPES = {
    "google_compute_instance",
    "google_compute_instance_template",
    "google_compute_region_instance_template",
    "google_compute_disk",
    "google_compute_region_disk",
    "google_compute_image",
    "google_compute_snapshot",
    "google_compute_address",
    "google_compute_global_address",
    "google_compute_forwarding_rule",
    "google_compute_global_forwarding_rule",
    "google_container_cluster",
    "google_container_node_pool",
    "google_sql_database_instance",
    "google_storage_bucket",
    "google_bigquery_dataset",
    "google_bigquery_table",
    "google_pubsub_topic",
    "google_pubsub_subscription",
    "google_cloudfunctions_function",
    "google_cloudfunctions2_function",
    "google_cloud_run_service",
    "google_cloud_run_v2_service",
    "google_cloud_run_v2_job",
    "google_dataflow_job",
    "google_dataproc_cluster",
    "google_composer_environment",
    "google_redis_instance",
    "google_filestore_instance",
    "google_spanner_instance",
    "google_artifact_registry_repository",
    "google_vertex_ai_endpoint",
    "google_notebooks_instance",
    "google_workflows_workflow",
    "google_secret_manager_secret",
}

REQUIRED_LABEL_KEYS = ("agent-id", "business-unit", "environment")


def _governance_paths():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(script_dir, "..", "references", "cost_tracking.md"))


def load_governance_rules():
    """Load labeling rules AND the labelable-resource-type allowlist from cost_tracking.md."""
    cost_tracking_path = _governance_paths()

    rules = {}
    labelable_types = set(DEFAULT_LABELABLE_TYPES)

    if not os.path.exists(cost_tracking_path):
        return rules, labelable_types

    try:
        with open(cost_tracking_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        in_types_section = False
        for raw_line in lines:
            line = raw_line.strip()

            if line.startswith("#"):
                in_types_section = line.lstrip("#").strip().lower() == "labelable resource types"
                continue

            if in_types_section:
                if line.startswith("-"):
                    rtype = line.lstrip("-").strip().strip("`")
                    if rtype:
                        labelable_types.add(rtype)
                continue

            if not line.startswith("|") or line.startswith("|---"):
                continue
            parts = [p.strip().replace("`", "") for p in line.split("|")[1:-1]]
            if len(parts) >= 2:
                key, val_rules = parts[0], parts[1]
                if key == "Label Key" or not key:
                    continue
                if "[" in val_rules or "{" in val_rules:
                    rules[key] = {"type": "regex", "pattern": val_rules}
                else:
                    choices = [c.strip() for c in val_rules.split(",") if c.strip()]
                    rules[key] = {"type": "choices", "choices": choices}
    except Exception as e:
        print(f"⚠️ Warning: Could not parse governance rules from cost_tracking.md: {e}", file=sys.stderr)

    return rules, labelable_types


def validate_gcp_label(key, value):
    """Validate key and value against standard GCP label requirements."""
    key_pattern = r"^[a-z][a-z0-9_-]{0,62}$"
    value_pattern = r"^[a-z0-9_-]{0,63}$"

    if not re.match(key_pattern, key):
        return False, f"Key '{key}' is invalid. GCP label keys must be 1-63 chars, start with lowercase, and contain only lowercase letters, numbers, dashes, or underscores."
    if not re.match(value_pattern, value):
        return False, f"Value '{value}' for key '{key}' is invalid. GCP label values must be 0-63 chars and contain only lowercase letters, numbers, dashes, or underscores."
    return True, ""


def validate_inputs(labels_dict, rules, strict=False):
    """Validate all labels against GCP and governance rules, warning or erroring based on strictness."""
    validated = {}
    has_errors = False

    for key, value in labels_dict.items():
        if not value:
            continue

        is_gcp_valid, gcp_err = validate_gcp_label(key, value)
        if not is_gcp_valid:
            print(f"❌ GCP Syntax Error: {gcp_err}", file=sys.stderr)
            has_errors = True
            continue

        if key in rules:
            rule = rules[key]
            if rule["type"] == "choices":
                if value not in rule["choices"]:
                    msg = f"Value '{value}' for '{key}' is not in standard choices: {rule['choices']}"
                    if strict:
                        print(f"❌ Governance Error: {msg}", file=sys.stderr)
                        has_errors = True
                    else:
                        print(f"⚠️ Governance Warning: {msg}", file=sys.stderr)
                        validated[key] = value
                else:
                    validated[key] = value
            elif rule["type"] == "regex":
                if not re.match(rule["pattern"], value):
                    friendly_desc = ""
                    if key == "agent-id":
                        friendly_desc = " (Must be 3-63 characters, containing only lowercase letters, numbers, dashes, or underscores; no uppercase or spaces. Example: 'support-bot')"
                    msg = f"Value '{value}' for '{key}' does not match governance pattern: {rule['pattern']}{friendly_desc}"
                    if strict:
                        print(f"❌ Governance Error: {msg}", file=sys.stderr)
                        has_errors = True
                    else:
                        print(f"⚠️ Governance Warning: {msg}", file=sys.stderr)
                        validated[key] = value
                else:
                    validated[key] = value
        else:
            print(f"ℹ️ Custom Label: Adding extra label '{key}' = '{value}'")
            validated[key] = value

    if has_errors:
        sys.exit(1)

    return validated


def is_resource_compliant(existing_labels, rules, strict):
    """True if a resource already carries valid values for every governed label key."""
    for key, rule in rules.items():
        value = existing_labels.get(key)
        if not value:
            return False
        is_valid, _ = validate_gcp_label(key, value)
        if not is_valid:
            return False
        if rule["type"] == "choices" and value not in rule["choices"] and strict:
            return False
        if rule["type"] == "regex" and not re.match(rule["pattern"], value):
            return False
    return True


def parse_labels_body(body_content):
    """Parse existing labels within a resource block into a dict."""
    pair_pattern = r'("([^"]+)"|([a-zA-Z0-9_-]+))\s*=\s*([^\s}]+)'
    pairs = re.findall(pair_pattern, body_content)
    result = {}
    for match in pairs:
        key = match[1] if match[1] else match[2]
        val = match[3].strip('"').strip("'")
        result[key] = val
    return result


def build_labels_block(existing_labels, labels_to_apply):
    """Construct a standardized, well-aligned labels HCL block."""
    merged = existing_labels.copy()
    merged.update(labels_to_apply)

    sorted_keys = sorted(merged.keys())
    max_len = max(len(k) for k in sorted_keys) if sorted_keys else 0

    lines = ["labels = {"]
    for k in sorted_keys:
        v = merged[k]
        padded_key = f'"{k}"'.ljust(max_len + 2)
        lines.append(f'    {padded_key} = "{v}"')
    lines.append("  }")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# String / comment / heredoc-aware brace matching.
# Replaces naive "count { and }" which breaks on things like:
#   startup_script = <<-EOT
#     echo "{not a terraform brace}"
#   EOT
#   description = "cost center: ${var.env}"
# ---------------------------------------------------------------------------
def find_block_end(content, idx):
    """Given content and the index right after a block's opening '{', return the
    index right after the matching closing '}'."""
    n = len(content)
    depth = 1
    while idx < n and depth > 0:
        ch = content[idx]

        if ch == "#":
            nl = content.find("\n", idx)
            idx = nl if nl != -1 else n
            continue

        if ch == "/" and idx + 1 < n and content[idx + 1] == "/":
            nl = content.find("\n", idx)
            idx = nl if nl != -1 else n
            continue

        if ch == "/" and idx + 1 < n and content[idx + 1] == "*":
            end = content.find("*/", idx + 2)
            idx = end + 2 if end != -1 else n
            continue

        if content[idx:idx + 2] == "<<":
            m = re.match(r"<<-?(\w+)", content[idx:idx + 64])
            if m:
                marker = m.group(1)
                line_end = content.find("\n", idx)
                idx = line_end + 1 if line_end != -1 else n
                end_re = re.compile(r"^[ \t]*" + re.escape(marker) + r"[ \t]*$", re.MULTILINE)
                m2 = end_re.search(content, idx)
                idx = m2.end() + 1 if m2 else n
                continue

        if ch == '"':
            idx += 1
            while idx < n and content[idx] != '"':
                if content[idx] == "\\":
                    idx += 2
                    continue
                if content[idx] == "$" and idx + 1 < n and content[idx + 1] == "{":
                    idx += 2
                    interp_depth = 1
                    while idx < n and interp_depth > 0:
                        if content[idx] == "{":
                            interp_depth += 1
                        elif content[idx] == "}":
                            interp_depth -= 1
                        idx += 1
                    continue
                idx += 1
            idx += 1  # skip closing quote
            continue

        if ch == "{":
            depth += 1
            idx += 1
            continue
        if ch == "}":
            depth -= 1
            idx += 1
            continue

        idx += 1

    return idx


def suggest_labels_with_gemini(resource_block_content, rules_text, project_id, location_id):
    """Call Vertex AI Gemini to suggest labels for one resource. Returns {} on any failure."""
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
    except ImportError:
        print("⚠️ Warning: 'google-cloud-aiplatform' package is not installed. Gemini suggestions disabled.", file=sys.stderr)
        return {}

    try:
        vertexai.init(project=project_id, location=location_id)
        model = GenerativeModel("gemini-3.5-flash")

        prompt = f"""
        You are an expert Cloud FinOps architect.
        We are tagging a GCP Terraform resource block. Here is the HCL definition of the resource:
        ```hcl
        {resource_block_content}
        ```

        Here is our organization's Cost Tracking & FinOps Labeling guidelines:
        ```markdown
        {rules_text}
        ```

        Task:
        1. Read the resource details and the guidelines.
        2. Suggest standard label values for the required keys: 'agent-id', 'business-unit', and 'environment'.
           Prefer standard choices, but you may propose a sensible non-standard value if none fit.
        3. Generate 1 to 3 relevant extra custom labels for this specific resource (e.g. 'tier', 'service-type').

        CRITICAL:
        - All label keys and values MUST match Google Cloud constraints: only lowercase letters, numbers,
          dashes (-), and underscores (_). No uppercase, spaces, or special characters.
        - Keys must start with a lowercase letter. Max length 63 characters.

        Return ONLY a valid JSON object mapping string keys to string values. Do not wrap in markdown code blocks.
        """

        response = model.generate_content(prompt)
        text = response.text.strip()

        if text.startswith("```"):
            text = re.sub(r"^```json\s*", "", text)
            text = re.sub(r"^```\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

        suggested = json.loads(text)
        if not isinstance(suggested, dict):
            print("⚠️ Gemini response was not a JSON object; ignoring.", file=sys.stderr)
            return {}
        return {str(k): str(v) for k, v in suggested.items()}
    except Exception as e:
        print(f"⚠️ Vertex AI error generating label suggestions: {e}", file=sys.stderr)
        return {}


def _ask_gemini_for_single_value(key, gemini_cache, full_block_content, rules_text, project_id, location_id):
    """Fetch (and cache, per resource block) a single suggested value from Gemini."""
    if not (project_id and location_id and full_block_content and rules_text):
        return None
    if "_suggestions" not in gemini_cache:
        print("🤖 Consulting Gemini for a suggested value...")
        gemini_cache["_suggestions"] = suggest_labels_with_gemini(
            full_block_content, rules_text, project_id, location_id
        )
    return gemini_cache["_suggestions"].get(key)


def prompt_labels_interactively(rules, args, defaults_dict, resource_desc,
                                 project_id=None, location_id=None,
                                 full_block_content=None, rules_text=None):
    """Prompt the user for label values. If the user rejects an existing/default
    value, offer to let Gemini suggest a replacement instead of typing one manually."""
    target_labels = {}
    gemini_cache = {}  # caches the single Gemini call for this resource block
    use_gemini = (not args.no_gemini) and bool(project_id) and bool(location_id)
    confirm_prompt = "Use this value anyway? (y/N): "

    def_agent = defaults_dict.get("agent-id") or args.agent_id or rules.get("agent-id", {}).get("default", "support-bot")
    def_bu = defaults_dict.get("business-unit") or args.business_unit or rules.get("business-unit", {}).get("default", "engineering")
    def_env = defaults_dict.get("environment") or args.environment or rules.get("environment", {}).get("default", "staging")

    print(f"\n🏷️  Tagging resource: {resource_desc}")

    # 1. Agent ID
    agent_rule = rules.get("agent-id", {})
    while True:
        val_agent = input(f"Enter Agent ID [default: {def_agent}]: ").strip()
        agent_id = val_agent if val_agent else def_agent

        # Validate GCP constraints first (Hard Rule)
        is_gcp_valid, gcp_err = validate_gcp_label("agent-id", agent_id)
        if not is_gcp_valid:
            print(f"❌ GCP Syntax Error: {gcp_err}")
            continue

        # Validate Governance compliance second (Soft Rule)
        if agent_rule and agent_rule.get("type") == "regex":
            if not re.match(agent_rule["pattern"], agent_id):
                print(f"⚠️ '{agent_id}' is invalid. Agent ID must be 3-63 characters, contain only lowercase letters, numbers, dashes, or underscores, and cannot contain uppercase letters or spaces (e.g. 'support-bot').")
                confirm = input(confirm_prompt).strip().lower()
                if confirm != "y":
                    continue
        
        target_labels["agent-id"] = agent_id
        break

    # 2. Business Unit
    bu_rule = rules.get("business-unit", {})
    bu_choices = bu_rule.get("choices", ["engineering", "finance", "consulting"])
    while True:
        val_bu = input(f"Select Business Unit {bu_choices} [default: {def_bu}]: ").strip()
        bu_val = val_bu if val_bu else def_bu

        # Validate GCP constraints first (Hard Rule)
        is_gcp_valid, gcp_err = validate_gcp_label("business-unit", bu_val)
        if not is_gcp_valid:
            print(f"❌ GCP Syntax Error: {gcp_err}")
            continue

        # Validate Governance compliance second (Soft Rule)
        if bu_val not in bu_choices:
            print(f"⚠️ '{bu_val}' is not one of the standard choices: {bu_choices}")
            confirm = input(confirm_prompt).strip().lower()
            if confirm != "y":
                continue

        target_labels["business-unit"] = bu_val
        break

    # 3. Environment
    env_rule = rules.get("environment", {})
    env_choices = env_rule.get("choices", ["dev", "staging", "uat", "prod"])
    while True:
        val_env = input(f"Select Environment {env_choices} [default: {def_env}]: ").strip()
        env_val = val_env if val_env else def_env

        # Validate GCP constraints first (Hard Rule)
        is_gcp_valid, gcp_err = validate_gcp_label("environment", env_val)
        if not is_gcp_valid:
            print(f"❌ GCP Syntax Error: {gcp_err}")
            continue

        # Validate Governance compliance second (Soft Rule)
        if env_val not in env_choices:
            print(f"⚠️ '{env_val}' is not one of the standard choices: {env_choices}")
            confirm = input(confirm_prompt).strip().lower()
            if confirm != "y":
                continue

        target_labels["environment"] = env_val
        break

    # 4. Optional extra custom labels via Gemini
    extra_labels = {}
    if use_gemini and full_block_content and rules_text:
        use_gemini_opt = input("Add Gemini-suggested extra custom labels too? (y/N) [default: n]: ").strip().lower()
        if use_gemini_opt == "y":
            if "_suggestions" not in gemini_cache:
                print("🤖 Consulting Gemini for custom labels...")
                gemini_cache["_suggestions"] = suggest_labels_with_gemini(
                    full_block_content, rules_text, project_id, location_id
                )
            custom_suggestions = {
                k: v for k, v in gemini_cache["_suggestions"].items()
                if k not in ("agent-id", "business-unit", "environment")
            }
            if custom_suggestions:
                print("\nGemini suggested the following new custom labels:")
                for k, v in sorted(custom_suggestions.items()):
                    apply_this = input(f"  Apply label '{k}' = '{v}'? (Y/n) [default: y]: ").strip().lower()
                    if not apply_this or apply_this == "y":
                        extra_labels[k] = v
            else:
                print("ℹ️ Gemini did not suggest any new custom labels.")

    return {**target_labels, **extra_labels}


def get_static_labels(args):
    """Retrieve labels from command-line arguments."""
    labels = {
        "agent-id": args.agent_id,
        "business-unit": args.business_unit,
        "environment": args.environment,
    }
    if args.extra_labels:
        for item in args.extra_labels.split(","):
            if "=" in item:
                k, v = item.split("=", 1)
                labels[k.strip()] = v.strip()
    return labels


def tag_terraform_file(filepath, rules, labelable_types, args,
                        use_gemini=False, project_id=None, location_id=None):
    """Update or inject labels blocks in supported Google Cloud resource blocks within a file."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original_content = content
    modified = False
    skipped_unsupported = 0
    skipped_compliant = 0

    pattern = r'resource\s+"(google_[^"]+)"\s+"([^"]+)"\s*\{'
    matches = list(re.finditer(pattern, content))

    rules_text = ""
    cost_tracking_path = _governance_paths()
    if os.path.exists(cost_tracking_path):
        with open(cost_tracking_path, "r", encoding="utf-8") as rf:
            rules_text = rf.read()

    for match in reversed(matches):
        resource_type = match.group(1)
        resource_name = match.group(2)

        if resource_type not in labelable_types:
            skipped_unsupported += 1
            continue

        start_pos = match.start()
        block_end_pos = find_block_end(content, match.end())
        full_block_content = content[start_pos:block_end_pos]
        block_body = content[match.end():block_end_pos - 1]

        labels_pattern = r'labels\s*=\s*\{([^}]*)\}'
        labels_match = re.search(labels_pattern, block_body)

        existing_labels = {}
        if labels_match:
            existing_labels = parse_labels_body(labels_match.group(1))

        if not args.force and is_resource_compliant(existing_labels, rules, args.strict):
            skipped_compliant += 1
            continue

        if use_gemini and project_id and location_id:
            print(f"🤖 Consulting Gemini for resource: {resource_type}.{resource_name}...")
            gemini_suggestions = suggest_labels_with_gemini(
                full_block_content, rules_text, project_id, location_id
            )
            if args.interactive:
                defaults = {**existing_labels, **gemini_suggestions}
                labels_to_apply = prompt_labels_interactively(
                    rules, args, defaults, f"{resource_type}.{resource_name}",
                    project_id, location_id, full_block_content, rules_text
                )
            else:
                labels_to_apply = gemini_suggestions or get_static_labels(args)
        else:
            if args.interactive:
                labels_to_apply = prompt_labels_interactively(
                    rules, args, existing_labels, f"{resource_type}.{resource_name}",
                    project_id, location_id, full_block_content, rules_text
                )
            else:
                labels_to_apply = get_static_labels(args)

        validated_labels = validate_inputs(labels_to_apply, rules, strict=args.strict)

        if validated_labels:
            if labels_match:
                new_labels_block = build_labels_block(existing_labels, validated_labels)
                new_block_content = block_body[:labels_match.start()] + new_labels_block + block_body[labels_match.end():]
            else:
                new_labels_block = build_labels_block({}, validated_labels)
                new_block_content = f'\n  {new_labels_block}' + block_body

            content = content[:match.end()] + new_block_content + content[block_end_pos - 1:]
            modified = True

    if skipped_unsupported:
        print(f"ℹ️ {filepath}: skipped {skipped_unsupported} resource(s) of unsupported/unlabelable type.")
    if skipped_compliant:
        print(f"ℹ️ {filepath}: skipped {skipped_compliant} resource(s) already governance-compliant (use --force to re-check).")

    if modified:
        if args.dry_run:
            diff = difflib.unified_diff(
                original_content.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile=f"a/{filepath}", tofile=f"b/{filepath}",
            )
            sys.stdout.writelines(diff)
            print(f"📝 [dry-run] Would tag: {filepath}")
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ Successfully tagged: {filepath}")


def tag_directory(directory, rules, labelable_types, args,
                   use_gemini=False, project_id=None, location_id=None):
    """Recursively tag all .tf files in directory."""
    for root, _, files in os.walk(os.path.abspath(directory)):
        if any((part.startswith('.') and part not in ('.', '..')) or part == 'venv' for part in root.split(os.sep)):
            continue
        for file in files:
            if file.endswith('.tf'):
                filepath = os.path.join(root, file)
                tag_terraform_file(filepath, rules, labelable_types, args, use_gemini, project_id, location_id)


if __name__ == "__main__":
    rules, labelable_types = load_governance_rules()

    parser = argparse.ArgumentParser(description="Auto-tag Terraform files with FinOps labels.")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to scan for Terraform files.")
    parser.add_argument("-i", "--interactive", action="store_true", help="Run interactively prompting for values.")
    parser.add_argument("--strict", action="store_true", help="Strict mode: errors out on governance option mismatches instead of warning.")
    parser.add_argument("--no-gemini", action="store_true", help="Disable Vertex AI Gemini suggestions and use static defaults.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing any files.")
    parser.add_argument("--force", action="store_true", help="Re-check and re-tag resources even if already governance-compliant.")

    def_agent = rules.get("agent-id", {}).get("default", "support-bot")
    def_bu = rules.get("business-unit", {}).get("default", "engineering")
    def_env = rules.get("environment", {}).get("default", "staging")

    parser.add_argument("--agent-id", default=def_agent, help="Value for agent-id label.")
    parser.add_argument("--business-unit", default=def_bu, help="Value for business-unit label.")
    parser.add_argument("--environment", default=def_env, help="Value for environment label.")
    parser.add_argument("--extra-labels", help="Comma-separated custom key=value pairs, e.g., 'team=ai,project=governance'")

    args = parser.parse_args()

    project_id = os.environ.get("PROJECT_ID")
    location_id = os.environ.get("LOCATION_ID")

    use_gemini = not args.no_gemini
    if use_gemini:
        if not project_id or not location_id:
            print("⚠️ Warning: PROJECT_ID and LOCATION_ID env variables are not defined. Falling back to static defaults.", file=sys.stderr)
            use_gemini = False

    tag_directory(args.directory, rules, labelable_types, args, use_gemini, project_id, location_id)
