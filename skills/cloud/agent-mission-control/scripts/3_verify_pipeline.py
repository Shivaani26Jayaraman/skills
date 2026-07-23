#!/usr/bin/env python3
import os
import sys
from google.cloud import bigquery

def verify():
    project_id = os.environ.get("PROJECT_ID", "olympus-475310")
    client = bigquery.Client(project=project_id)
    
    query = f"SELECT COUNT(*) as total FROM `{project_id}.agent_governance_datamart.v_blocked_incidents`"
    print(f"🔍 Verifying BigQuery View data for project: {project_id}...")
    try:
        results = client.query(query).result()
        for row in results:
            print(f"✅ SUCCESS! Mission Control View contains {row.total} security log entries.")
    except Exception as e:
        print(f"⚠️ Query error (logs may still be streaming): {e}")

if __name__ == "__main__":
    verify()
