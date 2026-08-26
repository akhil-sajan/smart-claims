# Build runbook

Original implementation, architecture/scope inspired by
[datamyselfai/databricks-zero-to-hero-course](https://github.com/datamyselfai/databricks-zero-to-hero-course)
("Databricks End-To-End Project 2026 | Zero-To-Hero"). Code is written from
scratch here, not copied — the course repo is kept locally at
`C:\Users\akhil\Documents\databricks-zero-to-hero-course` purely as a reference
for architecture/table names, not as a source to paste from.

## Status

- [x] Phase 0a: AWS CLI + Databricks CLI installed locally (winget)
- [x] Phase 0b: AWS (`aws sts get-caller-identity` — account 265544358795) and
      Databricks (`dbc-ab976425-7930.cloud.databricks.com`) both authenticated
- [~] Phase 1: AWS resources — S3 bucket + IAM role done; Kinesis deferred to
      Phase 4 (see below)
- [ ] Phase 2: Databricks Unity Catalog setup (catalog/schemas/volumes)
- [ ] Phase 3: SQL Server (real RDS instance, per your choice) + CDC
- [ ] Phase 4: Data ingestion (S3 upload, Kinesis producer)
- [ ] Phase 5: Medallion transforms (bronze -> silver -> gold)
- [ ] Phase 6: ML (damage classifier + rule engine)
- [ ] Phase 7: Consumption (dashboard + app)

## Target architecture (Unity Catalog catalog: `smart_claims_dev`)

```
00_landing   — Volumes: claims/images, claims/metadata, training_imgs (raw S3 landing)
01_bronze    — telematics (Kinesis), policy/claim/customer (SQL Server CDC),
               training_images, claim_images, claim_images_meta
02_silver    — cleaned versions of the above + claims_rules (rule engine table)
03_gold      — aggregated_telematics, customer_claim_policy,
               customer_claim_policy_telematics, claims_damage_level (registered model)
```

## Decisions made so far

- SQL Server: real RDS SQL Server (matches Lakeflow Connect CDC properly, costs money)
- ML compute: no strong preference yet — default to starting on CPU to get the
  pipeline correct, then move to GPU if fine-tuning is too slow. Revisit once we
  get there.
- Consumption "App" — upstream course repo never published this piece
  (`README.md` says "To be uploaded"). We'll design our own once we get to Phase 7.

## Phase 1 — AWS resources

- [x] S3 bucket for landing data: `smart-claims-dev-265544358795` (us-east-1,
      public access blocked, SSE-S3 default encryption)
- [x] IAM role for Databricks: `smart-claims-databricks-role` (trust policy:
      Databricks account 414351767826 + self-assume; inline policy
      `smart-claims-s3-access` scoped to the bucket above)
- [x] Databricks storage credential `smart_claims_s3_cred` (validated, all
      checks pass) + external location `smart_claims_landing` ->
      `s3://smart-claims-dev-265544358795/`
- [ ] Kinesis Data Stream for telematics — **deferred to Phase 4**. Costs
      ~$0.36/day while it exists, and isn't needed until we're actually
      replaying telematics data, so create it then and delete it between
      sessions to avoid idle cost. This is a personal/self-funded project —
      default to cost-minimal choices like this.
- [ ] RDS SQL Server instance (Phase 3)

## Phase 2 — Databricks workspace setup

- [ ] Unity Catalog catalog `smart_claims_dev` + schemas `00_landing`/`01_bronze`/
      `02_silver`/`03_gold`
- [ ] Volumes under `00_landing` for images/training_imgs/metadata
- [ ] Storage credential + external location for the S3 bucket
- [ ] Service credential for Kinesis
- [ ] Compute: cluster/serverless for pipelines; ML-capable compute for fine-tuning

## Phase 3 — SQL Server + CDC

- [ ] Create RDS SQL Server instance
- [ ] Create schema: policy / claim / customer tables (own DDL, in
      `src/02_sql_server_ingestion/`)
- [ ] Load `data/sql_server/{customers,policies,claims}.csv`
- [ ] Enable change tracking + CDC on the RDS instance and tables
- [ ] Lakeflow Connect SQL Server CDC gateway into `01_bronze.{policy,claim,customer}`

## Phase 4 — Data ingestion

- [ ] Upload `data/claims/images/*`, `data/claims/metadata/image_metadata.csv`,
      `data/training_imgs/*` to S3 / landing Volumes
- [ ] Write a Kinesis producer that replays `data/telematics/*.parquet` as events
- [ ] Auto Loader pipelines for S3 -> bronze

## Phase 5 — Medallion transforms

- [ ] Bronze ingestion for Kinesis telematics stream
- [ ] bronze -> silver cleaning (per-table quality rules)
- [ ] silver -> gold aggregation/joins (telematics avg, claim+policy+customer join,
      geocoded claim locations)

## Phase 6 — ML

- [ ] Fine-tune an image classifier on `training_images` (ok/minor/major),
      log + register to Unity Catalog model registry
- [ ] Rule engine: a rules table + dynamic SQL-expression evaluation over claims
      (e.g. invalid policy dates, amount exceeds policy limit, reported severity
      vs. model severity mismatch, speed at time of incident, etc.)

## Phase 7 — Consumption

- [ ] Dashboard summarizing claims, damage severity, rule flags
- [ ] Simple app/view for claims investigation (design fresh — not published upstream)
