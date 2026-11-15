from decimal import Decimal
from pathlib import Path

import pytest

from gaming_analytics_data_lake.metrics import (
    PlayerMetrics,
    summarize_players,
    summarize_players_with_quarantine,
)

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


def test_summarize_players_uses_latest_transaction_and_handles_replay(tmp_path):
    players = DATA_DIR / "players.csv"
    initial_batch = DATA_DIR / "transactions.csv"
    update = tmp_path / "update.csv"
    update.write_text(
        "transaction_id,player_id,transaction_type,amount,status,created_at,updated_at\n"
        "T003,P001,deposit,50.00,completed,2026-11-03T11:00:00Z,2026-11-03T12:00:00Z\n",
        encoding="utf-8",
    )

    expected = {
        "P001": PlayerMetrics(net_flow=Decimal("120.00"), failed_deposits=0),
        "P002": PlayerMetrics(net_flow=Decimal("-15.00"), failed_deposits=0),
    }
    assert summarize_players(players, initial_batch, update) == expected
    assert summarize_players(players, initial_batch, update, update) == expected
    assert summarize_players(players, update, initial_batch) == expected


def test_invalid_update_is_quarantined_and_preserves_previous_version(tmp_path):
    update = tmp_path / "update.csv"
    update.write_text(
        "transaction_id,player_id,transaction_type,amount,status,updated_at\n"
        "T003,P001,deposit,abc,completed,2026-11-03T12:00:00Z\n",
        encoding="utf-8",
    )

    metrics, rejected = summarize_players_with_quarantine(
        DATA_DIR / "players.csv", DATA_DIR / "transactions.csv", update
    )

    assert metrics["P001"] == PlayerMetrics(
        net_flow=Decimal("70.00"), failed_deposits=1
    )
    assert len(rejected) == 1
    assert rejected[0].source_file == "update.csv"
    assert rejected[0].raw_row["transaction_id"] == "T003"
    assert rejected[0].raw_row["amount"] == "abc"
    assert rejected[0].reasons == ("invalid_amount",)


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "0", "-1", ""])
def test_quarantine_reports_all_reasons_for_a_row(tmp_path, amount):
    batch = tmp_path / "invalid.csv"
    batch.write_text(
        "transaction_id,player_id,transaction_type,amount,status,updated_at\n"
        f",P999,deposit,{amount},completed,2026-11-03T12:00:00\n",
        encoding="utf-8",
    )

    metrics, rejected = summarize_players_with_quarantine(
        DATA_DIR / "players.csv", batch
    )

    assert metrics["P001"] == PlayerMetrics()
    assert len(rejected) == 1
    assert rejected[0].reasons == (
        "missing_transaction_id",
        "unknown_player",
        "invalid_amount",
        "invalid_updated_at",
    )
