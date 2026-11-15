import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from time import monotonic, sleep
from typing import Any

QUERY_PARAMETERS = {
    "get_player_finance": ("player_id", "start_date", "end_date"),
    "get_net_flow_by_player": ("start_date", "end_date"),
}

ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
PLAYER_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


class AthenaQueryError(RuntimeError):
    """An approved query did not finish successfully."""


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: list[dict[str, str | None]]


def _read_date(value: object, name: str) -> date:
    if not isinstance(value, str) or not ISO_DATE.fullmatch(value):
        raise ValueError(f"{name} must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a valid calendar date") from error


def _execution_parameters(
    names: tuple[str, ...], arguments: Mapping[str, object]
) -> list[str]:
    if arguments.keys() != set(names):
        raise ValueError(f"Expected parameters: {', '.join(names)}")

    start_date = _read_date(arguments["start_date"], "start_date")
    end_date = _read_date(arguments["end_date"], "end_date")
    if start_date >= end_date:
        raise ValueError("end_date must be later than start_date")

    parameters = [f"'{start_date.isoformat()}'", f"'{end_date.isoformat()}'"]
    if "player_id" in names:
        player_id = arguments["player_id"]
        if not isinstance(player_id, str) or not PLAYER_ID.fullmatch(player_id):
            raise ValueError("Invalid player_id")
        parameters.insert(0, f"'{player_id}'")
    return parameters


class AthenaQueryExecutor:
    """Execute the approved Gold queries using a region-specific Athena client."""

    def __init__(
        self,
        client: Any,
        workgroup: str,
        sql_directory: Path,
        *,
        timeout_seconds: float = 30,
        poll_interval_seconds: float = 0.5,
    ) -> None:
        self.client = client
        self.workgroup = workgroup
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.queries = {
            name: (sql_directory / f"{name}.sql").read_text(encoding="utf-8")
            for name in QUERY_PARAMETERS
        }

    def execute(self, name: str, arguments: Mapping[str, object]) -> QueryResult:
        if name not in QUERY_PARAMETERS:
            raise ValueError("Unknown Athena query")

        parameters = _execution_parameters(QUERY_PARAMETERS[name], arguments)
        started = self.client.start_query_execution(
            QueryString=self.queries[name],
            ExecutionParameters=parameters,
            WorkGroup=self.workgroup,
        )
        execution_id = started["QueryExecutionId"]
        self._wait_for_query(execution_id)
        return self._read_results(execution_id)

    def _wait_for_query(self, execution_id: str) -> None:
        deadline = monotonic() + self.timeout_seconds
        while True:
            response = self.client.get_query_execution(QueryExecutionId=execution_id)
            state = response["QueryExecution"]["Status"]["State"]
            if state == "SUCCEEDED":
                return
            if state in {"FAILED", "CANCELLED"}:
                raise AthenaQueryError(f"Athena query {execution_id}: {state}")

            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Athena query {execution_id} timed out")
            sleep(min(self.poll_interval_seconds, remaining))

    def _read_results(self, execution_id: str) -> QueryResult:
        pages = self.client.get_paginator("get_query_results").paginate(
            QueryExecutionId=execution_id
        )
        columns: tuple[str, ...] = ()
        rows: list[dict[str, str | None]] = []
        for index, page in enumerate(pages):
            result = page["ResultSet"]
            entries = result["Rows"]
            if index == 0:
                columns = tuple(
                    item["Name"] for item in result["ResultSetMetadata"]["ColumnInfo"]
                )
                entries = entries[1:]  # Athena sends the column header on page one.

            for entry in entries:
                cells = entry["Data"]
                rows.append(
                    {
                        name: cells[i].get("VarCharValue") if i < len(cells) else None
                        for i, name in enumerate(columns)
                    }
                )

        return QueryResult(columns, rows)
