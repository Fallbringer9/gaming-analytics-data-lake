from unittest.mock import Mock

import pytest

from gaming_analytics_data_lake.agent.athena import QueryResult
from gaming_analytics_data_lake.agent.bedrock import (
    BedrockAnalyticsAgent,
    ToolSelectionError,
)

PARAMETERS = {"start_date": "2026-11-03", "end_date": "2026-11-04"}
NAME = "get_net_flow_by_player"


def tool_use(name=NAME, arguments=PARAMETERS):
    return {"toolUse": {"name": name, "input": arguments}}


@pytest.fixture
def integration():
    client = Mock()
    executor = Mock()
    agent = BedrockAnalyticsAgent(client, "test-model", executor)
    return client, executor, agent


def set_response(client, *content, stop_reason="tool_use"):
    client.converse.return_value = {
        "stopReason": stop_reason,
        "output": {"message": {"content": list(content)}},
    }


def test_executes_one_approved_tool_and_returns_athena_data(integration):
    client, executor, agent = integration
    set_response(client, tool_use())
    result = QueryResult(("net_flow",), [{"net_flow": "120.00"}])
    executor.execute.return_value = result

    response = agent.ask("Flux net par joueur pour le 3 novembre 2026")

    assert response.query_name == NAME
    assert response.parameters == PARAMETERS
    assert response.result is result
    executor.execute.assert_called_once_with(NAME, PARAMETERS)
    config = client.converse.call_args.kwargs
    assert config["modelId"] == "test-model"
    assert {item["toolSpec"]["name"] for item in config["toolConfig"]["tools"]} == {
        "get_player_finance",
        NAME,
    }


@pytest.mark.parametrize(
    ("stop_reason", "blocks"),
    [
        ("end_turn", [{"text": "Aucune donnée"}]),
        ("max_tokens", [tool_use()]),
        ("tool_use", [tool_use("run_sql")]),
        ("tool_use", [tool_use(arguments=["bad"])]),
        ("tool_use", [tool_use(), tool_use()]),
    ],
)
def test_invalid_tool_selection_never_executes(integration, stop_reason, blocks):
    client, executor, agent = integration
    set_response(client, *blocks, stop_reason=stop_reason)

    with pytest.raises(ToolSelectionError):
        agent.ask("Question")

    executor.execute.assert_not_called()


def test_invalid_parameters_are_reported_from_executor(integration):
    client, executor, agent = integration
    set_response(client, tool_use(arguments={"start_date": "wrong"}))
    executor.execute.side_effect = ValueError("Invalid date")

    with pytest.raises(ToolSelectionError, match="paramètres"):
        agent.ask("Question")
