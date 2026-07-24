#!/usr/bin/env python3
"""
Python script to render Google Cloud Monitoring Dashboard from a Jinja2 template.
"""

import os
import sys
import argparse
import json
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("Error: jinja2 package is required. Install it using 'pip install jinja2'")
    sys.exit(1)

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def load_config(config_path: Path) -> dict:
    """Loads configuration variables from a JSON or YAML file."""
    if not config_path.exists():
        print(f"Error: Configuration file not found at {config_path}")
        sys.exit(1)

    suffix = config_path.suffix.lower()
    content = config_path.read_text(encoding="utf-8")

    if suffix in (".yaml", ".yml"):
        if not HAS_YAML:
            print("Error: pyyaml package is required to load YAML configs. Install it using 'pip install pyyaml'")
            sys.exit(1)
        return yaml.safe_load(content) or {}
    elif suffix == ".json":
        return json.loads(content)
    else:
        print(f"Error: Unsupported configuration file format: {suffix}. Use .json, .yaml, or .yml.")
        sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Render a parameterized Google Cloud Monitoring dashboard JSON from a Jinja2 template."
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file (JSON or YAML)."
    )
    parser.add_argument(
        "--template",
        type=str,
        default=str(Path(__file__).parent.parent / "references" / "dashboard.json.j2"),
        help="Path to the Jinja2 template file."
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(Path(__file__).parent.parent / "rendered_dashboard.json"),
        help="Path to save the rendered dashboard JSON."
    )
    parser.add_argument(
        "--project-id",
        type=str,
        help="GCP Project ID."
    )
    parser.add_argument(
        "--reasoning-engine-id",
        type=str,
        help="Vertex AI Reasoning Engine ID."
    )
    parser.add_argument(
        "--model-id",
        type=str,
        help="Model ID (e.g. gemini-3.5-flash)."
    )
    parser.add_argument(
        "--dashboard-display-name",
        type=str,
        help="Display name of the dashboard."
    )
    parser.add_argument(
        "--error-log-metric-name",
        type=str,
        help="Name of custom error log-based metric."
    )

    return parser.parse_args()


def main():
    args = parse_args()
    config = {}

    # 1. Load from config file if provided
    if args.config:
        config = load_config(Path(args.config))

    # 2. Command line arguments override file configs
    cli_vars = {
        "project_id": args.project_id,
        "reasoning_engine_id": args.reasoning_engine_id,
        "model_id": args.model_id,
        "dashboard_display_name": args.dashboard_display_name,
        "error_log_metric_name": args.error_log_metric_name,
    }

    for key, val in cli_vars.items():
        if val is not None:
            config[key] = val

    # 3. Validation: Verify all required parameters exist
    required_keys = [
        "project_id",
        "reasoning_engine_id",
        "model_id",
        "dashboard_display_name",
    ]
    missing = [k for k in required_keys if k not in config]
    if missing:
        print(f"Error: Missing required configuration variables: {', '.join(missing)}")
        print("Please provide them in a config file or as command-line arguments.")
        sys.exit(1)

    # Auto-derive error log metric name if not specified
    if "error_log_metric_name" not in config or not config["error_log_metric_name"]:
        config["error_log_metric_name"] = f"agent_engine_error_log_{config['reasoning_engine_id']}"


    template_path = Path(args.template)
    if not template_path.exists():
        print(f"Error: Template file not found at {template_path}")
        sys.exit(1)

    # 4. Render using Jinja2
    env = Environment(loader=FileSystemLoader(str(template_path.parent)))
    template = env.get_template(template_path.name)
    rendered_json = template.render(config)

    # 5. Optional verification: attempt to parse rendered string as JSON to ensure valid syntax
    try:
        json.loads(rendered_json)
    except json.JSONDecodeError as err:
        print("Warning: Rendered output is not valid JSON! Error:")
        print(err)

    # 6. Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered_json, encoding="utf-8")
    print(f"Successfully rendered dashboard configuration to {output_path}")


if __name__ == "__main__":
    main()
