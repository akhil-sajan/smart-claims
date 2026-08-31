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
- [x] Phase 1: AWS resources — S3 bucket + IAM role (Kinesis stream itself is
      created/deleted per-session in Phase 4, not left standing)
- [x] Phase 2: Databricks Unity Catalog setup (catalog/schemas/volumes)
- [x] Phase 3: SQL Server (real RDS instance) + CDC ingestion into `01_bronze`
- [x] Phase 4: Data ingestion (S3 upload, Kinesis producer) — all 7 `01_bronze`
      tables now exist: `customers`/`policies`/`claims` (SQL Server CDC),
      `claim_images`/`claim_images_meta`/`training_images` (S3 files via
      standalone Auto Loader streaming tables), `telematics` (Kinesis via
      `read_kinesis()`)
- [x] Phase 5: Medallion transforms (bronze -> silver -> gold)
- [x] Phase 6: ML (damage classifier + rule engine)
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
- [x] Kinesis Data Stream for telematics — built and torn down as part of
      Phase 4 (see below), not a standing resource. Create fresh, feed it,
      verify, delete — repeat this pattern any time telematics data needs
      reloading, rather than leaving it running between sessions.
- [x] RDS SQL Server instance (Phase 3)

## Phase 2 — Databricks workspace setup

- [x] Unity Catalog catalog `smart_claims_dev` (storage root explicitly set to
      `s3://smart-claims-dev-265544358795/` — first attempt used Databricks'
      default managed storage, which Lakeflow Connect pipelines reject; catalog
      was recreated with an explicit `--storage-root`) + schemas
      `00_landing`/`01_bronze`/`02_silver`/`03_gold`
- [x] Volumes under `00_landing`: `claim_images`, `training_imgs`, `claim_metadata`
- [x] Storage credential + external location for the S3 bucket (Phase 1)
- [ ] Service credential for Kinesis (Phase 4, when Kinesis is created)
- [x] Compute: Serverless Starter Warehouse + serverless pipeline compute

## Phase 3 — SQL Server + CDC

- [x] RDS SQL Server instance: `smart-claims-sqlserver` (Express edition,
      `db.t3.micro`, 20GB gp3, us-east-1, ~$18/month running / ~$2.30/month
      stopped — stop it between sessions via RDS console when not in use)
- [x] Database `smart_claims` with `customers`/`policies`/`claims` tables (own
      DDL). Loaded via staging tables (`*_staging`, all-text columns) then
      cleaned/cast into the real typed tables — see chat history for the exact
      migration SQL. `policies` had ~183 duplicate `policy_no` rows in source
      data, deduped by keeping the highest-premium row per policy.
- [x] Change Tracking enabled (database + all 3 tables) — Express edition
      doesn't support full CDC, but Lakeflow Connect's SQL Server connector is
      built around Change Tracking anyway.
- [x] Dedicated login `databricks_ingest` (not the admin login) for ingestion,
      permissions fixed via Databricks' official
      `src/02_sql_server_ingestion/lakeflow_utility_script.sql` (installs
      `lakeflowFixPermissions`/`lakeflowSetupChangeTracking`/
      `lakeflowSetupChangeDataCapture` procedures — re-run
      `EXEC dbo.lakeflowFixPermissions @User='databricks_ingest', @Tables='ALL'`
      any time permissions need re-syncing, e.g. after adding new tables)
- [x] Lakeflow Connect SQL Server CDC pipeline `smart_claims_sqlserver_ingestion`
      -> `smart_claims_dev.01_bronze.{customers,policies,claims}`, confirmed
      with real rows landed. Runs in continuous mode (stays running until
      manually stopped) — stopped after initial load to avoid ongoing
      serverless compute cost; restart it from Databricks' Pipelines UI when
      fresh syncs are needed.

### Gotchas hit along the way (useful if redoing this)
- RDS "Easy create" and default template settings inflate cost significantly
  (defaulted to 200GB storage + would've used Multi-AZ) — use "Full
  configuration" and explicitly set Single-AZ + 20GB + gp3.
- Azure Data Studio is retired (Feb 2026) — use VS Code + the MSSQL extension
  instead.
- RDS BULK INSERT can't read local client files (the SQL Server engine runs on
  AWS, not your PC) — use the MSSQL extension's Import Wizard instead, which
  streams over the client connection.
- The workspace's Databricks metastore is homed in us-east-2 while AWS
  resources are in us-east-1 (cross-region, minor cost/latency only, not
  worth fixing at this scale).
- Databricks' ingestion compute connects from a specific, workspace-dependent
  outbound IP — not published in any static Databricks doc. Found it by
  temporarily attaching a VPC Flow Log (REJECT traffic only) to the RDS
  instance's ENI and reading the rejected connection's source IP from
  CloudWatch Logs, rather than guessing.
- The Databricks connection needed `trustServerCertificate: true` in its
  options (RDS presents an Amazon-issued cert Databricks doesn't trust by
  default) — set via `databricks connections update`.

## Phase 4 — Data ingestion

- [x] Uploaded `data/claims/images/*` (15 files), `data/claims/metadata/image_metadata.csv`,
      `data/training_imgs/*` (56 files) to the `00_landing` Volumes via
      `databricks fs cp -r`
- [x] Standalone streaming tables (Databricks SQL Editor, `read_files()` +
      `CREATE OR REFRESH STREAMING TABLE`, no pipeline needed) load
      `00_landing` -> `01_bronze.{claim_images,training_images,claim_images_meta}`.
      Re-run `REFRESH STREAMING TABLE <name>` after uploading new files to
      pick them up.
- [x] Kinesis producer (`src/01_streaming_ingestion/kinesis_producer.py`) reads
      `data/telematics/*.parquet` with DuckDB (pyarrow is blocked by a local
      Windows Application Control policy on this machine — DuckDB works fine
      as the parquet reader instead) and replays all 780,060 rows into Kinesis
      via `boto3` batched `put_records` (partition key = `chassis_no`). On-demand
      Kinesis stream `smart-claims-telematics` is created fresh, fed, verified
      via CloudWatch `IncomingRecords`, then **deleted immediately after** —
      it's not a standing resource. A leftover stream (`telematics-stream-tmh`,
      from pre-conversation experimentation, same as the old `insurance_claim`
      catalog) was found and deleted first.
- [x] Standalone streaming table `01_bronze.telematics` via
      `read_kinesis(streamName, serviceCredential, region, initialPosition =>
      'trim_horizon')`, using a Databricks **service credential**
      (`smart_claims_kinesis_cred`, purpose=SERVICE, same reused IAM role as
      the S3 storage credential — just needed a `smart-claims-kinesis-access`
      policy added to it for `kinesis:GetRecords`/`GetShardIterator`/etc.,
      scoped to the stream's ARN). `initialPosition => 'trim_horizon'` reads
      from the start of the stream, not just new records.

### Gotchas
- **Serverless compute quota**: hit `RESOURCE_EXHAUSTED` creating the
  streaming tables because the SQL Server ingestion pipeline
  (`smart_claims_sqlserver_ingestion`) was still silently running in the
  background (had been for ~3 hours, re-triggering hourly) — stopping it
  freed up capacity. **Always verify a pipeline shows `IDLE` after use**
  (`databricks pipelines get <id>`), don't assume a stop/retry click actually
  stopped it.
- **RDS "auto recovery"**: after being manually stopped, RDS came back up on
  its own days later with event message "Recovery of the DB instance has
  started" — not something we triggered. Not a data-safety concern, but it
  does mean compute cost resumes; check status and re-stop it after any gap
  in sessions rather than assuming a stopped instance stays stopped
  indefinitely.

## Phase 5 — Medallion transforms

- [x] Bronze -> silver cleaning (`src/04_medallion_transformation/bronze_to_silver.sql`):
      `customers` (drop `.0` from IDs, parse birth dates), `policies`/`claims`
      (filter null keys + nonsensical dates), `telematics` (**unpack the raw
      Kinesis JSON payload** in the `data` binary column into real columns,
      filter impossible speed/GPS readings), `claim_images`/`training_images`
      (extract filename + the severity/damage label baked into the filename),
      `claim_images_meta` (drop malformed rows). No rows dropped except ~198
      claims with a missing key and some `.jpg`/`.png` naming edge cases.
- [x] Silver -> gold (`src/04_medallion_transformation/silver_to_gold.sql`):
      `aggregated_telematics` (per-vehicle avg/max/min speed + event count),
      `customer_claim_policy` (claims + policies + customers joined, one row
      per claim — 12,793 rows, matches silver `claims` exactly), plus that
      joined with `aggregated_telematics` — 12,788/12,793 claims (99.96%)
      matched a vehicle's telematics summary.
- Skipped geocoding claim locations from the original plan (no clear source
  lat/lon on the claims table itself — telematics has GPS, but per-claim
  location wasn't part of the source data). Revisit if needed later.

## Phase 6 — ML

- [x] Rule engine (`src/05_machine_learning/claims_rules_setup.sql` +
      `rule_engine.py`): a rules table (`02_silver.claims_rules`, one row per
      rule storing its condition as a plain SQL boolean expression string) +
      a small Python loop that reads it and checks every enabled rule against
      every claim in `03_gold.customer_claim_policy_telematics`, writing
      matches to `03_gold.claims_flags`. Adding a rule later = one `INSERT`,
      no code change. Thresholds were initially picked blind and needed
      correcting after checking the real data distribution (see gotchas).
- [x] Damage-severity image classifier (`src/05_machine_learning/damage_classifier.py`):
      transfer learning on a pretrained MobileNetV2 (backbone frozen, only the
      final classification layer retrained) using the 56 labeled
      `training_images`, tracked and registered via MLflow to Unity Catalog as
      `smart_claims_dev.03_gold.claims_damage_classifier`. Applied to the 15
      real `claim_images`, predictions saved to
      `03_gold.claims_damage_level`. **Caveat**: 56 images is a tiny dataset —
      98% training accuracy almost certainly reflects memorization, not a
      generalizable model. Fine as a working proof-of-concept pipeline, not
      representative of real-world accuracy.

### Gotchas
- **Rule thresholds picked without checking the data first**: `high_speed_before_incident`
  used a threshold of 120 before checking that this telematics sample only
  ranges 57-72 (zero matches, silently). `reported_suspicious_activity` used
  `= 'true'` before checking the actual column values (which are `'0'`/`'1'`
  text, not `'true'`/`'false'`) — also zero matches. **Always check a
  column's actual value range/distribution before writing a threshold or
  equality rule against it.** `claim_exceeds_sum_insured` (any excess)
  initially flagged 48% of all claims — tightened to `> sum_insured * 1.5`
  for a more meaningful signal.
- **Serverless notebook + `%pip install` + `dbutils.library.restartPython()`
  together lose the installed packages** (`ModuleNotFoundError: No module
  named 'torch'` on the next cell, even though the install reported
  success). Fix: install via `subprocess.check_call([sys.executable, "-m",
  "pip", "install", ...])` in the same cell as the code that needs it,
  instead of a separate `%pip` + restart cell.
- **Unity Catalog requires a model `signature`** (input/output shape) on
  `mlflow.pytorch.log_model(..., registered_model_name=...)` — infer one with
  `mlflow.models.infer_signature()` from a sample batch before registering,
  or the registration fails.

## Phase 7 — Consumption

- [ ] Dashboard summarizing claims, damage severity, rule flags
- [ ] Simple app/view for claims investigation (design fresh — not published upstream)
