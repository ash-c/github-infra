variable "owner" {
  description = "GitHub user that owns the managed repositories."
  type        = string
  default     = "ash-c"
}

variable "repos" {
  description = "Repositories to manage, keyed by repository name. Values live in repos.auto.tfvars."
  type = map(object({
    description            = optional(string)
    homepage_url           = optional(string)
    visibility             = optional(string, "public")
    topics                 = optional(list(string), [])
    default_branch         = optional(string, "main")
    archived               = optional(bool, false)
    is_template            = optional(bool, false)
    has_issues             = optional(bool, true)
    has_projects           = optional(bool, true)
    has_wiki               = optional(bool, true)
    has_discussions        = optional(bool, false)
    allow_merge_commit     = optional(bool, true)
    allow_squash_merge     = optional(bool, true)
    allow_rebase_merge     = optional(bool, true)
    allow_auto_merge       = optional(bool, false)
    allow_update_branch    = optional(bool, false)
    delete_branch_on_merge = optional(bool, false)

    # Protects the default branch. null leaves it unprotected.
    branch_protection = optional(object({
      # Required status check names, e.g. GitHub Actions job names.
      required_checks = optional(list(string), [])
      # false lets the owner (and CI using the owner's token) bypass the rules.
      enforce_admins = optional(bool, true)
    }))
  }))

  validation {
    condition     = alltrue([for r in values(var.repos) : contains(["public", "private"], r.visibility)])
    error_message = "visibility must be \"public\" or \"private\"."
  }
}

variable "netlify_team_slug" {
  description = "Slug of the Netlify team that owns the managed sites (app.netlify.com/teams/<slug>)."
  type        = string
}

variable "netlify_sites" {
  description = "Existing Netlify sites to manage, keyed by Netlify site name. Values live in netlify.auto.tfvars."
  type = map(object({
    # null leaves the site's domain settings unmanaged.
    custom_domain  = optional(string)
    domain_aliases = optional(list(string), [])

    # Non-secret values only: terraform.tfstate is public.
    env_vars = optional(map(object({
      value   = string
      context = optional(string, "all")
      # Custom scopes are not supported on the free plan; null uses all scopes.
      scopes = optional(list(string))
    })), {})
  }))
  default = {}

  validation {
    condition = alltrue(flatten([
      for site in values(var.netlify_sites) : [
        for v in values(site.env_vars) :
        contains(["all", "production", "deploy-preview", "branch-deploy", "dev", "dev-server"], v.context)
      ]
    ]))
    error_message = "env_vars context must be one of all, production, deploy-preview, branch-deploy, dev, dev-server."
  }
}
