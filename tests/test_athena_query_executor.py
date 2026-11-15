from pathlib import Path
from unittest.mock import Mock

import pytest

from gaming_analytics_data_lake.agent.adapters.athena import (
    AthenaQueryError,
    AthenaQueryExecutor,
)
from gaming_analytics_data_lake.agent.domain.catalog import validate_query

SQL_DIRECTORY = Path(__file__).resolve().parents[1] / "sql" / "agent"
DATES = {"start_date": "2026-11-03", "end_date": "2026-11-04"}


@pytest.fixture
def athena():
    client = Mock()
    client.start_query_execution.return_value = {"QueryExecutionId": "test-id"}
    client.get_query_execution.return_value = {
        "QueryExecution": {"Status": {"State": "SUCCEEDED"}}
    }
    executor = AthenaQueryExecutor(
        client, "test-group", SQL_DIRECTORY, poll_interval_seconds=0
    )
    return client, executor


def test_executor_uses_versioned_sql_and_ordered_parameters(athena):
    client, executor = athena
    client.get_paginator.return_value.paginate.return_value = [
        {
            "ResultSet": {
                "ResultSetMetadata": {
                    "ColumnInfo": [{"Name": "player_id"}, {"Name": "net_flow"}]
                },
                "Rows": [
                    {
                        "Data": [
                            {"VarCharValue": "player_id"},
                            {"VarCharValue": "net_flow"},
                        ]
                    },
                    {"Data": [{"VarCharValue": "P001"}, {"VarCharValue": "120.00"}]},
                ],
            }
        },
        {"ResultSet": {"Rows": [{"Data": [{"VarCharValue": "P002"}, {}]}]}},
    ]

    result = executor.execute(
        validate_query("get_player_finance", {"player_id": "P001", **DATES})
    )

    client.start_query_execution.assert_called_once_with(
        QueryString=(SQL_DIRECTORY / "get_player_finance.sql").read_text(),
        ExecutionParameters=["'P001'", "'2026-11-03'", "'2026-11-04'"],
        WorkGroup="test-group",
    )
    assert result.columns == ("player_id", "net_flow")
    assert result.rows == [
        {"player_id": "P001", "net_flow": "120.00"},
        {"player_id": "P002", "net_flow": None},
    ]


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("arbitrary_sql", DATES),
        ("../gold/select_player_daily_finance", DATES),
        ("get_net_flow_by_player", {**DATES, "extra": "value"}),
        ("get_net_flow_by_player", {"start_date": "2026-11-03"}),
        ("get_net_flow_by_player", {**DATES, "start_date": "20261103"}),
        ("get_net_flow_by_player", {**DATES, "start_date": "2026-02-30"}),
        ("get_net_flow_by_player", {**DATES, "end_date": "2026-11-03"}),
        ("get_player_finance", {**DATES, "player_id": "P001' OR '1'='1"}),
    ],
)
def test_invalid_requests_never_call_athena(athena, name, arguments):
    client, executor = athena

    with pytest.raises(ValueError):
        executor.execute(validate_query(name, arguments))

    client.start_query_execution.assert_not_called()


def test_failed_query_does_not_read_results(athena):
    client, executor = athena
    client.get_query_execution.return_value["QueryExecution"]["Status"]["State"] = (
        "FAILED"
    )

    with pytest.raises(AthenaQueryError, match="FAILED"):
        executor.execute(validate_query("get_net_flow_by_player", DATES))

    client.get_paginator.assert_not_called()


def test_query_timeout_does_not_read_results(athena):
    client, _ = athena
    client.get_query_execution.return_value["QueryExecution"]["Status"]["State"] = (
        "RUNNING"
    )
    executor = AthenaQueryExecutor(
        client, "test-group", SQL_DIRECTORY, timeout_seconds=0
    )

    with pytest.raises(TimeoutError, match="test-id"):
        executor.execute(validate_query("get_net_flow_by_player", DATES))

    client.get_paginator.assert_not_called()


@pytest.mark.parametrize("limit", [True, "5", 0, 101, 2.5])
def test_top_depositor_limit_is_validated(athena, limit):
    client, executor = athena

    with pytest.raises(ValueError, match="limit"):
        executor.execute(
            validate_query("get_top_depositors", {**DATES, "limit": limit})
        )

    client.start_query_execution.assert_not_called()


@pytest.mark.parametrize(
    ("name", "arguments", "last_parameter"),
    [
        ("get_top_depositors", {"limit": 5}, "5"),
        ("get_daily_finance_trend", {}, "NULL"),
        ("get_daily_finance_trend", {"player_id": "P001"}, "'P001'"),
    ],
)
def test_new_query_parameters_are_in_sql_order(athena, name, arguments, last_parameter):
    client, executor = athena
    client.get_paginator.return_value.paginate.return_value = []

    executor.execute(validate_query(name, {**DATES, **arguments}))

    assert client.start_query_execution.call_args.kwargs["ExecutionParameters"] == [
        "'2026-11-03'",
        "'2026-11-04'",
        last_parameter,
    ]


def test_large_deposits_does_not_accept_a_threshold_override(athena):
    client, executor = athena

    with pytest.raises(ValueError, match="Expected parameters"):
        executor.execute(
            validate_query("get_large_deposits", {**DATES, "threshold": 100})
        )

    client.start_query_execution.assert_not_called()
