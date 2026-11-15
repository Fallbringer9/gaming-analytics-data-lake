import argparse
import json
from dataclasses import asdict

from gaming_analytics_data_lake.agent.application import ToolSelectionError
from gaming_analytics_data_lake.agent.bootstrap import build_agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Interroger les indicateurs Gold.")
    parser.add_argument("question")
    args = parser.parse_args()

    try:
        agent = build_agent()
    except ValueError as error:
        parser.error(str(error))

    try:
        result = agent.ask(args.question)
    except ToolSelectionError as error:
        parser.error(str(error))
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
