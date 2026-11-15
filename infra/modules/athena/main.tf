resource "aws_glue_catalog_database" "gold" {
  name = "gaming_analytics_gold"
}

resource "aws_athena_workgroup" "gold" {
  name = "gaming-analytics-gold"

  configuration {
    enforce_workgroup_configuration = true
    bytes_scanned_cutoff_per_query  = 104857600

    engine_version {
      selected_engine_version = "Athena engine version 3"
    }

    result_configuration {
      output_location = "s3://${var.gold_bucket_name}/athena-results/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}
