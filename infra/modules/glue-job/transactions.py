import json
import re
import sys
from tempfile import SpooledTemporaryFile

import boto3
from awsglue.utils import getResolvedOptions
from pyspark import TaskContext
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

TRANSACTION_FIELDS = (
    "transaction_id",
    "player_id",
    "transaction_type",
    "amount",
    "status",
    "created_at",
    "updated_at",
)

ISO_TIMESTAMP = (
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)
VERSION_KEYS = ["transaction_id", "parsed_updated_at"]


def version_payload():
    return F.struct(
        "player_id", "transaction_type", "parsed_amount", "status", "parsed_created_at"
    )


args = getResolvedOptions(
    sys.argv, ["bronze_bucket", "database", "players_batch", "batch_id"]
)
for name in ("players_batch", "batch_id", "JOB_RUN_ID"):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args[name]):
        raise ValueError(f"Invalid {name}")

spark = SparkSession.builder.getOrCreate()
spark.conf.set("spark.sql.session.timeZone", "UTC")
bronze = f"s3://{args['bronze_bucket']}"
batch = args["batch_id"]
table = f"glue_catalog.{args['database']}.transactions"
players = (
    spark.read.option("header", True)
    .csv(f"{bronze}/bronze/players/batch_id={args['players_batch']}/")
    .select("player_id")
    .distinct()
    .withColumn("known_player", F.lit(True))
)
raw = (
    spark.read.option("header", True)
    .csv(f"{bronze}/bronze/transactions/batch_id={batch}/")
    .withColumn("source_file", F.input_file_name())
)
raw = raw.withColumn(
    "raw_row",
    F.to_json(
        F.struct(*(F.col(field) for field in raw.columns if field != "source_file")),
        {"ignoreNullFields": "false"},
    ),
)
for field in TRANSACTION_FIELDS:
    if field not in raw.columns:
        raw = raw.withColumn(field, F.lit(None).cast("string"))

checked = (
    raw.join(players, "player_id", "left")
    .withColumn("parsed_amount", F.expr("try_cast(trim(amount) AS DECIMAL(18, 2))"))
    .withColumn("parsed_created_at", F.try_to_timestamp("created_at"))
    .withColumn("parsed_updated_at", F.try_to_timestamp("updated_at"))
    .withColumn(
        "reasons",
        F.array_compact(
            F.array(
                F.when(
                    F.coalesce(F.trim("transaction_id"), F.lit("")) == "",
                    "missing_transaction_id",
                ),
                F.when(
                    F.col("known_player").isNull()
                    | (F.coalesce(F.trim("player_id"), F.lit("")) == ""),
                    "unknown_player",
                ),
                F.when(
                    ~F.coalesce(
                        F.trim("amount").rlike(r"^\+?(?:\d+(?:\.\d{1,2})?|\.\d{1,2})$"),
                        F.lit(False),
                    )
                    | F.col("parsed_amount").isNull()
                    | (F.col("parsed_amount") <= 0),
                    "invalid_amount",
                ),
                F.when(
                    F.col("parsed_created_at").isNull()
                    | ~F.col("created_at").rlike(ISO_TIMESTAMP),
                    "invalid_created_at",
                ),
                F.when(
                    ~F.coalesce(
                        F.col("transaction_type").isin("deposit", "withdrawal"),
                        F.lit(False),
                    ),
                    "invalid_transaction_type",
                ),
                F.when(
                    ~F.coalesce(
                        F.col("status").isin("completed", "failed"), F.lit(False)
                    ),
                    "invalid_status",
                ),
                F.when(
                    F.col("parsed_updated_at").isNull()
                    | ~F.col("updated_at").rlike(r"(?:Z|[+-]\d{2}:\d{2})$"),
                    "invalid_updated_at",
                ),
            )
        ),
    )
    .cache()
)
versions = checked.where(F.size("reasons") == 0).select(
    *VERSION_KEYS, version_payload().alias("incoming_payload")
)
conflicts = (
    versions.groupBy(*VERSION_KEYS)
    .agg(F.count_distinct("incoming_payload").alias("payload_count"))
    .where(F.col("payload_count") > 1)
    .select(*VERSION_KEYS)
)
if spark.catalog.tableExists(table):
    existing = spark.table(table).select(
        "transaction_id",
        F.col("updated_at").alias("parsed_updated_at"),
        "player_id",
        "transaction_type",
        F.col("amount").alias("parsed_amount"),
        "status",
        F.try_to_timestamp("created_at").alias("parsed_created_at"),
    )
    existing = existing.select(*VERSION_KEYS, version_payload().alias("silver_payload"))
    silver_conflicts = (
        versions.join(existing, VERSION_KEYS)
        .where(~F.col("incoming_payload").eqNullSafe(F.col("silver_payload")))
        .select(*VERSION_KEYS)
    )
    conflicts = conflicts.union(silver_conflicts)

checked = (
    checked.join(
        conflicts.distinct().withColumn("version_conflict", F.lit(True)),
        VERSION_KEYS,
        "left",
    )
    .withColumn(
        "reasons",
        F.when(
            (F.size("reasons") == 0) & F.col("version_conflict"),
            F.array(F.lit("conflicting_transaction_version")),
        ).otherwise(F.col("reasons")),
    )
    .cache()
)
rejected = checked.where(F.size("reasons") > 0)
rejected_count = rejected.count()
if rejected_count:
    reject_bucket = args["bronze_bucket"]
    reject_prefix = (
        f"quarantine/transactions/glue/batch_id={batch}/run_id={args['JOB_RUN_ID']}"
    )

    def write_rejected_partition(rows):
        partition = TaskContext.get().partitionId()
        with SpooledTemporaryFile(max_size=8 * 1024 * 1024) as body:
            for row in rows:
                body.write(
                    json.dumps(row.asDict(), ensure_ascii=False).encode() + b"\n"
                )

            if body.tell():
                body.seek(0)
                boto3.client("s3").upload_fileobj(
                    body,
                    reject_bucket,
                    f"{reject_prefix}/part-{partition:05d}.jsonl",
                    ExtraArgs={
                        "ContentType": "application/x-ndjson",
                        "ServerSideEncryption": "AES256",
                    },
                )

    rejected.select("source_file", "raw_row", "reasons").foreachPartition(
        write_rejected_partition
    )


valid = (
    checked.where(F.size("reasons") == 0)
    .select(
        "transaction_id",
        "player_id",
        "transaction_type",
        F.col("parsed_amount").alias("amount"),
        "status",
        "created_at",
        F.col("parsed_updated_at").alias("updated_at"),
    )
    .distinct()
)
window = Window.partitionBy("transaction_id").orderBy(
    F.desc("updated_at"), F.asc("created_at")
)
latest = valid.withColumn("version_rank", F.row_number().over(window))
latest = latest.where("version_rank = 1").drop("version_rank")
valid_count = latest.count()
if valid_count:
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            transaction_id STRING,
            player_id STRING,
            transaction_type STRING,
            amount DECIMAL(18, 2),
            status STRING,
            created_at STRING,
            updated_at TIMESTAMP
        ) USING iceberg TBLPROPERTIES ('format-version' = '2')
        """
    )
    # Cut file-provenance expressions from the source plan before Iceberg's MERGE.
    latest.localCheckpoint(eager=True).createOrReplaceTempView("batch_transactions")
    spark.sql(
        f"""
        MERGE INTO {table} AS target
        USING batch_transactions AS source
        ON target.transaction_id = source.transaction_id
        WHEN MATCHED AND source.updated_at > target.updated_at THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        """
    )

print(
    f"batch_id={batch} valid_transactions={valid_count} rejected_transactions={rejected_count}"
)
