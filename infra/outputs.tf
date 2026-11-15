output "bronze_bucket_name" {
  description = "Bucket où déposer les lots CSV bruts."
  value       = module.bronze.bucket_name
}

output "silver_warehouse_uri" {
  description = "Emplacement du warehouse Iceberg Silver à fournir au job Glue."
  value       = module.silver.warehouse_uri
}

output "gold_bucket_name" {
  description = "Bucket privé destiné aux résultats analytiques Gold."
  value       = module.gold.bucket_name
}

output "glue_execution_role_arn" {
  description = "ARN du rôle d’exécution du futur job AWS Glue."
  value       = module.glue_iam.role_arn
}

output "glue_job_name" {
  description = "Nom du job Glue de validation et d’écriture Silver."
  value       = module.glue_job.job_name
}

output "gold_athena_workgroup" {
  description = "Groupe de travail Athena pour le calcul et la consultation Gold."
  value       = module.athena.workgroup_name
}
