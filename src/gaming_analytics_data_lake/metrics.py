import csv
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass
class PlayerMetrics:
    net_flow: Decimal = Decimal("0.00")
    failed_deposits: int = 0


@dataclass(frozen=True)
class RejectedTransaction:
    source_file: str
    raw_row: dict[str | None, str | list[str] | None]
    reasons: tuple[str, ...]


def summarize_players(
    players_csv: Path, transactions_csv: Path, *additional_batches: Path
) -> dict[str, PlayerMetrics]:
    """Calculate net flow and failed deposit counts per registered player."""
    return _summarize_players(players_csv, (transactions_csv, *additional_batches))


def summarize_players_with_quarantine(
    players_csv: Path, transactions_csv: Path, *additional_batches: Path
) -> tuple[dict[str, PlayerMetrics], list[RejectedTransaction]]:
    """Calculate metrics from valid transactions and return rejected CSV records."""
    rejected: list[RejectedTransaction] = []
    metrics = _summarize_players(
        players_csv, (transactions_csv, *additional_batches), rejected
    )
    return metrics, rejected


def _summarize_players(
    players_csv: Path,
    batches: tuple[Path, ...],
    rejected: list[RejectedTransaction] | None = None,
) -> dict[str, PlayerMetrics]:
    with players_csv.open(encoding="utf-8", newline="") as players:
        metrics = {row["player_id"]: PlayerMetrics() for row in csv.DictReader(players)}

    for row in _latest_transactions(batches, metrics.keys(), rejected):
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


def _latest_transactions(
    batches: tuple[Path, ...],
    player_ids: AbstractSet[str],
    rejected: list[RejectedTransaction] | None,
) -> list[dict[str, str]]:
    versions: dict[str, tuple[datetime, dict[str, str]]] = {}
    for batch in batches:
        with batch.open(encoding="utf-8", newline="") as transactions:
            rows = csv.DictReader(transactions)
            has_version_fields = {"transaction_id", "updated_at"}.issubset(
                rows.fieldnames or ()
            )
            if rejected is None and not has_version_fields:
                if len(batches) == 1:
                    return list(rows)
                raise ValueError(f"Missing transaction_id or updated_at in {batch}")

            for row in rows:
                if rejected is not None:
                    reasons = _rejection_reasons(row, player_ids)
                    if reasons:
                        rejected.append(RejectedTransaction(batch.name, row, reasons))
                        continue

                transaction_id = row["transaction_id"]
                updated_at = datetime.fromisoformat(row["updated_at"])
                previous = versions.get(transaction_id)
                if previous is None or updated_at > previous[0]:
                    versions[transaction_id] = (updated_at, row)
                elif updated_at == previous[0] and row != previous[1]:
                    raise ValueError(
                        f"Conflicting versions of transaction {transaction_id}"
                    )

    return [row for _, row in versions.values()]


def _rejection_reasons(
    row: dict[str, str | None], player_ids: AbstractSet[str]
) -> tuple[str, ...]:
    reasons = []
    if not (row.get("transaction_id") or "").strip():
        reasons.append("missing_transaction_id")
    player_id = row.get("player_id") or ""
    if not player_id.strip() or player_id not in player_ids:
        reasons.append("unknown_player")

    try:
        amount = Decimal(row.get("amount") or "")
    except InvalidOperation:
        reasons.append("invalid_amount")
    else:
        if not amount.is_finite() or amount <= 0:
            reasons.append("invalid_amount")

    try:
        updated_at = datetime.fromisoformat(row.get("updated_at") or "")
    except ValueError:
        reasons.append("invalid_updated_at")
    else:
        if updated_at.utcoffset() is None:
            reasons.append("invalid_updated_at")

    return tuple(reasons)
