from decimal import Decimal
from pathlib import Path

import pytest

from gaming_analytics_data_lake.metrics import PlayerMetrics, summarize_players

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_summarize_players_uses_completed_transactions_for_net_flow():
    metrics = summarize_players(DATA_DIR / "players.csv", DATA_DIR / "transactions.csv")

    assert metrics == {
        "P001": PlayerMetrics(net_flow=Decimal("70.00"), failed_deposits=1),
        "P002": PlayerMetrics(net_flow=Decimal("-15.00"), failed_deposits=0),
    }


def test_summarize_players_rejects_unknown_player(tmp_path):
    transactions = tmp_path / "transactions.csv"
    transactions.write_text(
        "player_id,transaction_type,amount,status\nunknown,deposit,10.00,completed\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown player_id: unknown"):
        summarize_players(DATA_DIR / "players.csv", transactions)
