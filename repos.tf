resource "github_repository" "this" {
  for_each = var.repos

  name         = each.key
  description  = each.value.description
  homepage_url = each.value.homepage_url
  visibility   = each.value.visibility
  topics       = each.value.topics
  archived     = each.value.archived
  is_template  = each.value.is_template

  has_issues      = each.value.has_issues
  has_projects    = each.value.has_projects
  has_wiki        = each.value.has_wiki
  has_discussions = each.value.has_discussions

  allow_merge_commit     = each.value.allow_merge_commit
  allow_squash_merge     = each.value.allow_squash_merge
  allow_rebase_merge     = each.value.allow_rebase_merge
  allow_auto_merge       = each.value.allow_auto_merge
  allow_update_branch    = each.value.allow_update_branch
  delete_branch_on_merge = each.value.delete_branch_on_merge

  # If a destroy ever does run, archive the repository instead of deleting it.
  archive_on_destroy = true

  lifecycle {
    prevent_destroy = true
  }
}

resource "github_branch_default" "this" {
  for_each = var.repos

  repository = github_repository.this[each.key].name
  branch     = each.value.default_branch
}

resource "github_branch_protection" "default" {
  for_each = { for name, repo in var.repos : name => repo if repo.branch_protection != null && !repo.archived }

  repository_id = github_repository.this[each.key].node_id
  pattern       = each.value.default_branch

  enforce_admins      = each.value.branch_protection.enforce_admins
  allows_deletions    = false
  allows_force_pushes = false

  # Changes reach the branch only through pull requests. No approval is
  # required because the owner is the only collaborator.
  required_pull_request_reviews {
    required_approving_review_count = 0
  }

  dynamic "required_status_checks" {
    for_each = length(each.value.branch_protection.required_checks) > 0 ? [1] : []
    content {
      strict   = false
      contexts = each.value.branch_protection.required_checks
    }
  }
}
