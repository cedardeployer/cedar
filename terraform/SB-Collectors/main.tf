provider "aws" {
    # version = "~> 2.0"
    region = local.region
}

output "region" {
    value = local.region
}

module "_s3" {
  source = "../lib/aws//_s3"
}

