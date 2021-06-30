locals{
    


  domain            = "${local.domains[terraform.workspace]}"
  deployment_bucket = "${local.deployment_buckets[terraform.workspace]}"


# # S3 Bucket
# resource "aws_s3_bucket" "deployment" {
#   bucket = "${local.deployment_bucket}"
# }

    
}