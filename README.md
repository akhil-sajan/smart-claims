# Smart Claims — Insurance Lakehouse

An end-to-end data engineering + ML project on AWS + Databricks: a car-insurance
"smart claims" pipeline that ingests streaming telematics, relational
policy/claim/customer data, and claim photos, transforms them through a
medallion lakehouse, fine-tunes an image model to grade claim-photo damage
severity, runs a rule engine over incoming claims, and surfaces it all in a
Streamlit app hosted as a Databricks App.

Sample data is a public dataset, not original — see [data/README.md](data/README.md)
for source and layout.

**Status: complete**, all phases below implemented and working end to end
against real AWS/Databricks resources.

## Pipeline

1. **Ingestion**
   - Telematics: simulated driving data replayed into a Kinesis Data Stream,
     consumed into Delta via `read_kinesis()`
   - Policy/claim/customer: real RDS SQL Server, ingested via Lakeflow Connect
     CDC (Change Tracking)
   - Claim photos + training images: uploaded to S3, picked up via Auto Loader
     streaming tables
2. **Medallion transforms**: bronze (raw) → silver (cleaned/typed) → gold
   (aggregated, joined, business-ready)
3. **ML**
   - Rule engine: a rules table of plain-SQL conditions, evaluated against
     every claim to flag suspicious ones
   - Damage-severity classifier: transfer learning on MobileNetV2 over
     labeled accident photos, registered to Unity Catalog via MLflow
4. **Consumption**: a Streamlit app (Databricks App) with a claims dashboard
   and a per-claim investigation view (details, rule flags, photo + predicted
   severity)

## Architecture

Unity Catalog catalog `smart_claims_dev`:

```
00_landing   — raw landing volumes (claim images, training images, metadata)
01_bronze    — telematics (Kinesis), policy/claim/customer (SQL Server CDC),
               training_images, claim_images, claim_images_meta
02_silver    — cleaned versions of the above + claims_rules (rule engine)
03_gold      — aggregated_telematics, customer_claim_policy,
               customer_claim_policy_telematics, claims_damage_level (model),
               claims_flags
```

## Repo layout

```
src/
  01_streaming_ingestion/       kinesis_producer.py — replays telematics into Kinesis
  02_sql_server_ingestion/      lakeflow_utility_script.sql — CDC permission setup
  03_s3_ingestion/              S3 landing + Auto Loader (configured directly in the
                                 Databricks SQL Editor, no local script)
  04_medallion_transformation/  bronze_to_silver.sql, silver_to_gold.sql
  05_machine_learning/          claims_rules_setup.sql, rule_engine.py,
                                 fix_rule_descriptions.sql, damage_classifier.py
  06_consumption/app/           app.py, app.yaml, requirements.txt — the Streamlit app
data/    sample datasets (gitignored, see data/README.md)
```
