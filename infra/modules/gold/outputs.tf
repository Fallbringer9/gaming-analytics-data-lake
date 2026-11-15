output "bucket_name" {
  description = "Nom du bucket privé destiné aux données Gold."
  value       = aws_s3_bucket.gold.bucket
}
