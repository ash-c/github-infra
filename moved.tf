# cw-website was renamed to portfolio. Moving the state addresses makes
# Terraform rename the repository in place instead of planning a new one.
moved {
  from = github_repository.this["cw-website"]
  to   = github_repository.this["portfolio"]
}

moved {
  from = github_branch_default.this["cw-website"]
  to   = github_branch_default.this["portfolio"]
}

moved {
  from = github_branch_protection.default["cw-website"]
  to   = github_branch_protection.default["portfolio"]
}
