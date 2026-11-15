CREATE TABLE IF NOT EXISTS gaming_analytics_gold.player_daily_finance (
    player_id string,
    activity_date date,
    completed_deposits decimal(38, 2),
    completed_withdrawals decimal(38, 2),
    net_flow decimal(38, 2),
    failed_deposits bigint
)
LOCATION 's3://${gold_bucket}/warehouse/player_daily_finance/'
TBLPROPERTIES ('table_type' = 'ICEBERG', 'format' = 'parquet')
