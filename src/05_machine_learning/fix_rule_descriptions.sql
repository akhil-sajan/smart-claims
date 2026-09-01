-- Fix stale rule descriptions that no longer match their tuned thresholds
-- (the earlier threshold fixes only updated sql_expression, not description).

UPDATE smart_claims_dev.02_silver.claims_rules
SET description = 'Vehicle telematics show unusually high speed (over 68)'
WHERE rule_id = 3;

UPDATE smart_claims_dev.02_silver.claims_rules
SET description = 'Claimed amount exceeds the vehicle''s insured value by 50% or more'
WHERE rule_id = 2;
