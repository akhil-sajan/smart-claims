# Smart Claims — Insurance Lakehouse

An end-to-end data engineering + ML project on Databricks: a car-insurance
"smart claims" pipeline that ingests streaming telematics, relational
policy/claim/customer data, and claim photos, transforms them through a
medallion lakehouse, fine-tunes an image model to grade claim-photo damage
severity, runs a rule engine over incoming claims, and surfaces it all in a
dashboard.

Architecture and scope are inspired by the
[Databricks Zero-to-Hero course](https://github.com/datamyselfai/databricks-zero-to-hero-course)
by Thomas Haas — sample data comes from there (see [data/README.md](data/README.md)),
but all pipeline code here is an original implementation, not copied from the
course repo.

See [BUILD_NOTES.md](BUILD_NOTES.md) for the full build plan and current status.

## Architecture

Unity Catalog catalog `smart_claims_dev`:

```
00_landing   — raw landing volumes (claim images, training images, metadata)
01_bronze    — telematics (Kinesis), policy/claim/customer (SQL Server CDC),
               training_images, claim_images, claim_images_meta
02_silver    — cleaned versions of the above + claims_rules (rule engine)
03_gold      — aggregated_telematics, customer_claim_policy,
               customer_claim_policy_telematics, claims_damage_level (model)
```

## Repo layout

```
src/
  01_streaming_ingestion/   Kinesis producer + bronze ingestion
  02_sql_server_ingestion/  SQL Server schema + CDC setup
  03_s3_ingestion/          S3 landing + Auto Loader
  04_medallion_transformation/  bronze -> silver -> gold
  05_machine_learning/      damage classifier + rule engine
  06_consumption/           dashboard + app
data/    sample datasets (gitignored, see data/README.md)
```
