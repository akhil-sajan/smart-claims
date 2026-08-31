# Phase 6: dynamic rule engine
# Paste into a Databricks notebook cell (Python) and run.
# Reads every enabled rule from claims_rules, checks it against every claim
# in the gold table, and writes out which claims tripped which rules.
# Adding a new rule later = INSERT a row into claims_rules, no code change.

from functools import reduce

rules = spark.sql(
    "SELECT * FROM smart_claims_dev.02_silver.claims_rules WHERE enabled = true"
).collect()

flag_dfs = []
for rule in rules:
    query = f"""
        SELECT
            claim_no,
            '{rule.rule_name}' AS rule_name,
            '{rule.description}' AS description
        FROM smart_claims_dev.03_gold.customer_claim_policy_telematics
        WHERE {rule.sql_expression}
    """
    flag_dfs.append(spark.sql(query))

all_flags = reduce(lambda a, b: a.unionByName(b), flag_dfs)
all_flags.write.mode("overwrite").saveAsTable("smart_claims_dev.03_gold.claims_flags")

display(
    spark.sql(
        """
        SELECT rule_name, COUNT(*) AS flagged_claims
        FROM smart_claims_dev.03_gold.claims_flags
        GROUP BY rule_name
        ORDER BY flagged_claims DESC
        """
    )
)
