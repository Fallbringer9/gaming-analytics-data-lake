output "warehouse_uri" {
  description = "Emplacement S3 du warehouse Iceberg Silver."
  value       = "s3://${aws_s3_bucket.silver.bucket}/warehouse/"
}

output "bucket_arn" {
  description = "ARN du bucket S3 pour les politiques IAM."
  value       = aws_s3_bucket.silver.arn
}
