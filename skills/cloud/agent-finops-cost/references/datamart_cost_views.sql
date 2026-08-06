-- SQL Views for Datamart Cost Aggregation inside us-east1

-- View 1: Active Infrastructure Costs per Agent (Grouped by Resource Labels)
CREATE OR REPLACE VIEW `agent_governance_datamart_useast1.v_agent_infra_costs` AS
SELECT
  project.id AS project_id,
  (SELECT value FROM UNNEST(labels) WHERE key = 'agent-id') AS agent_id,
  (SELECT value FROM UNNEST(labels) WHERE key = 'business-unit') AS business_unit,
  (SELECT value FROM UNNEST(labels) WHERE key = 'environment') AS environment,
  service.description AS service_description,
  sku.description AS sku_description,
  usage_start_time,
  cost,
  currency
FROM
  `olympus-475310.agent_governance_datamart_useast1.gcp_billing_export_mock`
WHERE
  EXISTS(SELECT 1 FROM UNNEST(labels) WHERE key = 'agent-id');


-- View 2: Model Token Usage Costs per Agent (Estimated based on Vertex LLM usage log statistics)
CREATE OR REPLACE VIEW `agent_governance_datamart_useast1.v_agent_token_costs` AS
SELECT
  timestamp AS usage_time,
  labels.gen_ai_agent_name AS agent_id,
  'gemini-3.5-flash' AS model_id,
  CAST(labels.gen_ai_usage_input_tokens AS INT64) AS prompt_tokens,
  CAST(labels.gen_ai_usage_output_tokens AS INT64) AS completion_tokens,
  -- Calculate Token cost (e.g. prompt token cost: $0.075 / 1M, completion token cost: $0.30 / 1M)
  (CAST(labels.gen_ai_usage_input_tokens AS INT64) * 0.075 / 1000000) +
  (CAST(labels.gen_ai_usage_output_tokens AS INT64) * 0.30 / 1000000) AS estimated_token_cost
FROM
  `olympus-475310.retail_agent_telemetry.gen_ai_client_inference_operation_details`
WHERE
  labels.gen_ai_usage_input_tokens IS NOT NULL;


-- View 3: Master Cost Governance Hub (Joins Registry, Infrastructure, and Token usage)
CREATE OR REPLACE VIEW `agent_governance_datamart_useast1.v_master_cost_governance` AS
SELECT
  reg.agent_id,
  reg.name AS agent_name,
  reg.owner AS agent_owner,
  reg.business_unit,
  reg.data_classification,
  reg.location,
  COALESCE(infra.total_infra_cost, 0.0) AS total_infra_cost,
  COALESCE(token.total_token_cost, 0.0) AS total_token_cost,
  (COALESCE(infra.total_infra_cost, 0.0) + COALESCE(token.total_token_cost, 0.0)) AS total_cost
FROM
  `agent_governance_datamart_useast1.agent_registry_snapshot` reg
LEFT JOIN (
  SELECT
    agent_id,
    SUM(cost) AS total_infra_cost
  FROM
    `agent_governance_datamart_useast1.v_agent_infra_costs`
  GROUP BY
    agent_id
) infra ON reg.agent_id = infra.agent_id
LEFT JOIN (
  SELECT
    agent_id,
    SUM(estimated_token_cost) AS total_token_cost
  FROM
    `agent_governance_datamart_useast1.v_agent_token_costs`
  GROUP BY
    agent_id
) token ON reg.agent_id = token.agent_id;
