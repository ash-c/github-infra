# 0002. Manage Netlify site settings with Terraform

- Status: Accepted
- Date: 2026-11-21

## Context

The portfolio is hosted on the Netlify site `ashcrockett`. Its build configuration (command, publish directory, Node version, SPA redirect) lives in the portfolio repository's `netlify.toml`. Domain settings and environment variables were only editable in the Netlify UI, unlike the GitHub settings managed by [0001](0001-terraform-github-iac.md).

Options considered: Netlify UI only; the archived `hashicorp/netlify` provider; the official `netlify/netlify` provider in this repository, sharing the existing state and workflow.

## Decision

Manage Netlify site settings here with the official `netlify/netlify` provider, pinned to `~> 0.4.4` through `.terraform.lock.hcl`. The plan and apply workflow is unchanged apart from a `NETLIFY_TOKEN` Actions secret, exposed to the provider as `NETLIFY_API_TOKEN`.

- The provider has no site resource. Sites are created in the Netlify UI and read with the `netlify_site` data source, keyed by site name in `var.netlify_sites` (`netlify.auto.tfvars`).
- `netlify_site_domain_settings` manages the custom domain and aliases only for sites that set `custom_domain`, with `prevent_destroy`.
- `netlify_environment_variable` manages non-secret site environment variables.
- Build settings stay in `netlify.toml`, which overrides build settings set through the API and holds the SPA redirect that the provider cannot express.
- DNS is not managed. The `codewizardry.com` zone is on GoDaddy, not Netlify DNS.

## Consequences

- Domain and environment variable changes are reviewed in pull requests like repository settings.
- `terraform.tfstate` is public, so secret environment variables (`secret_values`) and any sensitive values must not be managed here without a private, encrypted backend.
- Every plan now needs a valid Netlify token. An expired or revoked `NETLIFY_TOKEN` fails plan and apply for GitHub changes too.
- Custom env var `scopes` are not supported on the free plan; leave them unset.
- The provider is young (0.x). Upgrades within `0.4` are taken through the lock file; a move to `0.5` or later needs a reviewed plan.
- Managing Netlify DNS (`netlify_dns_zone`, `netlify_dns_record`) is a possible follow-up if the domain moves to Netlify DNS.
