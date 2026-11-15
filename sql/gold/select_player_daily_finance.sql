SELECT
    player_id, activity_date, completed_deposits, completed_withdrawals, net_flow, failed_deposits
FROM gaming_analytics_gold.player_daily_finance
ORDER BY activity_date, player_id
