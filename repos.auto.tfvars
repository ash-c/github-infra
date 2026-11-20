# One entry per repository. Adding a repo here (and merging the PR) creates it on GitHub.
# Removing an entry is blocked by prevent_destroy; see README.md ("Retiring a repository").
repos = {
  "portfolio" = {
    description = "Portfolio website for Ash Crockett, full-stack software engineer in Taranaki, NZ."
    branch_protection = {
      required_checks = ["check"]
    }
  }

  "github-infra" = {
    description = "Infrastructure covering my GitHub repositories."
    branch_protection = {
      required_checks = ["plan"]
      # CI commits terraform.tfstate straight to main with the owner's token.
      enforce_admins = false
    }
  }

  "latlng" = {
    default_branch = "master"
  }

  "pirategame" = {
    description    = "Repo for final student project."
    default_branch = "master"
  }
}
