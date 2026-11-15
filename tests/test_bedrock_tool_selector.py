from unittest.mock import Mock

import pytest

from gaming_analytics_data_lake.agent.adapters.bedrock import BedrockToolSelector
from gaming_analytics_data_lake.agent.domain.models import ToolSelection

PARAMETERS = {"start_date": "2026-11-03", "end_date": "2026-11-04"}
NAME = "get_net_flow_by_player"


def tool_use(name=NAME, arguments=PARAMETERS):
    return {"toolUse": {"name": name, "input": arguments}}


@pytest.fixture
def bedrock():
    client = Mock()
    return client, BedrockToolSelector(client, "test-model")


def set_response(client, *content, stop_reason="tool_use"):
    client.converse.return_value = {
        "stopReason": stop_reason,
        "output": {"message": {"content": list(content)}},
    }


def test_reads_one_tool_selection_and_sends_the_catalog(bedrock):
    client, selector = bedrock
    set_response(client, tool_use())

    assert selector.select("Flux net par joueur") == ToolSelection(NAME, PARAMETERS)

    config = client.converse.call_args.kwargs
    assert config["modelId"] == "test-model"
    schemas = {
        item["toolSpec"]["name"]: item["toolSpec"]["inputSchema"]["json"]
        for item in config["toolConfig"]["tools"]
    }
    assert set(schemas) == {
        "get_player_finance",
        NAME,
        "get_finance_overview",
        "get_daily_finance_trend",
        "get_failed_deposits",
        "get_top_depositors",
        "get_max_deposit",
        "get_large_deposits",
    }
    assert "player_id" not in schemas["get_daily_finance_trend"]["required"]
    assert schemas["get_top_depositors"]["properties"]["limit"]["type"] == "integer"
    assert "threshold" not in schemas["get_large_deposits"]["properties"]


@pytest.mark.parametrize(
    ("stop_reason", "blocks"),
    [
        ("end_turn", [{"text": "Aucune donnée"}]),
        ("max_tokens", [tool_use()]),
        ("tool_use", [tool_use(arguments=["bad"])]),
        ("tool_use", [tool_use(), tool_use()]),
    ],
)
def test_unusable_responses_do_not_return_a_selection(bedrock, stop_reason, blocks):
    client, selector = bedrock
    set_response(client, *blocks, stop_reason=stop_reason)

    assert selector.select("Question") is None
