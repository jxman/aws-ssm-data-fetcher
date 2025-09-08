resource "aws_s3_bucket" "main" {
  bucket = "${var.project_name}-${var.environment}-${random_string.suffix.result}"

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-${var.environment}-bucket"
  })
}

resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}

resource "aws_s3_bucket_versioning" "main" {
  bucket = aws_s3_bucket.main.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "main" {
  bucket = aws_s3_bucket.main.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    id     = "cache_cleanup"
    status = "Enabled"

    filter {
      prefix = "cache/"
    }

    expiration {
      days = 7
    }

    noncurrent_version_expiration {
      noncurrent_days = 1
    }
  }

  rule {
    id     = "reports_lifecycle"
    status = "Enabled"

    filter {
      prefix = "reports/"
    }

    expiration {
      days = 60
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}

# S3 bucket notification for processing completion
resource "aws_s3_bucket_notification" "main" {
  bucket = aws_s3_bucket.main.id

  # Optional: Add Lambda function notifications if needed
  # lambda_function {
  #   lambda_function_arn = var.lambda_function_arn
  #   events              = ["s3:ObjectCreated:*"]
  #   filter_prefix       = "reports/"
  # }
}
