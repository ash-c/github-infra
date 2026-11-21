# github-infra

Terraform that manages the GitHub repositories owned by [`ash-c`](https://github.com/ash-c): creation, naming, descriptions, features, merge settings, default branches, branch protection and release branch rulesets. It manages itself too.

It also manages settings on existing Netlify sites: custom domains and non-secret environment variables.

## How it works

- Each repository is one entry in [`repos.auto.tfvars`](repos.auto.tfvars). Unset fields use the defaults in [`variables.tf`](variables.tf).
- [`repos.tf`](repos.tf) creates `github_repository`, `github_branch_default`, `github_repository_ruleset.release_branches` (unless `protect_release_branches = false` or archived) and (unless `branch_protection = { enabled = false }` or archived) `github_branch_protection` for every entry.
- Each Netlify site is one entry in [`netlify.auto.tfvars`](netlify.auto.tfvars), keyed by Netlify site name. [`netlify.tf`](netlify.tf) looks the site up and manages `netlify_site_domain_settings` (only where `custom_domain` is set) and one `netlify_environment_variable` per `env_vars` entry. Sites are created in the Netlify UI, and build settings stay in each repository's `netlify.toml`, which overrides build settings set through the API. DNS is not managed.
- State is the committed [`terraform.tfstate`](terraform.tfstate). There is no remote backend.
- [`.github/workflows/terraform.yml`](.github/workflows/terraform.yml):
  - **Pull request:** `fmt -check`, `init`, `validate`, `plan`. The plan is posted as a PR comment (updated on each push). The `plan` job is a required check on `main`.
  - **Merge to `main`:** `apply -auto-approve`, then commits `terraform.tfstate` back to `main` as `Update terraform.tfstate [skip ci]`. Can also be run manually (Actions → Terraform → Run workflow) to reconcile drift.

> [!WARNING]
> **Never run `terraform apply` (or `import`, `state rm`, `taint`) locally.** CI is the only writer of `terraform.tfstate`. A local apply changes GitHub without updating the committed state, and the next CI run will fight it. All changes go through pull requests.

Read-only local use is fine:

```sh
export GITHUB_TOKEN=$(gh auth token)   # any token that can read the repos
export NETLIFY_API_TOKEN=...           # a Netlify personal access token (init and validate accept any value)
terraform init
terraform fmt -recursive
terraform validate
terraform plan -lock=false
```

## Common changes

| Change | How |
| --- | --- |
| New repository | Add an entry to `repos.auto.tfvars`, open a PR, check the plan, merge. It is created with an initial commit on `main`; leave `default_branch` as `main` for new repos (rename the branch on GitHub first if you need another one). |
| Change settings | Edit the entry. The plan shows the in-place update. |
| Rename | Change the entry's key and add a `moved` block from `github_repository.this["old"]` to `github_repository.this["new"]` (and the same for `github_branch_default`, `github_branch_protection` and `github_repository_ruleset.release_branches`). Without it, Terraform plans a new repository and is blocked by `prevent_destroy`. |
| Bring an existing repository under management | Add its entry and an `import` block in [`imports.tf`](imports.tf). Remove the block after the apply. |
| Archive | Set `archived = true`. Branch protection is removed for archived repositories. |

### Retiring a repository

Terraform never deletes a repository here:

- `lifecycle { prevent_destroy = true }` makes any plan that would destroy a repository fail.
- `archive_on_destroy = true` means that if a destroy does run, the repository is archived, not deleted.

To stop managing a repository:

1. PR 1: set `archived = true` and merge.
2. PR 2: remove the entry and temporarily set `prevent_destroy = false` in `repos.tf`. The plan shows the repository being "destroyed" (archived). Merge, then restore `prevent_destroy = true` in a follow-up PR.
3. To actually delete it, use the GitHub UI (Settings → Danger zone).

## Branch protection

Every non-archived repository gets, on its default branch: PR-only changes with at least one approving review, required status checks as listed, and no force pushes or deletion. Set `branch_protection = { enabled = false }` to opt a repository out (`null` doesn't work: Terraform replaces it with the default). GitHub doesn't count a PR author's own approval, so someone other than the author must approve (see [ADR 0003](docs/adr/0003-require-pr-approval-before-merge.md)).

- `portfolio` requires its `check` CI job and enforces the rules for admins, so the owner can't bypass the approval.
- `github-infra` requires `plan` and sets `enforce_admins = false`, so the apply job can push the state commit to `main` with the owner's token. This also means the owner can bypass protection here; don't.
- Required checks are `strict`: a PR branch must be up to date with `main` before it can merge, so checks run against what will land. After `main` moves, use **Update branch** on open PRs.
- Branch protection on **private** repositories needs GitHub Pro. All repositories are currently public.

### Release branches

Every repository gets a `release branches` ruleset (`github_repository_ruleset.release_branches`) that blocks deletion of and force pushes to `release/*` branches, so automatic branch deletion after a merge doesn't remove them. Nobody can bypass it: to delete a release branch, set `protect_release_branches = false` on the repository first. Archived repositories are skipped.

## Netlify

| Change | How |
| --- | --- |
| Manage another site | Create it in the Netlify UI, then add an entry keyed by its site name to `netlify.auto.tfvars`. |
| Custom domain | Set `custom_domain` (and optionally `domain_aliases`). DNS for the domain is configured outside Terraform. Removing it later is blocked by `prevent_destroy`. |
| Environment variable | Add it to the site's `env_vars` with a `value` and optional `context` (default `all`). Leave `scopes` unset on the free plan. |

> [!WARNING]
> **Only non-secret environment variables belong here.** `terraform.tfstate` is public, and every value, including `secret_values`, is written to it in plain text. Set secrets in the Netlify UI.

## Authentication and PAT rotation

The provider reads `GITHUB_TOKEN`, which the workflow sets from the **`GH_TOKEN` Actions secret**: a fine-grained personal access token. The built-in workflow `GITHUB_TOKEN` cannot administer other repositories.

> [!IMPORTANT]
> **The current fine-grained PAT expires on 2027-11-21.** When it expires, every plan and apply fails with `401 Bad credentials`.

Rotate before then:

1. GitHub → Settings → Developer settings → Fine-grained tokens → **Generate new token** (or *Regenerate* the existing one).
2. Resource owner `ash-c`, **Repository access: All repositories**.
3. Repository permissions:
   - Administration: **Read and write**
   - Contents: **Read and write**
   - Pull requests: **Read and write**
   - Metadata: **Read-only** (added automatically)
4. Set an expiry (up to 1 year, or longer if allowed) and note it.
5. `ash-c/github-infra` → Settings → Secrets and variables → Actions → update **`GH_TOKEN`**.
6. Update the expiry date in this README and re-run the latest Terraform workflow (or open a PR) to confirm the plan succeeds.

### Netlify token

The Netlify provider reads `NETLIFY_API_TOKEN`, which the workflow sets from the **`NETLIFY_TOKEN` Actions secret**: a Netlify personal access token. Every plan and apply needs it, including GitHub-only changes.

> [!IMPORTANT]
> **The current Netlify token expires on 2027-11-21**, the same day as `GH_TOKEN`. When it expires, every plan and apply fails.

Create or rotate it alongside `GH_TOKEN`:

1. Netlify → User settings → Applications → Personal access tokens → **New access token**. Set an expiry and note it.
2. `ash-c/github-infra` → Settings → Secrets and variables → Actions → create or update **`NETLIFY_TOKEN`**.
3. Update the expiry date in this README.
4. Re-run the latest Terraform workflow (or open a PR) to confirm the plan succeeds, then revoke the old token.

## State and concurrency

- The apply job runs in the `terraform-state` concurrency group, so only one apply runs at a time, and it checks out the tip of `main` rather than the triggering commit. A queued run that GitHub cancels is covered by the next one, which applies everything merged so far.
- If `main` moves while an apply runs, the job rebases its state commit onto `main` and pushes again. Only CI edits `terraform.tfstate`, so this should not conflict. If it does, someone edited the state by hand: stop, compare the two versions, and fix it in a PR before merging anything else.
- If an apply fails partway, the job still commits the partial state. Fix the cause in a new PR.
- The state is public along with this repository. It contains repository and Netlify site IDs and settings, including Netlify environment variable values. Don't manage secrets (webhook secrets, deploy keys, Actions secrets, secret Netlify environment variables) here without moving to a private, encrypted backend.

## Bootstrap (done once)

1. Fine-grained PAT created (expires 2027-11-21) and stored as `GH_TOKEN`.
1. Netlify personal access token created (expires 2027-11-21) and stored as `NETLIFY_TOKEN`.
2. `github-infra` created in the GitHub UI, since Terraform cannot create the repository it runs from.
3. First PR added the configuration with `import` blocks for every existing repository. Merging it ran the first apply, which imported them and committed `terraform.tfstate`. The completed import blocks have since been removed.

## Decisions

See [`docs/adr/`](docs/adr). Add a new ADR (copy `0000-template.md`) for significant changes, such as a different backend.
