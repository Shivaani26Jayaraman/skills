#!/usr/bin/env python3
"""
finops_tagger.py — Auto-tag GCP Terraform resources with FinOps cost-tracking labels.

Key production hardening over the original version:
  1. Supported services for labels: only tags resource types that actually support a
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
import ast

# ---------------------------------------------------------------------------
# Default list of supported services for labels.
# This can be extended (not replaced) via a "## Supported services for labels"
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
    """Load labeling rules AND the supported services for labels from cost_tracking.md."""
    cost_tracking_path = _governance_paths()

    rules = {}
    labelable_types = set(DEFAULT_LABELABLE_TYPES)

    if not os.path.exists(cost_tracking_path):
        return rules, labelable_types

    try:
        with open(cost_tracking_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        in_types_section = False
        headers = []
        rules_idx = 1 # default fallback

        for raw_line in lines:
            line = raw_line.strip()

            if line.startswith("#"):
                in_types_section = line.lstrip("#").strip().lower() in ("labelable resource types", "supported services for labels")
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
            if not parts or not parts[0]:
                continue

            if parts[0].lower() in ["label key", "key"]:
                headers = [p.lower() for p in parts]
                for idx, h in enumerate(headers):
                    if "rule" in h or "value" in h or "options" in h:
                        rules_idx = idx
                continue

            key = parts[0].replace("*", "").strip()
            if key == "Label Key" or not key:
                continue

            if len(parts) > rules_idx:
                val_rules = parts[rules_idx]
                val_rules = re.sub(r'(?i)^regex:\s*', '', val_rules).strip()
                if "[" in val_rules or "{" in val_rules or "^" in val_rules:
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

    for req_key in REQUIRED_LABEL_KEYS:
        if req_key not in labels_dict or not labels_dict[req_key]:
            print(f"❌ Governance Error: Missing mandatory label key '{req_key}'", file=sys.stderr)
            has_errors = True

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
        if key not in REQUIRED_LABEL_KEYS:
            value = existing_labels.get(key)
            if not value:
                continue
        else:
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


def build_labels_block(existing_labels, labels_to_apply, block_name="labels"):
    """Construct a standardized, well-aligned labels HCL block."""
    merged = existing_labels.copy()
    merged.update(labels_to_apply)

    sorted_keys = sorted(merged.keys())
    max_len = max(len(k) for k in sorted_keys) if sorted_keys else 0

    lines = [f"{block_name} = {{"]
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
        3. Suggest optional label values for 'cost-centre' and 'team' if applicable.
        4. Generate 1 to 3 relevant extra custom labels for this specific resource (e.g. 'tier', 'service-type').

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
    def_cc = defaults_dict.get("cost-centre") or args.cost_centre or rules.get("cost-centre", {}).get("default", "cc-1001")

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

    # 4. Cost Centre (Optional)
    cc_rule = rules.get("cost-centre", {})
    def_cc_val = defaults_dict.get("cost-centre") or args.cost_centre
    if not def_cc_val and use_gemini:
        def_cc_val = _ask_gemini_for_single_value("cost-centre", gemini_cache, full_block_content, rules_text, project_id, location_id)

    while True:
        val_cc = input(f"Enter Cost Centre (optional) [default: {def_cc_val or 'skip'}]: ").strip()
        cc_val = val_cc if val_cc else def_cc_val
        if not cc_val or cc_val.lower() == 'skip':
            break

        # Validate GCP constraints first (Hard Rule)
        is_gcp_valid, gcp_err = validate_gcp_label("cost-centre", cc_val)
        if not is_gcp_valid:
            print(f"❌ GCP Syntax Error: {gcp_err}")
            continue

        # Validate Governance compliance second (Soft Rule)
        if cc_rule and cc_rule.get("type") == "regex":
            if not re.match(cc_rule["pattern"], cc_val):
                print(f"⚠️ '{cc_val}' is invalid. Cost center does not match compliance rules.")
                confirm = input(confirm_prompt).strip().lower()
                if confirm != "y":
                    continue

        target_labels["cost-centre"] = cc_val
        break

    # 5. Team (Optional)
    team_rule = rules.get("team", {})
    def_team_val = defaults_dict.get("team") or (args.team if hasattr(args, "team") else None)
    if not def_team_val and use_gemini:
        def_team_val = _ask_gemini_for_single_value("team", gemini_cache, full_block_content, rules_text, project_id, location_id)

    while True:
        val_team = input(f"Enter Team (optional) [default: {def_team_val or 'skip'}]: ").strip()
        team_val = val_team if val_team else def_team_val
        if not team_val or team_val.lower() == 'skip':
            break

        # Validate GCP constraints first (Hard Rule)
        is_gcp_valid, gcp_err = validate_gcp_label("team", team_val)
        if not is_gcp_valid:
            print(f"❌ GCP Syntax Error: {gcp_err}")
            continue

        # Validate Governance compliance second (Soft Rule)
        if team_rule and team_rule.get("type") == "regex":
            if not re.match(team_rule["pattern"], team_val):
                print(f"⚠️ '{team_val}' is invalid. Team does not match compliance rules.")
                confirm = input(confirm_prompt).strip().lower()
                if confirm != "y":
                    continue

        target_labels["team"] = team_val
        break

    # 6. Optional extra custom labels via Gemini
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
                if k not in REQUIRED_LABEL_KEYS and k not in ("cost-centre", "team")
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


class QueryVisitor(ast.NodeVisitor):
    def __init__(self):
        self.query_calls = []

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'query':
            self.query_calls.append(node)
        self.generic_visit(node)


def suggest_python_refactoring_with_gemini(file_content, project_id, location_id):
    """Call Vertex AI Gemini to refactor python code to load job_config.json for BigQuery QueryJobConfig."""
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
    except ImportError:
        print("⚠️ Warning: 'google-cloud-aiplatform' package is not installed. Gemini suggestions disabled.", file=sys.stderr)
        return None

    try:
        vertexai.init(project=project_id, location=location_id)
        model = GenerativeModel("gemini-3.5-flash")

        prompt = f"""
        You are an expert Python and Cloud FinOps developer.
        We want to ensure that all Google Cloud BigQuery client queries in this Python file are executed with proper compliance labels loaded from a `job_config.json` file.
        
        Here is the original Python code:
        ```python
        {file_content}
        ```

        Task:
        1. Identify all calls to bigquery Client `.query()` method.
        2. Ensure they pass a `job_config` parameter using `google.cloud.bigquery.QueryJobConfig`.
        3. Make sure the labels for the `QueryJobConfig` are loaded from a `job_config.json` file located in the same directory as the Python file.
        4. Use path resolution to load `job_config.json` safely:
           ```python
           import os
           import json
           config_path = os.path.join(os.path.dirname(__file__), "job_config.json")
           with open(config_path, "r") as f:
               config_data = json.load(f)
           job_config = bigquery.QueryJobConfig(labels=config_data.get("labels", {{}}))
           ```
        5. Define the `QueryJobConfig` loading block right before the query is run, or reuse it if multiple query calls exist.
        6. Make sure any necessary imports (`import os`, `import json`, `from google.cloud import bigquery`) are added or preserved.
        7. Do not modify other logic, comments, or variables in the code.
        
        Return ONLY the modified Python code, with no extra text or markdown wrapping blocks.
        """

        response = model.generate_content(prompt)
        text = response.text.strip()

        if text.startswith("```"):
            text = re.sub(r"^```python\s*", "", text)
            text = re.sub(r"^```\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

        return text
    except Exception as e:
        print(f"⚠️ Vertex AI error refactoring python code: {e}", file=sys.stderr)
        return None


def tag_python_file(filepath, rules, args, use_gemini=False, project_id=None, location_id=None):
    """Scan python files for untagged BigQuery queries, output job_config.json, and suggest config updates."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except Exception as e:
        print(f"⚠️ Warning: Could not parse python file {filepath}: {e}", file=sys.stderr)
        return

    visitor = QueryVisitor()
    visitor.visit(tree)

    if not visitor.query_calls:
        return

    # Determine paths and load existing config if it exists
    dirpath = os.path.dirname(filepath)
    json_path = os.path.join(dirpath, "job_config.json")
    existing_labels = {}
    json_exists = os.path.exists(json_path)
    if json_exists:
        try:
            with open(json_path, "r", encoding="utf-8") as jf:
                existing_config = json.load(jf)
                existing_labels = existing_config.get("labels", {})
        except Exception:
            pass

    # Check if any AST calls are missing job_config
    has_non_compliant_calls = False
    for call in visitor.query_calls:
        has_job_config = False
        for kw in call.keywords:
            if kw.arg == 'job_config':
                has_job_config = True
                break
        if not has_job_config:
            has_non_compliant_calls = True
            break

    # The config file itself must be compliant (contain required labels)
    is_config_compliant = json_exists and is_resource_compliant(existing_labels, rules, args.strict)

    if not args.force and not has_non_compliant_calls and is_config_compliant:
        return

    print(f"⚠️ Governance Warning: python file '{filepath}' has untagged or non-compliant BigQuery queries.")

    if args.strict:
        print(f"❌ Governance Error: python file '{filepath}' has untagged or non-compliant BigQuery queries.", file=sys.stderr)
        sys.exit(1)

    # Prompt or gather static labels
    if args.interactive:
        labels_to_apply = prompt_labels_interactively(
            rules, args, existing_labels, f"BigQuery queries in {filepath}",
            project_id, location_id, content, ""
        )
    else:
        labels_to_apply = get_static_labels(args)

    validated_labels = validate_inputs(labels_to_apply, rules, strict=args.strict)
    if not validated_labels:
        return

    # Write the job_config.json file
    merged_labels = {**existing_labels, **validated_labels}
    new_config = {"labels": merged_labels}

    if args.dry_run:
        print(f"📝 [dry-run] Would write job_config.json to: {json_path}")
        print(json.dumps(new_config, indent=2))
    else:
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(new_config, jf, indent=2)
        print(f"✅ Successfully wrote job_config.json: {json_path}")

    # Consult Gemini to refactor the python file to load job_config.json
    if use_gemini and project_id and location_id:
        print(f"🤖 Consulting Gemini to refactor {filepath}...")
        refactored = suggest_python_refactoring_with_gemini(content, project_id, location_id)
        if refactored and refactored != content:
            if args.dry_run:
                diff = difflib.unified_diff(
                    content.splitlines(keepends=True),
                    refactored.splitlines(keepends=True),
                    fromfile=f"a/{filepath}", tofile=f"b/{filepath}",
                )
                sys.stdout.writelines(diff)
                print(f"📝 [dry-run] Would tag python queries: {filepath}")
            else:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(refactored)
                print(f"✅ Successfully tagged python queries: {filepath}")
    else:
        print(f"ℹ️ Auto-refactoring Python files requires Gemini. Please set PROJECT_ID and LOCATION_ID.")


def get_static_labels(args):
    """Retrieve labels from command-line arguments."""
    labels = {
        "agent-id": args.agent_id,
        "business-unit": args.business_unit,
        "environment": args.environment,
    }
    if getattr(args, "cost_centre", None):
        labels["cost-centre"] = args.cost_centre
    if getattr(args, "team", None):
        labels["team"] = args.team
    if args.extra_labels:
        for item in args.extra_labels.split(","):
            if "=" in item:
                k, v = item.split("=", 1)
                labels[k.strip()] = v.strip()
    return labels


def tag_terraform_file(filepath, rules, labelable_types, args,
                        use_gemini=False, project_id=None, location_id=None):
    """Update or inject labels blocks in supported Google Cloud resource and provider blocks within a file."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original_content = content
    modified = False
    skipped_unsupported = 0
    skipped_compliant = 0

    # Matches:
    #   resource "google_compute_instance" "name" {
    #   provider "google" {
    pattern = r'(resource\s+"(google_[^"]+)"\s+"([^"]+)"|provider\s+"(google)")\s*\{'
    matches = list(re.finditer(pattern, content))

    rules_text = ""
    cost_tracking_path = _governance_paths()
    if os.path.exists(cost_tracking_path):
        with open(cost_tracking_path, "r", encoding="utf-8") as rf:
            rules_text = rf.read()

    for match in reversed(matches):
        is_provider = (match.group(4) == "google")

        if is_provider:
            block_desc = "provider.google"
            labels_block_name = "default_labels"
        else:
            resource_type = match.group(2)
            resource_name = match.group(3)
            block_desc = f"{resource_type}.{resource_name}"
            labels_block_name = "labels"

            if resource_type not in labelable_types:
                skipped_unsupported += 1
                continue

        start_pos = match.start()
        block_end_pos = find_block_end(content, match.end())
        full_block_content = content[start_pos:block_end_pos]
        block_body = content[match.end():block_end_pos - 1]

        labels_pattern = rf'{labels_block_name}\s*=\s*\{{([^}}]*)\}}'
        labels_match = re.search(labels_pattern, block_body)

        existing_labels = {}
        if labels_match:
            existing_labels = parse_labels_body(labels_match.group(1))

        if not args.force and is_resource_compliant(existing_labels, rules, args.strict):
            skipped_compliant += 1
            continue

        if use_gemini and project_id and location_id:
            print(f"🤖 Consulting Gemini for {block_desc}...")
            gemini_suggestions = suggest_labels_with_gemini(
                full_block_content, rules_text, project_id, location_id
            )
            if args.interactive:
                defaults = {**existing_labels, **gemini_suggestions}
                labels_to_apply = prompt_labels_interactively(
                    rules, args, defaults, block_desc,
                    project_id, location_id, full_block_content, rules_text
                )
            else:
                labels_to_apply = gemini_suggestions or get_static_labels(args)
        else:
            if args.interactive:
                labels_to_apply = prompt_labels_interactively(
                    rules, args, existing_labels, block_desc,
                    project_id, location_id, full_block_content, rules_text
                )
            else:
                labels_to_apply = get_static_labels(args)

        validated_labels = validate_inputs(labels_to_apply, rules, strict=args.strict)

        if validated_labels:
            if labels_match:
                new_labels_block = build_labels_block(existing_labels, validated_labels, block_name=labels_block_name)
                new_block_content = block_body[:labels_match.start()] + new_labels_block + block_body[labels_match.end():]
            else:
                new_labels_block = build_labels_block({}, validated_labels, block_name=labels_block_name)
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
    """Recursively tag all .tf and .py files in directory or a single file."""
    target_path = os.path.abspath(directory)
    if os.path.isfile(target_path):
        if target_path.endswith('.tf'):
            tag_terraform_file(target_path, rules, labelable_types, args, use_gemini, project_id, location_id)
        elif target_path.endswith('.py'):
            tag_python_file(target_path, rules, args, use_gemini, project_id, location_id)
        return

    for root, _, files in os.walk(target_path):
        if any((part.startswith('.') and part not in ('.', '..')) or part == 'venv' for part in root.split(os.sep)):
            continue
        for file in files:
            filepath = os.path.join(root, file)
            if file.endswith('.tf'):
                tag_terraform_file(filepath, rules, labelable_types, args, use_gemini, project_id, location_id)
            elif file.endswith('.py'):
                tag_python_file(filepath, rules, args, use_gemini, project_id, location_id)


def is_terraform_file_compliant(filepath, rules, labelable_types, strict):
    """Returns True if all labelable resources in the file are compliant, otherwise False."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r'(resource\s+"(google_[^"]+)"\s+"([^"]+)"|provider\s+"(google)")\s*\{'
    matches = list(re.finditer(pattern, content))

    for match in matches:
        is_provider = (match.group(4) == "google")
        if is_provider:
            labels_block_name = "default_labels"
        else:
            resource_type = match.group(2)
            if resource_type not in labelable_types:
                continue
            labels_block_name = "labels"

        block_end_pos = find_block_end(content, match.end())
        block_body = content[match.end():block_end_pos - 1]

        labels_pattern = rf'{labels_block_name}\s*=\s*\{{([^}}]*)\}}'
        labels_match = re.search(labels_pattern, block_body)

        existing_labels = {}
        if labels_match:
            existing_labels = parse_labels_body(labels_match.group(1))

        if not is_resource_compliant(existing_labels, rules, strict):
            return False

    return True


def is_python_file_compliant(filepath, rules, strict):
    """Returns True if all BigQuery queries in the file are compliant, otherwise False."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except Exception:
        return True

    visitor = QueryVisitor()
    visitor.visit(tree)

    if not visitor.query_calls:
        return True

    dirpath = os.path.dirname(filepath)
    json_path = os.path.join(dirpath, "job_config.json")
    existing_labels = {}
    json_exists = os.path.exists(json_path)
    if json_exists:
        try:
            with open(json_path, "r", encoding="utf-8") as jf:
                existing_config = json.load(jf)
                existing_labels = existing_config.get("labels", {})
        except Exception:
            pass

    has_non_compliant_calls = False
    for call in visitor.query_calls:
        has_job_config = False
        for kw in call.keywords:
            if kw.arg == 'job_config':
                has_job_config = True
                break
        if not has_job_config:
            has_non_compliant_calls = True
            break

    is_config_compliant = json_exists and is_resource_compliant(existing_labels, rules, strict)

    return not has_non_compliant_calls and is_config_compliant


def check_directory_compliance(directory, rules, labelable_types, strict):
    """Scan directory or file and print any non-compliant files. Returns True if all compliant, else False."""
    target_path = os.path.abspath(directory)
    files_to_check = []

    if os.path.isfile(target_path):
        if target_path.endswith('.tf') or target_path.endswith('.py'):
            files_to_check.append(target_path)
    else:
        for root, _, files in os.walk(target_path):
            if any((part.startswith('.') and part not in ('.', '..')) or part == 'venv' for part in root.split(os.sep)):
                continue
            for file in files:
                if file.endswith('.tf') or file.endswith('.py'):
                    files_to_check.append(os.path.join(root, file))

    non_compliant_files = []
    for filepath in files_to_check:
        if filepath.endswith('.tf'):
            compliant = is_terraform_file_compliant(filepath, rules, labelable_types, strict)
        else:
            compliant = is_python_file_compliant(filepath, rules, strict)

        if not compliant:
            non_compliant_files.append(filepath)
            print(f"❌ Non-compliant: {filepath}")

    return len(non_compliant_files) == 0


if __name__ == "__main__":
    rules, labelable_types = load_governance_rules()

    parser = argparse.ArgumentParser(description="Auto-tag Terraform files with FinOps labels.")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to scan for Terraform files.")
    parser.add_argument("-i", "--interactive", action="store_true", help="Run interactively prompting for values.")
    parser.add_argument("--strict", action="store_true", help="Strict mode: errors out on governance option mismatches instead of warning.")
    parser.add_argument("--no-gemini", action="store_true", help="Disable Vertex AI Gemini suggestions and use static defaults.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing any files.")
    parser.add_argument("--force", action="store_true", help="Re-check and re-tag resources even if already governance-compliant.")
    parser.add_argument("--check", action="store_true", help="Scan and list non-compliant files, then exit.")

    def_agent = rules.get("agent-id", {}).get("default", "support-bot")
    def_bu = rules.get("business-unit", {}).get("default", "engineering")
    def_env = rules.get("environment", {}).get("default", "stage")

    parser.add_argument("--agent-id", default=def_agent, help="Value for agent-id label.")
    parser.add_argument("--business-unit", default=def_bu, help="Value for business-unit label.")
    parser.add_argument("--environment", default=def_env, help="Value for environment label.")
    parser.add_argument("--cost-centre", default=None, help="Value for cost-centre label (optional).")
    parser.add_argument("--team", default=None, help="Value for team label (optional).")
    parser.add_argument("--extra-labels", help="Comma-separated custom key=value pairs, e.g., 'project=governance'")

    args = parser.parse_args()

    if args.check:
        all_compliant = check_directory_compliance(args.directory, rules, labelable_types, args.strict)
        sys.exit(0 if all_compliant else 1)

    project_id = os.environ.get("PROJECT_ID")
    location_id = os.environ.get("LOCATION_ID")

    use_gemini = not args.no_gemini
    if use_gemini:
        if not project_id or not location_id:
            print("⚠️ Warning: PROJECT_ID and LOCATION_ID env variables are not defined. Falling back to static defaults.", file=sys.stderr)
            use_gemini = False

    tag_directory(args.directory, rules, labelable_types, args, use_gemini, project_id, location_id)
