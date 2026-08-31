"""Replay sample telematics parquet data into the smart-claims-telematics
Kinesis stream, simulating live driving events from vehicles in the field.

Run from the project root:
    python src/01_streaming_ingestion/kinesis_producer.py
"""
import json

import boto3
import duckdb

STREAM_NAME = "smart-claims-telematics"
REGION = "us-east-1"
BATCH_SIZE = 500


def main():
    kinesis = boto3.client("kinesis", region_name=REGION)
    con = duckdb.connect()
    rows = con.execute(
        "SELECT chassis_no, latitude, longitude, "
        "CAST(event_timestamp AS VARCHAR) AS event_timestamp, speed "
        "FROM read_parquet('data/telematics/*.parquet') "
        "ORDER BY event_timestamp"
    ).fetchall()

    total = len(rows)
    print(f"Loaded {total} telematics records. Sending to Kinesis stream '{STREAM_NAME}'...")

    sent = 0
    for i in range(0, total, BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        records = []
        for chassis_no, lat, lon, ts, speed in batch:
            payload = {
                "chassis_no": chassis_no,
                "latitude": lat,
                "longitude": lon,
                "event_timestamp": ts,
                "speed": speed,
            }
            records.append(
                {
                    "Data": json.dumps(payload).encode("utf-8"),
                    "PartitionKey": chassis_no,
                }
            )

        response = kinesis.put_records(StreamName=STREAM_NAME, Records=records)
        failed = response.get("FailedRecordCount", 0)
        sent += len(records) - failed
        if failed:
            print(f"  warning: {failed} records failed in this batch")
        if (i // BATCH_SIZE) % 20 == 0:
            print(f"  sent {sent}/{total}...")

    print(f"Done. Sent {sent}/{total} records.")


if __name__ == "__main__":
    main()
