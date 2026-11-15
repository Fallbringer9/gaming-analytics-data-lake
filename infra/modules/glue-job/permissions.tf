data "aws_iam_policy_document" "job" {
  statement {
    sid       = "ReadJobScript"
    actions   = ["s3:GetObject"]
    resources = ["${var.bronze_bucket_arn}/${local.script_key}"]
  }

  statement {
    sid       = "ReadBucketLocation"
    actions   = ["s3:GetBucketLocation"]
    resources = [var.bronze_bucket_arn]
  }

  statement {
    sid       = "ListJobOutputPrefixes"
    actions   = ["s3:ListBucket"]
    resources = [var.bronze_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${local.temp_prefix}/*"]
    }
  }

  statement {
    sid       = "WriteJobOutputPrefixes"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload"]
    resources = ["${var.bronze_bucket_arn}/${local.temp_prefix}/*"]
  }

  statement {
    sid       = "WriteQuarantineReports"
    actions   = ["s3:PutObject", "s3:AbortMultipartUpload"]
    resources = ["${var.bronze_bucket_arn}/${local.reject_prefix}/*"]
  }

  statement {
    sid       = "ReadSilverDatabase"
    actions   = ["glue:GetDatabase"]
    resources = ["${local.glue_arn}:catalog", "${local.glue_arn}:database/${local.database_name}"]
  }

  statement {
    sid     = "ManageSilverTransactionsTable"
    actions = ["glue:GetTable", "glue:CreateTable", "glue:UpdateTable"]
    resources = [
      "${local.glue_arn}:catalog",
      "${local.glue_arn}:database/${local.database_name}",
      "${local.glue_arn}:table/${local.database_name}/transactions",
    ]
  }

  statement {
    sid       = "WriteJobLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = [for group in aws_cloudwatch_log_group.jobs : "${local.logs_arn}:log-group:${group.name}:log-stream:*"]
  }
}

resource "aws_iam_role_policy" "job" {
  name   = "gaming-analytics-glue-job"
  role   = var.role_name
  policy = data.aws_iam_policy_document.job.json
}
