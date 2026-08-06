# Looker Studio Operational Dashboard Setup Guide

This guide describes how to connect your Looker Studio report to the BigQuery views we created in project `olympus-475310` to chart your agent operational metrics.

---

## 1. Connect Data Sources to Looker Studio

For each of the three views, add them as a data source in Looker Studio:

1. Click **Add data** in Looker Studio.
2. Select the **BigQuery** connector.
3. Select Project **`olympus-475310`** ➔ Dataset **`agent_governance_datamart_useast1`**.
4. Add the following views:
   * `v_looker_agent_performance` (Agent Invocations, Errors, Latency)
   * `v_looker_token_usage` (Agent Token usage)
   * `v_looker_tool_analytics` (Tool Calls, Failures, Timeouts)

---

## 2. Configure Your Charts

### Chart 1: Agent Total Invocations & Error Count
* **Data Source:** `v_looker_agent_performance`
* **Chart Type:** Time Series Chart or Combo Chart (Line + Column)
* **Dimension:** `timestamp` (grouped by hour or day)
* **Metric 1:** `invocation_count` (Sum) ➔ Rename to **Total Invocations**
* **Metric 2:** `error_count` (Sum) ➔ Rename to **Total Errors**

### Chart 2: Agent Error Rate (%)
* **Data Source:** `v_looker_agent_performance`
* **Chart Type:** Scorecard or Gauge Chart
* **Metric:** Create a custom field (Formula):
  $$\text{Error Rate} = \frac{\text{SUM}(error\_count)}{\text{SUM}(invocation\_count)}$$
* **Type:** Percent

### Chart 3: Agent Token Usage
* **Data Source:** `v_looker_token_usage`
* **Chart Type:** Stacked Column Bar Chart
* **Dimension:** `timestamp` (grouped by day)
* **Breakdown Dimension:** `agent_id`
* **Metric:** `total_tokens` (Sum) or include both `input_tokens` and `output_tokens`

### Chart 4: Tool Invocation, Failure & Timeout Count
* **Data Source:** `v_looker_tool_analytics`
* **Chart Type:** Column Bar Chart
* **Dimension:** `tool_name`
* **Metric 1:** `tool_invocation_count` (Sum) ➔ Rename to **Invocations**
* **Metric 2:** `tool_failure_count` (Sum) ➔ Rename to **Failures**
* **Metric 3:** `tool_timeout_count` (Sum) ➔ Rename to **Timeouts**
