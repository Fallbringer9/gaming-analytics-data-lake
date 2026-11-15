WITH totals AS (
    SELECT
        player_id,
        SUM(completed_deposits) AS completed_deposits
    FROM gaming_analytics_gold.player_daily_finance
    WHERE activity_date >= CAST(? AS date)
        AND activity_date < CAST(? AS date)
    GROUP BY player_id
    HAVING SUM(completed_deposits) > 0
),
ranked AS (
    SELECT
        player_id,
        completed_deposits,
        ROW_NUMBER() OVER (ORDER BY completed_deposits DESC, player_id) AS deposit_rank
    FROM totals
)
SELECT player_id, completed_deposits
FROM ranked
WHERE deposit_rank <= CAST(? AS integer)
ORDER BY deposit_rank
