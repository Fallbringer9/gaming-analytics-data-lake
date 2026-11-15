import os
from pathlib import Path

import boto3

from gaming_analytics_data_lake.agent.adapters.athena import AthenaQueryExecutor
from gaming_analytics_data_lake.agent.adapters.bedrock import BedrockToolSelector
from gaming_analytics_data_lake.agent.application import AnalyticsAgent


def build_agent() -> AnalyticsAgent:
    athena_region = os.getenv("ATHENA_REGION", "eu-west-3")
    bedrock_region = os.getenv("BEDROCK_REGION")
    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not bedrock_region or not model_id:
        raise ValueError("Définir BEDROCK_REGION et BEDROCK_MODEL_ID.")

    session = boto3.Session()
    executor = AthenaQueryExecutor(
        session.client("athena", region_name=athena_region),
        os.getenv("ATHENA_WORKGROUP", "gaming-analytics-gold"),
        Path("sql/agent"),
    )
    selector = BedrockToolSelector(
        session.client("bedrock-runtime", region_name=bedrock_region), model_id
    )
    return AnalyticsAgent(selector, executor)
