# Netlify team that owns the sites below.
netlify_team_slug = "TEAM_SLUG"

# One entry per existing Netlify site, keyed by site name. Sites themselves are
# created in the Netlify UI; build settings live in each repo's netlify.toml.
netlify_sites = {
  # Hosts the portfolio repository (ashcrockett.netlify.app).
  "ashcrockett" = {
    # No custom domain yet. Setting custom_domain makes Terraform manage the
    # site's custom domain and domain_aliases.
    #
    # Non-secret env vars only (terraform.tfstate is public). NODE_VERSION is
    # set in netlify.toml, not here.
    env_vars = {}
  }
}
