# 0001. Manage GitHub repositories with Terraform and committed state

- Status: Accepted
- Date: 2026-11-21

## Context

Repository settings for `ash-c` (descriptions, merge options, default branches, branch protection) were set by hand in the GitHub UI. That drifts, is not reviewable, and makes new projects inconsistent. There is one owner and no organization, and no remote state backend (S3, HCP Terraform) is wanted for a handful of repositories.

Options considered: GitHub UI only; a script calling the REST API; Terraform with a remote backend; Terraform with state committed to the repository.

## Decision

Manage all `ash-c` repositories with Terraform using the `integrations/github` provider, with a local `terraform.tfstate` committed to this repository. GitHub Actions is the only writer of state: it plans on every pull request and applies on merge to `main`, then commits the updated state back to `main`.

- Repositories are entries in `var.repos` (`repos.auto.tfvars`); adding a repository is one map entry and a pull request.
- Authentication is a fine-grained PAT stored as the `GH_TOKEN` Actions secret, because the workflow's `GITHUB_TOKEN` cannot administer other repositories.
- `github_repository` has `prevent_destroy` and `archive_on_destroy`, so Terraform never deletes a repository.
- Applies run in a single `concurrency` group and always use the tip of `main`.

## Consequences

- Repository settings are reviewed in pull requests and visible as code; drift shows up in the next plan.
- Running `terraform apply` locally would fork the state; the README forbids it, and it must be enforced by convention.
- State is public with the repository. It holds repository IDs and settings only; secrets (webhook secrets, deploy keys) must not be managed here without a private, encrypted backend.
- The PAT expires and must be rotated (see README). An expired token makes every plan and apply fail.
- `github-infra` itself allows admin bypass of branch protection so CI can push state commits with the owner's token.
- Moving to a remote backend later needs `terraform init -migrate-state` and a superseding ADR.
