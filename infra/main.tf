module "bronze" {
  source = "./modules/bronze"
}

module "silver" {
  source = "./modules/silver"
}

module "glue_iam" {
  source = "./modules/glue-iam"

  bronze_bucket_arn = module.bronze.bucket_arn
  silver_bucket_arn = module.silver.bucket_arn
}

module "glue_job" {
  source = "./modules/glue-job"

  bronze_bucket_name = module.bronze.bucket_name
  bronze_bucket_arn  = module.bronze.bucket_arn
  warehouse_uri      = module.silver.warehouse_uri
  role_arn           = module.glue_iam.role_arn
  role_name          = module.glue_iam.role_name
}
