resource "aws_s3_bucket" "bronze" {
  bucket_prefix = "gaming-analytics-bronze-"
}

resource "aws_s3_bucket_public_access_block" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
