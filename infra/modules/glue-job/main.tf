data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  name          = "gaming-analytics-bronze-to-silver"
  database_name = "gaming_analytics_silver"
  glue_arn      = "arn:${data.aws_partition.current.partition}:glue:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}"
  logs_arn      = "arn:${data.aws_partition.current.partition}:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}"
  script_key    = "glue/scripts/transactions-${filesha256("${path.module}/transactions.py")}.py"
  reject_prefix = "quarantine/transactions/glue"
  temp_prefix   = "glue/temp/transactions"
}

resource "aws_glue_catalog_database" "silver" {
  name = local.database_name
}

resource "aws_s3_object" "script" {
  bucket                 = var.bronze_bucket_name
  key                    = local.script_key
  source                 = "${path.module}/transactions.py"
  source_hash            = filesha256("${path.module}/transactions.py")
  server_side_encryption = "AES256"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_cloudwatch_log_group" "jobs" {
  for_each          = toset(["error", "output"])
  name              = "/aws-glue/${local.name}/${each.key}"
  retention_in_days = 14
}

resource "aws_glue_job" "silver" {
  name              = local.name
  role_arn          = var.role_arn
  glue_version      = "5.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 10
  max_retries       = 0

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_object.script.bucket}/${aws_s3_object.script.key}"
    python_version  = "3"
  }

  execution_property {
    max_concurrent_runs = 1
  }

  default_arguments = {
    "--players_batch"       = "001"
    "--job-bookmark-option" = "job-bookmark-disable"
    "--enable-spark-ui"     = "false"
  }

  non_overridable_arguments = {
    "--TempDir"                = "s3://${var.bronze_bucket_name}/${local.temp_prefix}/"
    "--bronze_bucket"          = var.bronze_bucket_name
    "--database"               = aws_glue_catalog_database.silver.name
    "--custom-logGroup-prefix" = "/aws-glue/${local.name}"
    "--datalake-formats"       = "iceberg"
    "--conf" = join(" --conf ", [
      "spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
      "spark.sql.catalog.glue_catalog=org.apache.iceberg.spark.SparkCatalog",
      "spark.sql.catalog.glue_catalog.warehouse=${var.warehouse_uri}",
      "spark.sql.catalog.glue_catalog.catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog",
      "spark.sql.catalog.glue_catalog.io-impl=org.apache.iceberg.aws.s3.S3FileIO",
    ])
  }

  depends_on = [aws_iam_role_policy.job, aws_cloudwatch_log_group.jobs]
}
