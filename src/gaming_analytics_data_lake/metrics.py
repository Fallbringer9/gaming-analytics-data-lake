import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass
class PlayerMetrics:
    net_flow: Decimal = Decimal("0.00")
    failed_deposits: int = 0


def summarize_players(
    players_csv: Path, transactions_csv: Path
) -> dict[str, PlayerMetrics]:
    """Calculate net flow and failed deposit counts per registered player."""
    with players_csv.open(encoding="utf-8", newline="") as players:
        metrics = {row["player_id"]: PlayerMetrics() for row in csv.DictReader(players)}

    with transactions_csv.open(encoding="utf-8", newline="") as transactions:
        for row in csv.DictReader(transactions):
            player_id = row["player_id"]
            if player_id not in metrics:
                raise ValueError(f"Unknown player_id: {player_id}")

            player = metrics[player_id]
            match row["transaction_type"], row["status"]:
                case "deposit", "completed":
                    player.net_flow += Decimal(row["amount"])
                case "withdrawal", "completed":
                    player.net_flow -= Decimal(row["amount"])
                case "deposit", "failed":
                    player.failed_deposits += 1

    return metrics
