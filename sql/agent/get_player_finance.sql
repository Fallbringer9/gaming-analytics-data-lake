SELECT
    player_id,
    SUM(completed_deposits) AS completed_deposits,
    SUM(completed_withdrawals) AS completed_withdrawals,
    SUM(net_flow) AS net_flow,
    SUM(failed_deposits) AS failed_deposits
FROM gaming_analytics_gold.player_daily_finance
WHERE player_id = ?
    AND activity_date >= CAST(? AS date)
    AND activity_date < CAST(? AS date)
GROUP BY player_id
