import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

import boto3

from gaming_analytics_data_lake.agent.adapters.athena import AthenaQueryExecutor
from gaming_analytics_data_lake.agent.adapters.bedrock import BedrockToolSelector
from gaming_analytics_data_lake.agent.application import (
    AnalyticsAgent,
    ToolSelectionError,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Interroger les indicateurs Gold.")
    parser.add_argument("question")
    args = parser.parse_args()

    athena_region = os.getenv("ATHENA_REGION", "eu-west-3")
    bedrock_region = os.getenv("BEDROCK_REGION")
    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not bedrock_region or not model_id:
        parser.error("Définir BEDROCK_REGION et BEDROCK_MODEL_ID.")

    session = boto3.Session()
    executor = AthenaQueryExecutor(
        session.client("athena", region_name=athena_region),
        os.getenv("ATHENA_WORKGROUP", "gaming-analytics-gold"),
        Path("sql/agent"),
    )
    selector = BedrockToolSelector(
        session.client("bedrock-runtime", region_name=bedrock_region), model_id
    )
    agent = AnalyticsAgent(selector, executor)
    try:
        result = agent.ask(args.question)
    except ToolSelectionError as error:
        parser.error(str(error))
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
