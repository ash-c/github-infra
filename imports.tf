# Brings repositories that existed before this configuration under management.
# These are no-ops once the resources are in terraform.tfstate.
import {
  to = github_repository.this["cw-website"]
  id = "cw-website"
}

import {
  to = github_repository.this["github-infra"]
  id = "github-infra"
}

import {
  to = github_repository.this["latlng"]
  id = "latlng"
}

import {
  to = github_repository.this["pirategame"]
  id = "pirategame"
}
