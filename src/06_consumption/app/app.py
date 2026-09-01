"""Smart Claims investigation app.

Dashboard tab: high-level summary of claims, rule flags, and predicted
damage severity. Investigation tab: pick a specific claim and see its full
details, photo, predicted vs. reported severity, and any rule flags.
"""

import io

import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config
from PIL import Image

# The SQL warehouse this app queries against (the "Serverless Starter
# Warehouse" created earlier in this project).
WAREHOUSE_HTTP_PATH = "/sql/1.0/warehouses/9ad4d5297cb46084"

st.set_page_config(page_title="Smart Claims", layout="wide")

cfg = Config()


@st.cache_resource
def get_connection():
    server_hostname = cfg.host.replace("https://", "").replace("http://", "")
    return sql.connect(
        server_hostname=server_hostname,
        http_path=WAREHOUSE_HTTP_PATH,
        credentials_provider=lambda: cfg.authenticate,
    )


def run_query(query: str, params: tuple = ()) -> pd.DataFrame:
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall_arrow().to_pandas()


st.title("Smart Claims")
tab_dashboard, tab_investigate = st.tabs(["Dashboard", "Claim Investigation"])

# ---------------------------------------------------------------------------
with tab_dashboard:
    summary = run_query(
        """
        SELECT COUNT(*) AS total_claims, ROUND(AVG(claim_total), 2) AS avg_claim
        FROM smart_claims_dev.03_gold.customer_claim_policy_telematics
        """
    )
    flagged = run_query(
        """
        SELECT COUNT(DISTINCT claim_no) AS flagged_claims
        FROM smart_claims_dev.03_gold.claims_flags
        """
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Total claims", f"{int(summary['total_claims'][0]):,}")
    col2.metric("Average claim amount", f"${summary['avg_claim'][0]:,.2f}")
    col3.metric("Claims with at least one flag", f"{int(flagged['flagged_claims'][0]):,}")

    st.subheader("Claims flagged per rule")
    rule_counts = run_query(
        """
        SELECT rule_name, COUNT(*) AS flagged_claims
        FROM smart_claims_dev.03_gold.claims_flags
        GROUP BY rule_name
        ORDER BY flagged_claims DESC
        """
    )
    st.bar_chart(rule_counts.set_index("rule_name"))

    st.subheader("Predicted damage severity (claim photos)")
    severity_counts = run_query(
        """
        SELECT predicted_severity, COUNT(*) AS count
        FROM smart_claims_dev.03_gold.claims_damage_level
        GROUP BY predicted_severity
        """
    )
    st.bar_chart(severity_counts.set_index("predicted_severity"))

# ---------------------------------------------------------------------------
with tab_investigate:
    claim_options = run_query(
        """
        SELECT DISTINCT claim_no
        FROM smart_claims_dev.02_silver.claim_images_meta
        ORDER BY claim_no
        LIMIT 500
        """
    )
    selected_claim = st.selectbox(
        "Pick a claim to investigate (showing claims that have an associated photo)",
        claim_options["claim_no"],
    )

    if selected_claim:
        details = run_query(
            """
            SELECT *
            FROM smart_claims_dev.03_gold.customer_claim_policy_telematics
            WHERE claim_no = ?
            """,
            (selected_claim,),
        )

        if details.empty:
            st.warning("No claim details found for this claim_no.")
        else:
            row = details.iloc[0]
            left, right = st.columns([1, 1])

            with left:
                st.subheader("Claim details")
                st.write(f"**Customer:** {row['customer_name']}")
                st.write(f"**Claim date:** {row['claim_date']}")
                st.write(f"**Claim total:** ${row['claim_total']:,.2f}")
                st.write(f"**Reported severity:** {row['reported_severity']}")
                st.write(f"**Collision type:** {row['collision_type']}")
                st.write(f"**Vehicle:** {row['model_year']} {row['make']} {row['model']}")
                st.write(f"**Policy:** {row['policy_no']} ({row['policy_type']})")
                if pd.notna(row.get("avg_speed")):
                    st.write(f"**Vehicle avg speed (telematics):** {row['avg_speed']}")
                    st.write(f"**Vehicle max speed (telematics):** {row['max_speed']}")

                st.subheader("Rule flags")
                flags = run_query(
                    """
                    SELECT rule_name, description
                    FROM smart_claims_dev.03_gold.claims_flags
                    WHERE claim_no = ?
                    """,
                    (selected_claim,),
                )
                if flags.empty:
                    st.success("No rules flagged on this claim.")
                else:
                    for _, flag_row in flags.iterrows():
                        st.error(f"**{flag_row['rule_name']}** — {flag_row['description']}")

            with right:
                st.subheader("Claim photo & predicted severity")
                photo = run_query(
                    """
                    SELECT ci.content, cdl.predicted_severity
                    FROM smart_claims_dev.02_silver.claim_images_meta cim
                    JOIN smart_claims_dev.02_silver.claim_images ci
                        ON cim.image_name = ci.image_name
                    LEFT JOIN smart_claims_dev.03_gold.claims_damage_level cdl
                        ON cim.image_name = cdl.image_name
                    WHERE cim.claim_no = ?
                    LIMIT 1
                    """,
                    (selected_claim,),
                )
                if photo.empty:
                    st.info("No photo on file for this claim.")
                else:
                    img_bytes = photo.iloc[0]["content"]
                    img = Image.open(io.BytesIO(img_bytes))
                    st.image(img)
                    predicted = photo.iloc[0]["predicted_severity"]
                    if pd.notna(predicted):
                        st.write(f"**Model-predicted severity:** {predicted}")
                        # reported_severity uses a different vocabulary
                        # ("Major Damage") than the model's labels
                        # ("major") — normalize before comparing.
                        reported_to_model_label = {
                            "Trivial Damage": "ok",
                            "Minor Damage": "minor",
                            "Major Damage": "major",
                            "Total Loss": "major",
                        }
                        normalized_reported = reported_to_model_label.get(
                            row["reported_severity"]
                        )
                        if normalized_reported and predicted != normalized_reported:
                            st.warning(
                                "Predicted severity differs from reported severity — worth a second look."
                            )
