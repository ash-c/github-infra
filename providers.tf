# Authenticates with the GITHUB_TOKEN environment variable (the GH_TOKEN secret in CI).
provider "github" {
  owner = var.owner
}
