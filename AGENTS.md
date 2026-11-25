# AGENTS.md

Terraform for the `ash-c` GitHub repositories and existing Netlify sites. [README.md](README.md) is the source of truth for authentication, state and concurrency, and lifecycle procedures; this file summarises the rules agents must follow.

## Layout

- `repos.auto.tfvars`: one entry per managed repository. Unset fields use the defaults in `variables.tf`.
- `variables.tf`: input types and defaults. A default change applies to every repository that doesn't override it.
- `repos.tf`: `github_repository`, `github_branch_default` and `github_branch_protection` for each entry.
- `netlify.auto.tfvars` and `netlify.tf`: Netlify site settings, managed separately from the repositories.
- `imports.tf`, `moved.tf`: import and moved blocks.
- `terraform.tfstate`: committed state, written only by CI.
- `docs/adr/`: decision records. Add one here for significant changes, copying the sibling Home Repo template `../home-repo/docs/adr/0000-template.md`.

## Rules

- All infrastructure changes go through pull requests.
- Never run `terraform apply`, `import`, `state rm`, `state mv` or `taint` locally, and never edit `terraform.tfstate` by hand. CI is the only writer of state.
- Keep `prevent_destroy = true` and `archive_on_destroy = true` on repositories, and don't weaken existing branch protection.
- A rename changes the entry's key and needs `moved` blocks for every affected resource (`github_repository`, `github_branch_default`, `github_branch_protection`, `github_repository_ruleset.release_branches`). Without them the plan tries to replace the repository.
- Bring repositories under management and retire them using the README procedures (`import` blocks; archive first, then remove). Don't improvise destructive operations.
- State is public. Never commit credentials, and don't manage secret values (Actions secrets, deploy keys, webhook secrets, secret Netlify environment variables) through these resources.
- Authentication uses `GITHUB_TOKEN` and `NETLIFY_API_TOKEN`. Both providers are configured, so every plan needs both, including GitHub-only changes. Don't record token values or expiry dates here; the README tracks expiry.

## Verification

Read-only commands, matching CI:

```sh
terraform fmt -check -recursive -diff
terraform init              # only if providers aren't installed in .terraform/
terraform validate -no-color
terraform plan -no-color -lock=false   # needs GITHUB_TOKEN and NETLIFY_API_TOKEN
```

- `init` and `validate` accept any `NETLIFY_API_TOKEN` value; `plan` needs real read access.
- If Terraform or credentials aren't available locally, rely on the PR's CI run.
- Never use `apply` as verification.

## CI

[`.github/workflows/terraform.yml`](.github/workflows/terraform.yml):

- **Pull request:** `fmt -check`, `init`, `validate`, `plan`, then posts the plan as a PR comment. `plan` is a required check on `main`.
- **Merge to `main`:** `apply -auto-approve`, then commits `terraform.tfstate` to `main` as `Update terraform.tfstate [skip ci]`.

Before merging, read the PR's plan comment and confirm it shows only the intended changes: no unexpected creates, destroys, replacements or drift.
