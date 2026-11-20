# Authenticates with the GITHUB_TOKEN environment variable (the GH_TOKEN secret in CI).
provider "github" {
  owner = var.owner
}

# Authenticates with the NETLIFY_API_TOKEN environment variable (the NETLIFY_TOKEN secret in CI).
provider "netlify" {
  default_team_slug = var.netlify_team_slug
}
