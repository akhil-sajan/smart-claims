-- Phase 6: rule engine table + starting rules
-- Run in Databricks SQL Editor, connected to the Serverless Starter Warehouse.

CREATE TABLE IF NOT EXISTS smart_claims_dev.02_silver.claims_rules (
  rule_id INT,
  rule_name STRING,
  description STRING,
  sql_expression STRING,
  enabled BOOLEAN
);

DELETE FROM smart_claims_dev.02_silver.claims_rules;

INSERT INTO smart_claims_dev.02_silver.claims_rules VALUES
(1, 'claim_outside_policy_period',
    'Claim date falls outside the policy''s effective/expiry window',
    'claim_date < pol_eff_date OR claim_date > pol_expiry_date', true),
(2, 'claim_exceeds_sum_insured',
    'Claimed amount exceeds the vehicle''s insured value',
    'claim_total > sum_insured', true),
(3, 'high_speed_before_incident',
    'Vehicle telematics show unusually high speed (over 120)',
    'max_speed > 120', true),
(4, 'reported_suspicious_activity',
    'Claim was flagged as suspicious activity at intake',
    "suspicious_activity = 'true'", true),
(5, 'early_claim_after_issuance',
    'Claim filed within 7 days of policy issuance',
    'DATEDIFF(claim_date, pol_issue_date) < 7', true);
