from gaming_analytics_data_lake.agent.domain.catalog import validate_query
from gaming_analytics_data_lake.agent.domain.models import AgentResult
from gaming_analytics_data_lake.agent.ports import QueryExecutor, ToolSelector


class ToolSelectionError(ValueError):
    """A question did not result in an approved query."""


class AnalyticsAgent:
    def __init__(self, selector: ToolSelector, executor: QueryExecutor) -> None:
        self.selector = selector
        self.executor = executor

    def ask(self, question: str) -> AgentResult:
        if not question.strip():
            raise ToolSelectionError("La question est vide.")

        selection = self.selector.select(question)
        if selection is None:
            raise ToolSelectionError(
                "Précise une question du catalogue avec une période et, si nécessaire, un joueur."
            )
        try:
            query = validate_query(selection.name, selection.parameters)
        except ValueError as error:
            raise ToolSelectionError(
                "L’outil ou ses paramètres ne sont pas valides."
            ) from error

        result = self.executor.execute(query)
        return AgentResult(query.name, selection.parameters, result)
