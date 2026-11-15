MERGE INTO gaming_analytics_gold.player_daily_finance AS target
USING (
    WITH dated_transactions AS (
        SELECT
            player_id,
            CAST(at_timezone(from_iso8601_timestamp(created_at), 'UTC') AS date) AS activity_date,
            amount,
            transaction_type,
            status
        FROM gaming_analytics_silver.transactions
    ),
    daily AS (
        SELECT
            player_id,
            activity_date,
            SUM(CASE WHEN transaction_type = 'deposit' AND status = 'completed'
                THEN amount ELSE DECIMAL '0.00' END) AS completed_deposits,
            SUM(CASE WHEN transaction_type = 'withdrawal' AND status = 'completed'
                THEN amount ELSE DECIMAL '0.00' END) AS completed_withdrawals,
            SUM(CASE WHEN transaction_type = 'deposit' AND status = 'completed' THEN amount
                     WHEN transaction_type = 'withdrawal' AND status = 'completed' THEN -amount
                     ELSE DECIMAL '0.00' END) AS net_flow,
            COUNT_IF(transaction_type = 'deposit' AND status = 'failed') AS failed_deposits
        FROM dated_transactions
        GROUP BY player_id, activity_date
    )
    SELECT
        COALESCE(daily.player_id, existing.player_id) AS player_id,
        COALESCE(daily.activity_date, existing.activity_date) AS activity_date,
        daily.completed_deposits,
        daily.completed_withdrawals,
        daily.net_flow,
        daily.failed_deposits,
        daily.player_id IS NULL AS remove_row
    FROM daily
    FULL OUTER JOIN gaming_analytics_gold.player_daily_finance AS existing
        ON daily.player_id = existing.player_id
        AND daily.activity_date IS NOT DISTINCT FROM existing.activity_date
) AS source
ON target.player_id = source.player_id
AND target.activity_date IS NOT DISTINCT FROM source.activity_date
WHEN MATCHED AND source.remove_row THEN DELETE
WHEN MATCHED AND (
    target.completed_deposits IS DISTINCT FROM source.completed_deposits
    OR target.completed_withdrawals IS DISTINCT FROM source.completed_withdrawals
    OR target.net_flow IS DISTINCT FROM source.net_flow
    OR target.failed_deposits IS DISTINCT FROM source.failed_deposits
) THEN UPDATE SET
    completed_deposits = source.completed_deposits,
    completed_withdrawals = source.completed_withdrawals,
    net_flow = source.net_flow,
    failed_deposits = source.failed_deposits
WHEN NOT MATCHED AND NOT source.remove_row THEN INSERT (
    player_id, activity_date, completed_deposits, completed_withdrawals, net_flow, failed_deposits
) VALUES (
    source.player_id, source.activity_date, source.completed_deposits,
    source.completed_withdrawals, source.net_flow, source.failed_deposits
)
