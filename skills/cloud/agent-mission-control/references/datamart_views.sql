-- Mission Control View: Blocked Security Incidents & Errors
CREATE OR REPLACE VIEW `agent_governance_datamart.v_blocked_incidents` AS
SELECT
  timestamp,
  jsonPayload.agent_id AS agent_id,
  jsonPayload.action_taken AS action_taken,
  jsonPayload.reason AS reason,
  jsonPayload.business_unit AS business_unit,
  jsonPayload.environment AS environment,
  severity
FROM `agent_governance_datamart.agent_security_log_*`;
