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
