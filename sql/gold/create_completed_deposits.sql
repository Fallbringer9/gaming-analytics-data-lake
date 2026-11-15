CREATE TABLE IF NOT EXISTS gaming_analytics_gold.completed_deposits (
    transaction_id string,
    player_id string,
    activity_date date,
    amount decimal(18, 2)
)
LOCATION 's3://${gold_bucket}/warehouse/completed_deposits/'
TBLPROPERTIES ('table_type' = 'ICEBERG', 'format' = 'parquet')
