moved {
  from = aws_s3_bucket.bronze
  to   = module.bronze.aws_s3_bucket.bronze
}

moved {
  from = aws_s3_bucket_public_access_block.bronze
  to   = module.bronze.aws_s3_bucket_public_access_block.bronze
}
