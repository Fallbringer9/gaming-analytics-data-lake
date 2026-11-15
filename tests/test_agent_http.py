import io
import json
from unittest.mock import Mock
from wsgiref.util import setup_testing_defaults
from wsgiref.validate import validator

import pytest

from gaming_analytics_data_lake.agent.adapters.http import create_application
from gaming_analytics_data_lake.agent.application import ToolSelectionError
from gaming_analytics_data_lake.agent.domain.models import AgentResult, QueryResult
from gaming_analytics_data_lake.agent.ports import QuestionAnswerer


def request(
    agent, body, *, path="/api/ask", method="POST", content_type="application/json"
):
    environ = {}
    setup_testing_defaults(environ)
    environ.update(
        {
            "PATH_INFO": path,
            "REQUEST_METHOD": method,
            "CONTENT_TYPE": content_type,
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": io.BytesIO(body),
            "QUERY_STRING": "",
        }
    )
    start_response = Mock()
    response = validator(create_application(agent))(environ, start_response)
    try:
        data = json.loads(b"".join(response))
    finally:
        response.close()
    status, headers = start_response.call_args.args[:2]
    return int(status.split()[0]), dict(headers), data


@pytest.mark.parametrize("rows", [[], [{"amount": "10000.01"}]])
def test_api_returns_the_tool_parameters_and_result(rows):
    agent = Mock(spec=QuestionAnswerer)
    agent.ask.return_value = AgentResult(
        "get_large_deposits",
        {"start_date": "2026-11-04", "end_date": "2026-11-11"},
        QueryResult(("amount",), rows),
    )

    status, headers, payload = request(
        agent, json.dumps({"question": " Quels dépôts ? "}).encode()
    )

    assert status == 200
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert headers["Cache-Control"] == "no-store"
    assert payload == {
        "query_name": "get_large_deposits",
        "parameters": {"start_date": "2026-11-04", "end_date": "2026-11-11"},
        "result": {"columns": ["amount"], "rows": rows},
    }
    agent.ask.assert_called_once_with("Quels dépôts ?")


@pytest.mark.parametrize(
    ("body", "options", "expected"),
    [
        (b'{"question":""}', {}, 400),
        (b'{"question":42}', {}, 400),
        (b'{"question":"x","sql":"SELECT 1"}', {}, 400),
        (b"{", {}, 400),
        (b"x" * 16_385, {}, 413),
        (b'{"question":"x"}', {"content_type": "text/plain"}, 415),
        (b"", {"path": "/other"}, 404),
        (b"", {"method": "GET"}, 405),
    ],
)
def test_invalid_requests_do_not_call_the_agent(body, options, expected):
    agent = Mock(spec=QuestionAnswerer)
    status, headers, payload = request(agent, body, **options)

    assert status == expected
    assert payload["error"]["code"] == "invalid_request"
    if status == 405:
        assert headers["Allow"] == "POST"
    agent.ask.assert_not_called()


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (ToolSelectionError("Précise la période."), 422, "unsupported_question"),
        (TimeoutError("AWS execution ID"), 504, "timeout"),
        (RuntimeError("AWS execution ID"), 500, "service_error"),
    ],
)
def test_api_maps_errors_to_safe_json(error, status, code):
    agent = Mock(spec=QuestionAnswerer)
    agent.ask.side_effect = error

    actual, _, payload = request(agent, b'{"question":"Question"}')

    assert actual == status
    assert payload["error"]["code"] == code
    assert "AWS execution ID" not in payload["error"]["message"]
