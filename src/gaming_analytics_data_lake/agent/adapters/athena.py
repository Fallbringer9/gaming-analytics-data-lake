from datetime import date
from pathlib import Path
from time import monotonic, sleep
from typing import Any

from gaming_analytics_data_lake.agent.domain.catalog import (
    QUERY_PARAMETERS,
    ValidatedQuery,
)
from gaming_analytics_data_lake.agent.domain.models import QueryResult


class AthenaQueryError(RuntimeError):
    """An approved query did not finish successfully."""


def _encode_parameter(value: date | str | int | None) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, date):
        return f"'{value.isoformat()}'"
    return "'" + value.replace("'", "''") + "'"


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

    def execute(self, query: ValidatedQuery) -> QueryResult:
        parameters = [_encode_parameter(value) for value in query.values]
        started = self.client.start_query_execution(
            QueryString=self.queries[query.name],
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
