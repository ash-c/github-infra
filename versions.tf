terraform {
  required_version = ">= 1.7"

  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.13"
    }
    netlify = {
      source  = "netlify/netlify"
      version = "~> 0.4.4"
    }
  }
}
