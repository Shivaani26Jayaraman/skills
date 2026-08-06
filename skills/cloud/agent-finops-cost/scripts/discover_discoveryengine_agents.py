#!/usr/bin/env python3
import os
import sys
from google.cloud import bigquery

try:
    from google.cloud import discoveryengine_v1
except ImportError:
    print("google-cloud-discoveryengine is not installed. Installing it now...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "google-cloud-discoveryengine", "--index-url", "https://pypi.org/simple/"])
    from google.cloud import discoveryengine_v1
PROJECT_ID = "olympus-475310"
LOCATIONS = ["global", "us"]
DATASET_ID = "agent_governance_datamart_useast1"
TABLE_ID = "agent_registry_snapshot"

def discover_discoveryengine_agents():
    print(f"🔍 Starting discovery of Vertex AI Agent Builder (Discovery Engine) engines in project: {PROJECT_ID}...")
    
    bq_client = bigquery.Client(project=PROJECT_ID)
    table_ref = bq_client.dataset(DATASET_ID).table(TABLE_ID)
    
    new_agents = []
    
    for location in LOCATIONS:
        print(f"\n🌐 Scanning location: {location}...")
        try:
            client = discoveryengine_v1.EngineServiceClient()
            # Standard parent path for Discovery Engine collections
            parent = f"projects/{PROJECT_ID}/locations/{location}/collections/default_collection"
            
            request = discoveryengine_v1.ListEnginesRequest(parent=parent)
            page_result = client.list_engines(request=request)
            
            count = 0
            for engine in page_result:
                count += 1
                engine_id = engine.name.split("/")[-1]
                display_name = engine.display_name
                print(f"   * Found Agent Builder Engine: Name='{display_name}', ID='{engine_id}'")
                
                row = {
                    "agent_id": engine_id,
                    "name": display_name,
                    "owner": "Agent Builder Managed",
                    "business_unit": "pso",
                    "data_classification": "Confidential",
                    "location": location,
                    "agent_type": "Agent Builder Engine"
                }
                new_agents.append(row)
                
            print(f"   ✅ Finished processing {count} engines in {location}.")
            
        except Exception as e:
            print(f"   ⚠️ Error scanning {location}: {e}")
            
    if new_agents:
        print(f"\n📥 Appending {len(new_agents)} discovered agents to {DATASET_ID}.{TABLE_ID}...")
        errors = bq_client.insert_rows_json(table_ref, new_agents)
        if not errors:
            print("✅ Successfully appended agents to the BigQuery registry snapshot!")
        else:
            print(f"❌ Error inserting rows to BigQuery: {errors}")
    else:
        print("\nℹ️ No new Agent Builder engines discovered.")

if __name__ == "__main__":
    discover_discoveryengine_agents()
