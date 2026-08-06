-- Create Agent Registry Snapshot Table in us-east1
CREATE OR REPLACE TABLE `agent_governance_datamart_useast1.agent_registry_snapshot` (
  agent_id STRING,
  name STRING,
  owner STRING,
  business_unit STRING,
  data_classification STRING,
  location STRING,
  agent_type STRING
);

-- Populate with discovered agents from us-central1
INSERT INTO `agent_governance_datamart_useast1.agent_registry_snapshot` (agent_id, name, owner, business_unit, data_classification, location, agent_type)
VALUES
  ('retail-agent', 'retail-agent', 'Retail Platform Team', 'pso', 'Confidential', 'us-central1', 'Reasoning Engine'),
  ('retail-agent-v2', 'retail-agent-v2', 'Retail Platform Team', 'pso', 'Confidential', 'us-central1', 'Reasoning Engine'),
  ('retail-agent-v3', 'retail-agent-v3', 'Retail Platform Team', 'pso', 'Confidential', 'us-central1', 'Reasoning Engine'),
  ('retail-agent-v4', 'retail-agent-v4', 'Retail Platform Team', 'pso', 'Confidential', 'us-central1', 'Reasoning Engine'),
  ('general-support-assistant', 'General Support Assistant', 'Customer Operations', 'pso', 'Restricted', 'us-central1', 'Reasoning Engine');
