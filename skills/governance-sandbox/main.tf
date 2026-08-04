resource "google_cloud_run_v2_service" "customer_support" {
  name     = "agent-support-service"
  location = "us-central1"
}
