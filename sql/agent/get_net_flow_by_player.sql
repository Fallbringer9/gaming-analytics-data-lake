SELECT
    player_id,
    SUM(net_flow) AS net_flow
FROM gaming_analytics_gold.player_daily_finance
WHERE activity_date >= CAST(? AS date)
    AND activity_date < CAST(? AS date)
GROUP BY player_id
ORDER BY net_flow DESC, player_id
