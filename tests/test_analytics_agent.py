from datetime import date
from unittest.mock import Mock

import pytest

from gaming_analytics_data_lake.agent.application import (
    AnalyticsAgent,
    ToolSelectionError,
)
from gaming_analytics_data_lake.agent.domain.catalog import ValidatedQuery
from gaming_analytics_data_lake.agent.domain.models import QueryResult, ToolSelection
from gaming_analytics_data_lake.agent.ports import QueryExecutor, ToolSelector

DATES = {"start_date": "2026-11-03", "end_date": "2026-11-04"}


def test_case_validates_the_selection_then_executes_through_its_port():
    selector = Mock(spec=ToolSelector)
    executor = Mock(spec=QueryExecutor)
    selector.select.return_value = ToolSelection(
        "get_top_depositors", {**DATES, "limit": 1}
    )
    expected = QueryResult(("player_id",), [{"player_id": "P001"}])
    executor.execute.return_value = expected

    result = AnalyticsAgent(selector, executor).ask("Top des déposants")

    executor.execute.assert_called_once_with(
        ValidatedQuery("get_top_depositors", (date(2026, 11, 3), date(2026, 11, 4), 1))
    )
    assert result.query_name == "get_top_depositors"
    assert result.parameters == {**DATES, "limit": 1}
    assert result.result is expected


@pytest.mark.parametrize(
    "selection",
    [
        None,
        ToolSelection("arbitrary_sql", DATES),
        ToolSelection("get_net_flow_by_player", {**DATES, "end_date": "invalid"}),
        ToolSelection("get_large_deposits", {**DATES, "threshold": 100}),
    ],
)
def test_case_does_not_execute_invalid_selections(selection):
    selector = Mock(spec=ToolSelector)
    executor = Mock(spec=QueryExecutor)
    selector.select.return_value = selection

    with pytest.raises(ToolSelectionError):
        AnalyticsAgent(selector, executor).ask("Question")

    executor.execute.assert_not_called()
