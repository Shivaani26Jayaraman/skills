resource "google_cloud_run_v2_service" "customer_support" {
  labels = {
    "agent-id"      = "ace-agent"
    "business-unit" = "finance"
    "cost-centre"   = "cc-finance"
    "environment"   = "staging"
  }
  name     = "agent-support-service"
  location = "us-central1"
}
