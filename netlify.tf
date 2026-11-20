# Netlify sites are created in the Netlify UI. Terraform looks them up by name and
# manages settings on them. Build settings stay in each site's netlify.toml.
data "netlify_site" "this" {
  for_each = var.netlify_sites

  name = each.key
}

resource "netlify_site_domain_settings" "this" {
  for_each = { for name, site in var.netlify_sites : name => site if site.custom_domain != null }

  site_id        = data.netlify_site.this[each.key].id
  custom_domain  = each.value.custom_domain
  domain_aliases = each.value.domain_aliases

  lifecycle {
    prevent_destroy = true
  }
}

locals {
  netlify_env_vars = merge([
    for site_name, site in var.netlify_sites : {
      for key, env in site.env_vars : "${site_name}/${key}" => merge(env, { site = site_name, key = key })
    }
  ]...)
}

resource "netlify_environment_variable" "this" {
  for_each = local.netlify_env_vars

  site_id = data.netlify_site.this[each.value.site].id
  key     = each.value.key
  scopes  = each.value.scopes
  values = [{
    value   = each.value.value
    context = each.value.context
  }]
}
