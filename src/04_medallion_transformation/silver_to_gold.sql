-- Phase 5: silver -> gold aggregation/joins
-- Run in Databricks SQL Editor, connected to the Serverless Starter Warehouse.

CREATE OR REPLACE TABLE smart_claims_dev.03_gold.aggregated_telematics AS
SELECT
  chassis_no,
  COUNT(*) AS event_count,
  ROUND(AVG(speed), 2) AS avg_speed,
  ROUND(MAX(speed), 2) AS max_speed,
  ROUND(MIN(speed), 2) AS min_speed,
  MIN(event_timestamp) AS first_event_timestamp,
  MAX(event_timestamp) AS last_event_timestamp
FROM smart_claims_dev.02_silver.telematics
GROUP BY chassis_no;

CREATE OR REPLACE TABLE smart_claims_dev.03_gold.customer_claim_policy AS
SELECT
  cl.claim_no,
  cl.claim_date,
  cl.total AS claim_total,
  cl.severity AS reported_severity,
  cl.collision_type,
  cl.number_of_vehicles_involved,
  cl.suspicious_activity,
  p.policy_no,
  p.policy_type,
  p.pol_issue_date,
  p.pol_eff_date,
  p.pol_expiry_date,
  p.make,
  p.model,
  p.model_year,
  p.chassis_no,
  p.sum_insured,
  p.premium,
  c.customer_id,
  c.name AS customer_name,
  c.date_of_birth,
  c.borough,
  c.neighborhood,
  c.zip_code
FROM smart_claims_dev.02_silver.claims cl
JOIN smart_claims_dev.02_silver.policies p ON cl.policy_no = p.policy_no
JOIN smart_claims_dev.02_silver.customers c ON p.cust_id = c.customer_id;

CREATE OR REPLACE TABLE smart_claims_dev.03_gold.customer_claim_policy_telematics AS
SELECT
  ccp.*,
  t.event_count AS telematics_event_count,
  t.avg_speed,
  t.max_speed,
  t.min_speed,
  t.first_event_timestamp,
  t.last_event_timestamp
FROM smart_claims_dev.03_gold.customer_claim_policy ccp
LEFT JOIN smart_claims_dev.03_gold.aggregated_telematics t
  ON ccp.chassis_no = t.chassis_no;
