output "role_arn" {
  description = "ARN du rôle d’exécution à fournir au job AWS Glue."
  value       = aws_iam_role.glue.arn
}

output "role_name" {
  value = aws_iam_role.glue.name
}
