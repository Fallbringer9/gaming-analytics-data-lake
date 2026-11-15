SELECT
    activity_date,
    SUM(completed_deposits) AS completed_deposits,
    SUM(completed_withdrawals) AS completed_withdrawals,
    SUM(net_flow) AS net_flow,
    SUM(failed_deposits) AS failed_deposits
FROM gaming_analytics_gold.player_daily_finance
WHERE activity_date >= CAST(? AS date)
    AND activity_date < CAST(? AS date)
    AND player_id = COALESCE(CAST(? AS varchar), player_id)
GROUP BY activity_date
ORDER BY activity_date
