-- Phase 5: bronze -> silver cleaning
-- Run in Databricks SQL Editor, connected to the Serverless Starter Warehouse.

CREATE OR REPLACE TABLE smart_claims_dev.02_silver.customers AS
SELECT
  CAST(customer_id AS INT) AS customer_id,
  TRY_TO_DATE(date_of_birth, 'dd-MM-yyyy') AS date_of_birth,
  borough,
  neighborhood,
  zip_code,
  name
FROM smart_claims_dev.01_bronze.customers
WHERE customer_id IS NOT NULL;

CREATE OR REPLACE TABLE smart_claims_dev.02_silver.policies AS
SELECT *
FROM smart_claims_dev.01_bronze.policies
WHERE policy_no IS NOT NULL
  AND (pol_eff_date IS NULL OR pol_expiry_date IS NULL OR pol_eff_date <= pol_expiry_date);

CREATE OR REPLACE TABLE smart_claims_dev.02_silver.claims AS
SELECT *
FROM smart_claims_dev.01_bronze.claims
WHERE claim_no IS NOT NULL
  AND policy_no IS NOT NULL;

CREATE OR REPLACE TABLE smart_claims_dev.02_silver.telematics AS
WITH parsed AS (
  SELECT
    from_json(
      CAST(data AS STRING),
      'chassis_no STRING, latitude DOUBLE, longitude DOUBLE, event_timestamp STRING, speed DOUBLE'
    ) AS payload
  FROM smart_claims_dev.01_bronze.telematics
)
SELECT
  payload.chassis_no,
  payload.latitude,
  payload.longitude,
  TRY_CAST(payload.event_timestamp AS TIMESTAMP) AS event_timestamp,
  payload.speed
FROM parsed
WHERE payload.chassis_no IS NOT NULL
  AND payload.speed BETWEEN 0 AND 200
  AND payload.latitude BETWEEN -90 AND 90
  AND payload.longitude BETWEEN -180 AND 180;

CREATE OR REPLACE TABLE smart_claims_dev.02_silver.claim_images AS
SELECT
  regexp_extract(path, '([^/]+)$', 1) AS image_name,
  regexp_extract(path, '_(High|Medium|Low)\\.jpg$', 1) AS filename_severity,
  content,
  length,
  modificationTime
FROM smart_claims_dev.01_bronze.claim_images;

CREATE OR REPLACE TABLE smart_claims_dev.02_silver.training_images AS
SELECT
  regexp_extract(path, '([^/]+)$', 1) AS image_name,
  regexp_extract(path, '-([a-z]+)\\s*\\(', 1) AS label,
  content,
  length,
  modificationTime
FROM smart_claims_dev.01_bronze.training_images;

CREATE OR REPLACE TABLE smart_claims_dev.02_silver.claim_images_meta AS
SELECT image_name, image_id, claim_no, chassis_no
FROM smart_claims_dev.01_bronze.claim_images_meta
WHERE _rescued_data IS NULL;
