MERGE INTO gaming_analytics_gold.completed_deposits AS target
USING (
    WITH deposits AS (
        SELECT
            transaction_id,
            player_id,
            CAST(at_timezone(from_iso8601_timestamp(created_at), 'UTC') AS date) AS activity_date,
            amount
        FROM gaming_analytics_silver.transactions
        WHERE transaction_type = 'deposit' AND status = 'completed'
    )
    SELECT
        COALESCE(deposits.transaction_id, existing.transaction_id) AS transaction_id,
        deposits.player_id,
        deposits.activity_date,
        deposits.amount,
        deposits.transaction_id IS NULL AS remove_row
    FROM deposits
    FULL OUTER JOIN gaming_analytics_gold.completed_deposits AS existing
        ON deposits.transaction_id = existing.transaction_id
) AS source
ON target.transaction_id = source.transaction_id
WHEN MATCHED AND source.remove_row THEN DELETE
WHEN MATCHED AND (
    target.player_id IS DISTINCT FROM source.player_id
    OR target.activity_date IS DISTINCT FROM source.activity_date
    OR target.amount IS DISTINCT FROM source.amount
) THEN UPDATE SET
    player_id = source.player_id,
    activity_date = source.activity_date,
    amount = source.amount
WHEN NOT MATCHED AND NOT source.remove_row THEN INSERT (
    transaction_id, player_id, activity_date, amount
) VALUES (
    source.transaction_id, source.player_id, source.activity_date, source.amount
)
