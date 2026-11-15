output "bucket_name" {
  description = "Bucket où déposer les lots CSV bruts."
  value       = aws_s3_bucket.bronze.bucket
}

output "bucket_arn" {
  description = "ARN du bucket S3 pour les politiques IAM."
  value       = aws_s3_bucket.bronze.arn
}
