-- Create Mock GCP Billing Export Table in us-east1
CREATE OR REPLACE TABLE `agent_governance_datamart_useast1.gcp_billing_export_mock` (
  project STRUCT<id STRING, name STRING>,
  labels ARRAY<STRUCT<key STRING, value STRING>>,
  service STRUCT<description STRING>,
  sku STRUCT<description STRING>,
  usage_start_time TIMESTAMP,
  cost FLOAT64,
  currency STRING
);

-- Populate with mock cost records for our discovered agents
INSERT INTO `agent_governance_datamart_useast1.gcp_billing_export_mock` (project, labels, service, sku, usage_start_time, cost, currency)
VALUES
  -- Costs for retail-agent
  (STRUCT('olympus-475310', 'olympus'), 
   [STRUCT('agent-id', 'retail-agent'), STRUCT('business-unit', 'pso'), STRUCT('environment', 'staging')],
   STRUCT('Vertex AI'), STRUCT('Reasoning Engine Execution'), CURRENT_TIMESTAMP(), 15.45, 'USD'),
  (STRUCT('olympus-475310', 'olympus'), 
   [STRUCT('agent-id', 'retail-agent'), STRUCT('business-unit', 'pso'), STRUCT('environment', 'staging')],
   STRUCT('Cloud Run'), STRUCT('CPU Allocation Time'), CURRENT_TIMESTAMP(), 8.20, 'USD'),

  -- Costs for retail-agent-v2
  (STRUCT('olympus-475310', 'olympus'), 
   [STRUCT('agent-id', 'retail-agent-v2'), STRUCT('business-unit', 'pso'), STRUCT('environment', 'staging')],
   STRUCT('Vertex AI'), STRUCT('Reasoning Engine Execution'), CURRENT_TIMESTAMP(), 22.10, 'USD'),
  (STRUCT('olympus-475310', 'olympus'), 
   [STRUCT('agent-id', 'retail-agent-v2'), STRUCT('business-unit', 'pso'), STRUCT('environment', 'staging')],
   STRUCT('Cloud Run'), STRUCT('CPU Allocation Time'), CURRENT_TIMESTAMP(), 12.05, 'USD'),

  -- Costs for retail-agent-v3
  (STRUCT('olympus-475310', 'olympus'), 
   [STRUCT('agent-id', 'retail-agent-v3'), STRUCT('business-unit', 'pso'), STRUCT('environment', 'staging')],
   STRUCT('Vertex AI'), STRUCT('Reasoning Engine Execution'), CURRENT_TIMESTAMP(), 5.12, 'USD'),

  -- Costs for general-support-assistant
  (STRUCT('olympus-475310', 'olympus'), 
   [STRUCT('agent-id', 'general-support-assistant'), STRUCT('business-unit', 'pso'), STRUCT('environment', 'staging')],
   STRUCT('Vertex AI'), STRUCT('Reasoning Engine Execution'), CURRENT_TIMESTAMP(), 45.30, 'USD'),
  (STRUCT('olympus-475310', 'olympus'), 
   [STRUCT('agent-id', 'general-support-assistant'), STRUCT('business-unit', 'pso'), STRUCT('environment', 'staging')],
   STRUCT('Cloud Run'), STRUCT('CPU Allocation Time'), CURRENT_TIMESTAMP(), 25.15, 'USD');
