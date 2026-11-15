import json
import logging
from dataclasses import asdict
from http import HTTPStatus
from pathlib import Path
from typing import Any

from gaming_analytics_data_lake.agent.application import ToolSelectionError
from gaming_analytics_data_lake.agent.ports import QuestionAnswerer

MAX_BODY_BYTES = 16_384
MAX_QUESTION_LENGTH = 1_000
LOGGER = logging.getLogger(__name__)
WEB_DIRECTORY = Path(__file__).with_name("web")
WEB_ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/assets/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


class InvalidRequest(ValueError):
    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status


def _read_question(environ: dict[str, Any]) -> str:
    content_type = environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise InvalidRequest(
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Envoie un corps application/json."
        )

    try:
        length = int(environ.get("CONTENT_LENGTH", ""))
    except ValueError as error:
        raise InvalidRequest(
            HTTPStatus.BAD_REQUEST, "Taille du corps invalide."
        ) from error
    if length <= 0:
        raise InvalidRequest(HTTPStatus.BAD_REQUEST, "La question est requise.")
    if length > MAX_BODY_BYTES:
        raise InvalidRequest(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Requête trop volumineuse."
        )

    try:
        payload = json.loads(environ["wsgi.input"].read(length).decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise InvalidRequest(HTTPStatus.BAD_REQUEST, "Corps JSON invalide.") from error
    if not isinstance(payload, dict) or payload.keys() != {"question"}:
        raise InvalidRequest(
            HTTPStatus.BAD_REQUEST, "Envoie un objet avec le champ question."
        )
    question = payload["question"]
    if not isinstance(question, str) or not question.strip():
        raise InvalidRequest(HTTPStatus.BAD_REQUEST, "La question est requise.")

    question = question.strip()
    if len(question) > MAX_QUESTION_LENGTH:
        raise InvalidRequest(
            HTTPStatus.BAD_REQUEST, "La question dépasse 1 000 caractères."
        )
    return question


def create_application(agent: QuestionAnswerer):
    assets = {
        route: ((WEB_DIRECTORY / filename).read_bytes(), content_type)
        for route, (filename, content_type) in WEB_ROUTES.items()
    }

    def application(environ, start_response):
        path = environ["PATH_INFO"]
        method = environ["REQUEST_METHOD"]
        if path in assets and method in {"GET", "HEAD"}:
            body, content_type = assets[path]
            start_response(
                "200 OK",
                [
                    ("Content-Type", content_type),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-cache"),
                ],
            )
            return [body if method == "GET" else b""]

        extra_headers = []
        try:
            if path in assets:
                extra_headers.append(("Allow", "GET, HEAD"))
                raise InvalidRequest(
                    HTTPStatus.METHOD_NOT_ALLOWED, "Utilise la méthode GET."
                )
            if path != "/api/ask":
                raise InvalidRequest(HTTPStatus.NOT_FOUND, "Route inconnue.")
            if method != "POST":
                extra_headers.append(("Allow", "POST"))
                raise InvalidRequest(
                    HTTPStatus.METHOD_NOT_ALLOWED, "Utilise la méthode POST."
                )

            question = _read_question(environ)
            payload = asdict(agent.ask(question))
            status = HTTPStatus.OK
        except InvalidRequest as error:
            status = error.status
            payload = {"error": {"code": "invalid_request", "message": str(error)}}
        except ToolSelectionError as error:
            status = HTTPStatus.UNPROCESSABLE_ENTITY
            payload = {"error": {"code": "unsupported_question", "message": str(error)}}
        except TimeoutError:
            status = HTTPStatus.GATEWAY_TIMEOUT
            payload = {
                "error": {
                    "code": "timeout",
                    "message": "La requête a dépassé le délai.",
                }
            }
        except Exception as error:  # noqa: BLE001 - Keep internal errors out of HTTP replies.
            LOGGER.error("Question execution failed: %s", type(error).__name__)
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            payload = {
                "error": {
                    "code": "service_error",
                    "message": "Le service n’a pas pu terminer la requête.",
                }
            }

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        start_response(
            f"{status.value} {status.phrase}",
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
                *extra_headers,
            ],
        )
        return [body]

    return application
