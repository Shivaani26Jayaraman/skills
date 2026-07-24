#!/usr/bin/env python3
import os
import sys
from google.cloud import aiplatform_v1

PROJECT_ID = "olympus-475310"
LOCATIONS = ["us-central1", "global"]

def discover_and_label_fleet():
    print(f"🔍 Starting discovery of AI Agents in project: {PROJECT_ID}...")
    
    for location in LOCATIONS:
        print(f"\n🌐 Scanning location: {location}...")
        
        # Initialize client for specific location
        api_endpoint = f"{location}-aiplatform.googleapis.com" if location != "global" else "us-central1-aiplatform.googleapis.com"
        client_options = {"api_endpoint": api_endpoint}
        client = aiplatform_v1.ReasoningEngineServiceClient(client_options=client_options)
        
        parent = f"projects/{PROJECT_ID}/locations/{location}"
        
        try:
            # List reasoning engines
            request = aiplatform_v1.ListReasoningEnginesRequest(parent=parent)
            page_result = client.list_reasoning_engines(request=request)
            
            count = 0
            for response in page_result:
                count += 1
                engine_id = response.name.split("/")[-1]
                display_name = response.display_name
                print(f"   * Found Agent: Name='{display_name}', ID='{engine_id}'")
                
                # Derive agent-id label safely from display name
                agent_id = display_name.lower().replace(" ", "-").replace("_", "-")
                
                # Set up the new labels
                labels = {
                    "agent-id": agent_id,
                    "business-unit": "pso",
                    "environment": "staging"
                }
                
                print(f"     -> Applying labels: {labels}")
                
                # Prepare update request
                reasoning_engine = aiplatform_v1.ReasoningEngine(
                    name=response.name,
                    labels=labels
                )
                update_mask = {"paths": ["labels"]}
                
                # Apply update
                update_request = aiplatform_v1.UpdateReasoningEngineRequest(
                    reasoning_engine=reasoning_engine,
                    update_mask=update_mask
                )
                operation = client.update_reasoning_engine(request=update_request)
                print(f"     ✅ Labels update initiated for {display_name}.")
                
            if count == 0:
                print(f"   (No agents found in {location})")
            else:
                print(f"   ✅ Finished processing {count} agents in {location}.")
                
        except Exception as e:
            print(f"   ⚠️ Error scanning {location}: {e}")

if __name__ == "__main__":
    discover_and_label_fleet()
