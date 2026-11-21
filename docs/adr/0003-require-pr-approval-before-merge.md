# 0003. Require PR approval before merge

- Status: Accepted
- Date: 2026-11-21

## Context

Branch protection required pull requests on the default branch but `required_approving_review_count = 0`, because the owner was the only collaborator. Most pull requests are now authored by Devin, so an approving review from the owner is a meaningful gate. Protection was also opt-in: `branch_protection` defaulted to `null`, leaving any new repository unprotected until someone remembered to add it.

Options considered: keep 0 approvals; require 1 approval only on repositories that opt in; require 1 approval and make protection the default for every non-archived repository.

## Decision

Every non-archived repository requires at least one approving review before a pull request can merge into its default branch. `branch_protection` now defaults to `{}`, so protection applies unless a repository sets `branch_protection = { enabled = false }` or is archived. An explicit `null` can't be the opt-out, because Terraform replaces a null optional attribute with its default. The approval count is fixed at 1 in `repos.tf`, not a per-repository setting.

`enforce_admins` is unchanged and stays per repository:

- `github-infra` keeps `enforce_admins = false`, so the apply job can push the `terraform.tfstate` commit to `main` with the owner's token. The owner can also bypass the approval here.
- `portfolio` keeps `enforce_admins = true` (the default), so the rule applies to the owner too.

## Consequences

- New repositories get default-branch protection, including the approval requirement, without extra configuration.
- GitHub doesn't count a PR author's own approval. A pull request opened by the owner on a repository with `enforce_admins = true` (currently `portfolio`) needs a second person with write access to approve it. Pull requests authored by Devin can be approved by the owner.
- Any collaborator with write access can provide the approval; it doesn't have to be the owner.
- Opting a repository out of protection is now an explicit `branch_protection = { enabled = false }` in `repos.auto.tfvars`, visible in review.
