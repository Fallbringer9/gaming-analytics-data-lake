from typing import Protocol

from gaming_analytics_data_lake.agent.domain.catalog import ValidatedQuery
from gaming_analytics_data_lake.agent.domain.models import QueryResult, ToolSelection


class ToolSelector(Protocol):
    def select(self, question: str) -> ToolSelection | None: ...


class QueryExecutor(Protocol):
    def execute(self, query: ValidatedQuery) -> QueryResult: ...
