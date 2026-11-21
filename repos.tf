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

  # New repositories get an initial commit on GitHub's default branch (main),
  # so github_branch_default has a branch to point at.
  auto_init = true

  # If a destroy ever does run, archive the repository instead of deleting it.
  archive_on_destroy = true

  lifecycle {
    prevent_destroy = true
    # auto_init only matters at creation; imported repositories read it as false.
    ignore_changes = [auto_init]
  }
}

resource "github_branch_default" "this" {
  for_each = var.repos

  repository = github_repository.this[each.key].name
  branch     = each.value.default_branch
}

resource "github_branch_protection" "default" {
  for_each = { for name, repo in var.repos : name => repo if repo.branch_protection.enabled && !repo.archived }

  repository_id = github_repository.this[each.key].node_id
  pattern       = each.value.default_branch

  enforce_admins      = each.value.branch_protection.enforce_admins
  allows_deletions    = false
  allows_force_pushes = false

  # Changes reach the branch only through pull requests with at least one
  # approving review from a collaborator with write access.
  required_pull_request_reviews {
    required_approving_review_count = 1
  }

  dynamic "required_status_checks" {
    for_each = length(each.value.branch_protection.required_checks) > 0 ? [1] : []
    content {
      strict   = true
      contexts = each.value.branch_protection.required_checks
    }
  }
}

resource "github_repository_ruleset" "release_branches" {
  for_each = { for name, repo in var.repos : name => repo if repo.protect_release_branches && !repo.archived }

  name        = "release branches"
  repository  = github_repository.this[each.key].name
  target      = "branch"
  enforcement = "active"

  conditions {
    ref_name {
      include = ["refs/heads/release/*"]
      exclude = []
    }
  }

  rules {
    deletion         = true
    non_fast_forward = true
  }
}
