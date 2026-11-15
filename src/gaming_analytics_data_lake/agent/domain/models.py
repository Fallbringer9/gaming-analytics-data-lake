from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSelection:
    name: str
    parameters: dict[str, object]


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: list[dict[str, str | None]]


@dataclass(frozen=True)
class AgentResult:
    query_name: str
    parameters: dict[str, object]
    result: QueryResult
