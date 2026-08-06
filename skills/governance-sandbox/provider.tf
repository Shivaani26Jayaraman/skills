provider "google" {
  default_labels = {
    "agent-id"      = "ace-agent"
    "business-unit" = "finance"
    "cost-centre"   = "cc-finance"
    "environment"   = "staging"
  }
  project = "olympus-475310"
}
