import os
import json
from google.cloud import bigquery

client = bigquery.Client()

# Load compliance labels from job_config.json in the same directory
config_path = os.path.join(os.path.dirname(__file__), "job_config.json")
with open(config_path, "r") as f:
    config_data = json.load(f)

job_config = bigquery.QueryJobConfig(labels=config_data.get("labels", {}))

# Run query with configured labels
query_job = client.query("SELECT 1", job_config=job_config)
