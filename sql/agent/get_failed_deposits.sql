SELECT
    player_id,
    SUM(failed_deposits) AS failed_deposits
FROM gaming_analytics_gold.player_daily_finance
WHERE activity_date >= CAST(? AS date)
    AND activity_date < CAST(? AS date)
GROUP BY player_id
HAVING SUM(failed_deposits) > 0
ORDER BY failed_deposits DESC, player_id
