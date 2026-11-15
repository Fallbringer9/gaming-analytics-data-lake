SELECT player_id, activity_date, amount
FROM gaming_analytics_gold.completed_deposits
WHERE activity_date >= CAST(? AS date)
    AND activity_date < CAST(? AS date)
ORDER BY amount DESC, activity_date, player_id, transaction_id
LIMIT 1
