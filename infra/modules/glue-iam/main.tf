data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "glue" {
  name               = "AWSGlueServiceRole-GamingAnalytics"
  assume_role_policy = data.aws_iam_policy_document.trust.json
}

data "aws_iam_policy_document" "s3" {
  statement {
    sid       = "ListBronzeInputPrefixes"
    actions   = ["s3:ListBucket"]
    resources = [var.bronze_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["bronze/players/*", "bronze/transactions/*"]
    }
  }

  statement {
    sid     = "ReadBronzeInputs"
    actions = ["s3:GetObject"]
    resources = [
      "${var.bronze_bucket_arn}/bronze/players/*",
      "${var.bronze_bucket_arn}/bronze/transactions/*",
    ]
  }

  statement {
    sid       = "ListSilverWarehouse"
    actions   = ["s3:ListBucket"]
    resources = [var.silver_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["warehouse/*"]
    }
  }

  statement {
    sid       = "ReadWriteSilverWarehouse"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${var.silver_bucket_arn}/warehouse/*"]
  }
}

resource "aws_iam_role_policy" "s3" {
  name   = "gaming-analytics-s3"
  role   = aws_iam_role.glue.name
  policy = data.aws_iam_policy_document.s3.json
}
