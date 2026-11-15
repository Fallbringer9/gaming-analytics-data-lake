import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

QUERY_PARAMETERS = {
    "get_player_finance": ("player_id", "start_date", "end_date"),
    "get_net_flow_by_player": ("start_date", "end_date"),
    "get_finance_overview": ("start_date", "end_date"),
    "get_daily_finance_trend": ("start_date", "end_date", "player_id"),
    "get_failed_deposits": ("start_date", "end_date"),
    "get_top_depositors": ("start_date", "end_date", "limit"),
    "get_max_deposit": ("start_date", "end_date"),
    "get_large_deposits": ("start_date", "end_date"),
}
OPTIONAL_QUERY_PARAMETERS = {"get_daily_finance_trend": frozenset({"player_id"})}
MAX_RANKING_ROWS = 100

ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
PLAYER_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


TOOL_DESCRIPTIONS = {
    "get_player_finance": "Donne les indicateurs financiers d’un joueur identifié.",
    "get_net_flow_by_player": "Donne le flux net par joueur, tous joueurs confondus.",
    "get_finance_overview": "Bilan financier global de la période, tous joueurs confondus.",
    "get_daily_finance_trend": "Évolution des indicateurs jour par jour, avec filtre joueur facultatif.",
    "get_failed_deposits": "Liste les joueurs ayant eu des dépôts échoués, triée par nombre d’échecs.",
    "get_top_depositors": "Classe les joueurs par montant total des dépôts validés sur la période.",
    "get_max_deposit": "Trouve le plus gros dépôt individuel validé, avec le joueur et la date.",
    "get_large_deposits": "Liste les dépôts individuels validés strictement supérieurs à 10 000.",
}
PARAMETER_DESCRIPTIONS = {
    "player_id": "Identifiant du joueur, par exemple P001.",
    "start_date": "Premier jour inclus, au format AAAA-MM-JJ.",
    "end_date": "Premier jour exclu, au format AAAA-MM-JJ.",
    "limit": "Nombre de joueurs demandé dans le classement.",
}


@dataclass(frozen=True)
class ValidatedQuery:
    name: str
    values: tuple[date | str | int | None, ...]


def _read_date(value: object, name: str) -> date:
    if not isinstance(value, str) or not ISO_DATE.fullmatch(value):
        raise ValueError(f"{name} must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a valid calendar date") from error


def validate_query(name: str, arguments: Mapping[str, object]) -> ValidatedQuery:
    if name not in QUERY_PARAMETERS:
        raise ValueError("Unknown query")

    names = QUERY_PARAMETERS[name]
    required = set(names) - OPTIONAL_QUERY_PARAMETERS.get(name, frozenset())
    if not required <= arguments.keys() <= set(names):
        raise ValueError(f"Expected parameters: {', '.join(names)}")

    start_date = _read_date(arguments["start_date"], "start_date")
    end_date = _read_date(arguments["end_date"], "end_date")
    if start_date >= end_date:
        raise ValueError("end_date must be later than start_date")

    values: dict[str, date | str | int | None] = {
        "start_date": start_date,
        "end_date": end_date,
    }
    if "player_id" in names:
        player_id = arguments.get("player_id")
        if "player_id" not in arguments:
            values["player_id"] = None
        elif isinstance(player_id, str) and PLAYER_ID.fullmatch(player_id):
            values["player_id"] = player_id
        else:
            raise ValueError("Invalid player_id")

    if "limit" in names:
        limit = arguments["limit"]
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= MAX_RANKING_ROWS
        ):
            raise ValueError(
                f"limit must be an integer between 1 and {MAX_RANKING_ROWS}"
            )
        values["limit"] = limit

    return ValidatedQuery(name, tuple(values[parameter] for parameter in names))
