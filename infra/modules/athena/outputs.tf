output "workgroup_name" {
  description = "Groupe de travail Athena pour Gold."
  value       = aws_athena_workgroup.gold.name
}
