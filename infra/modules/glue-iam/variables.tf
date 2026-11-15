variable "bronze_bucket_arn" {
  description = "ARN du bucket qui contient les lots CSV bruts."
  type        = string
}

variable "silver_bucket_arn" {
  description = "ARN du bucket qui héberge le warehouse Iceberg."
  type        = string
}
