provider "aws" {
    region = "us-east-1"
    
  assume_role {
    # The role ARN within Account B to AssumeRole into. Created in step 1.
    role_arn    = "arn:aws:iam::01234567890:role/role_in_account_b"
    # (Optional) The external ID created in step 1c.
    external_id = "my_external_id"
  }
}