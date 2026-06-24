"""Build and optionally execute the project's five analytical notebooks."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DIR = PROJECT_ROOT / "notebooks"
PYTHON_VERSION = "3.12.7"


def md(text: str):
    return new_markdown_cell(text.strip())


def code(text: str):
    return new_code_cell(text.strip())


def notebook(title: str, cells: list) -> nbformat.NotebookNode:
    return new_notebook(
        cells=[md(f"# {title}\n\n*Executed analytical companion to the validated production pipeline.*"), *cells],
        metadata={
            "kernelspec": {
                "display_name": "Python 3.12",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": PYTHON_VERSION,
                "mimetype": "text/x-python",
                "codemirror_mode": {"name": "ipython", "version": 3},
                "pygments_lexer": "ipython3",
                "nbconvert_exporter": "python",
                "file_extension": ".py",
            },
        },
    )


COMMON_SETUP = r"""
from pathlib import Path
import json
import sys

import pandas as pd
from IPython.display import Image, Markdown, display

PROJECT_ROOT = next(
    path for path in [Path.cwd().resolve(), *Path.cwd().resolve().parents]
    if (path / "src" / "retail_analytics").exists()
)
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

pd.set_option("display.max_rows", 12)
pd.set_option("display.max_columns", 14)
pd.set_option("display.width", 140)

def load_json(relative_path):
    return json.loads((PROJECT_ROOT / relative_path).read_text(encoding="utf-8"))

print(f"Project root: {PROJECT_ROOT}")
print(f"Python: {sys.version.split()[0]}")
"""


def validation_notebook() -> nbformat.NotebookNode:
    return notebook(
        "01 — Data Validation and Cleaning",
        [
            md("""
## Objective

Document the validated ingestion and cleaning contract using existing profiles and processed Parquet metadata. This notebook does **not** open or rewrite the raw Excel workbook.

## Business Questions

- What fields, worksheets, and date coverage are present in the source?
- Where are missing values and exact duplicates concentrated?
- How are completed sales, returns, anonymous sales, and excluded records separated?
- Do row counts and monetary values reconcile after cleaning?

## Inputs

- `reports/raw_data_profile.json`
- `reports/cleaning_summary.json`
- Processed Parquet metadata under `data/processed/`
- Reusable contracts in `retail_analytics.cleaning`

## Methodology

Read compact validation artifacts and Parquet schemas only. The production functions remain the source of truth; no raw-workbook ingestion or cleaning is rerun here.

## Code
"""),
            code(COMMON_SETUP + r"""
import pyarrow.parquet as pq
from retail_analytics.cleaning import (
    calculate_outlier_thresholds,
    partition_masks,
    prepare_transactions,
)

raw_profile = load_json("reports/raw_data_profile.json")
cleaning = load_json("reports/cleaning_summary.json")
print("Reusable cleaning module loaded:", prepare_transactions.__module__)
"""),
            code(r"""
raw_schema = pd.DataFrame(
    [
        ("Invoice", "string", "Transaction identifier; C prefix indicates cancellation"),
        ("StockCode", "string", "Product identifier"),
        ("Description", "nullable string", "Product description"),
        ("Quantity", "integer", "Units; negative values indicate returns"),
        ("InvoiceDate", "datetime", "Transaction timestamp"),
        ("Price", "numeric", "Unit price in GBP"),
        ("Customer ID", "nullable string", "Customer identifier"),
        ("Country", "string", "Customer country"),
    ],
    columns=["Raw field", "Expected type", "Meaning"],
)
display(raw_schema)
display(pd.DataFrame({
    "Source worksheet": raw_profile["coverage"]["source_sheets"],
    "Role": ["First source year", "Second source year"],
}))
print(
    "Coverage:", raw_profile["coverage"]["minimum_invoice_date"], "to",
    raw_profile["coverage"]["maximum_invoice_date"]
)
"""),
            code(r"""
missing = (
    pd.DataFrame(raw_profile["missing_values"]).T
    .rename_axis("field").reset_index()
    .rename(columns={"count": "missing_rows", "percent": "missing_pct"})
)
missing["missing_rows"] = missing["missing_rows"].map(lambda value: f"{value:,.0f}")
missing["missing_pct"] = missing["missing_pct"].map(lambda value: f"{value:.2f}%")
display(missing)

duplicates = pd.DataFrame([
    ("Rows read", raw_profile["row_counts"]["total"]),
    ("Exact duplicates within sheets", raw_profile["row_counts"]["exact_duplicates_within_sheet"]),
    ("Exact duplicates across workbook", raw_profile["row_counts"]["exact_duplicates_across_workbook"]),
    ("Unique cleaned rows", cleaning["unique_rows"]),
], columns=["Audit measure", "Rows"])
duplicates["Rows"] = duplicates["Rows"].map(lambda value: f"{value:,.0f}")
display(duplicates)
"""),
            code(r"""
parquet_path = PROJECT_ROOT / "data" / "processed" / "completed_sales.parquet"
parquet = pq.ParquetFile(parquet_path)
processed_schema = pd.DataFrame(
    [(field.name, str(field.type)) for field in parquet.schema_arrow],
    columns=["Processed field", "Parquet type"],
)
print(f"Completed-sales rows from Parquet metadata: {parquet.metadata.num_rows:,.0f}")
display(processed_schema.head(14))
"""),
            md("""
## Results

The following tables reproduce the validated cleaning decisions and reconciliation—not a second implementation of them.
"""),
            code(r"""
decisions = pd.DataFrame([
    ("Exact duplicates", "Remove exact repeated source rows once"),
    ("Completed sales", "Positive quantity and price; invoice is not cancelled"),
    ("Returns/cancellations", "Cancelled invoice or negative quantity"),
    ("Anonymous sales", "Retain for aggregate sales; exclude from customer analytics"),
    ("Non-sales records", "Isolate with an explicit exclusion reason"),
    ("Extreme values", "Flag with IQR thresholds; do not automatically delete"),
], columns=["Decision area", "Validated treatment"])
display(decisions)

partitions = pd.DataFrame(
    [(name.replace("_", " ").title(), value) for name, value in cleaning["partitions"].items()],
    columns=["Partition", "Rows"],
)
partitions["Rows"] = partitions["Rows"].map(lambda value: f"{value:,.0f}")
display(partitions)

reconciliation = pd.DataFrame([
    ("Unique rows", cleaning["unique_rows"]),
    ("Partition total", cleaning["reconciliation"]["partition_total"]),
    ("Completed-sales value", f"GBP {cleaning['completed_sales_value_gbp']:,.2f}"),
    ("Signed returns value", f"GBP {cleaning['returns_value_gbp']:,.2f}"),
], columns=["Reconciliation measure", "Validated result"])
display(reconciliation)
print("Partition reconciliation passed:", cleaning["reconciliation"]["matches_unique_rows"])
"""),
            md("""
## Business Insights

- The two worksheets cover 1 December 2009 through 9 December 2011; the last month is partial.
- Missing customer IDs are expected and materially important: anonymous completed sales remain in aggregate revenue, but cannot support customer-level RFM, cohort, statistical, or clustering analysis because no stable customer key exists.
- Exact duplicate removal prevents double counting while preserving legitimate repeated product lines.
- Outliers are flagged rather than deleted because they may represent genuine wholesale or high-volume activity; deletion would silently change confirmed revenue.

## Assumptions

- Invoice prefixes and quantity signs retain their documented transactional meaning.
- GBP is the reporting currency and no foreign-exchange conversion is required.
- Existing JSON reports and Parquet files are outputs of the validated production pipeline.

## Limitations

- The source has no unit cost, margin, marketing exposure, or demographic fields.
- Missing descriptions limit product interpretation for a small subset of rows.
- Validation identifies unusual observations but cannot independently confirm whether each is wholesale, error, or another operational case.

## Next Steps

- Monitor future source extracts against the same schema and reconciliation gates.
- Investigate flagged high-value lines with operational context before any exclusion decision.
- Preserve worksheet and transaction-line lineage in downstream refreshes.
"""),
        ],
    )


def sql_eda_notebook() -> nbformat.NotebookNode:
    return notebook(
        "02 — SQL and Exploratory Analysis",
        [
            md("""
## Objective

Explain the SQLite star schema and validated exploratory results using read-only database metadata, named SQL definitions, exported aggregates, and existing charts.

## Business Questions

- How is the analytical star schema organised and reconciled?
- What are the confirmed executive KPIs?
- How do sales vary over time, geography, product, and order value?
- Which interpretation caveats matter for decision-makers?

## Inputs

- `data/processed/retail_analytics.sqlite` opened read-only
- `sql/03_business_queries.sql` parsed with the reusable SQL runner
- `reports/sql_results/`, `reports/eda_tables/`, and `reports/eda_summary.json`
- Existing charts under `images/eda/`

## Methodology

Inspect database metadata and compact exported reports. Named analytical SQL is parsed, not reimplemented; million-row facts are never printed.

## Code
"""),
            code(COMMON_SETUP + r"""
import sqlite3
from retail_analytics.sql_runner import parse_named_queries

sql_model = load_json("reports/sql_model_summary.json")
eda_summary = load_json("reports/eda_summary.json")
manifest = load_json("reports/sql_query_manifest.json")
database_path = PROJECT_ROOT / "data" / "processed" / "retail_analytics.sqlite"
"""),
            code(r"""
uri = f"file:{database_path.as_posix()}?mode=ro"
with sqlite3.connect(uri, uri=True) as connection:
    schema_objects = pd.read_sql_query(
        "SELECT name, type FROM sqlite_master "
        "WHERE type IN ('table', 'index') AND name NOT LIKE 'sqlite_%' "
        "ORDER BY type, name",
        connection,
    )
display(schema_objects)

table_counts = pd.DataFrame(
    [(name, rows) for name, rows in sql_model["table_counts"].items()],
    columns=["Star-schema table", "Rows"],
)
table_counts["Rows"] = table_counts["Rows"].map(lambda value: f"{value:,.0f}")
display(table_counts)
print("Foreign-key failures:", sql_model["foreign_key_failures"])
"""),
            code(r"""
named_queries = parse_named_queries(PROJECT_ROOT / "sql" / "03_business_queries.sql")
query_catalogue = pd.DataFrame([
    {
        "Query": name,
        "Exported rows": manifest["queries"][name]["rows"],
        "Output columns": len(manifest["queries"][name]["columns"]),
    }
    for name, _ in named_queries
])
display(query_catalogue)
"""),
            md("""
## Results
"""),
            code(r"""
kpis = pd.read_csv(PROJECT_ROOT / "reports" / "sql_results" / "executive_kpis.csv").iloc[0]
kpi_table = pd.DataFrame([
    ("Completed-sales revenue", f"GBP {kpis.revenue_gbp:,.2f}"),
    ("Completed orders", f"{kpis.orders:,.0f}"),
    ("Identified customers", f"{kpis.identified_customers:,.0f}"),
    ("Average order value", f"GBP {kpis.average_order_value_gbp:,.2f}"),
    ("Revenue per identified customer", f"GBP {kpis.revenue_per_identified_customer_gbp:,.2f}"),
], columns=["Executive KPI", "Validated value"])
display(kpi_table)

monthly = pd.read_csv(PROJECT_ROOT / "reports" / "eda_tables" / "monthly_performance.csv")
monthly_view = monthly.tail(6)[
    ["year_month", "revenue_gbp", "orders", "average_order_value_gbp", "is_partial_period"]
].copy()
monthly_view["revenue_gbp"] = monthly_view["revenue_gbp"].map(lambda value: f"GBP {value:,.2f}")
monthly_view["average_order_value_gbp"] = monthly_view["average_order_value_gbp"].map(lambda value: f"GBP {value:,.2f}")
monthly_view["orders"] = monthly_view["orders"].map(lambda value: f"{value:,.0f}")
display(monthly_view)
"""),
            code(r"""
country = pd.read_csv(PROJECT_ROOT / "reports" / "eda_tables" / "country_performance.csv").head(8)
country_view = country[["country", "revenue_gbp", "orders", "revenue_share_pct"]].copy()
country_view["revenue_gbp"] = country_view["revenue_gbp"].map(lambda value: f"GBP {value:,.2f}")
country_view["orders"] = country_view["orders"].map(lambda value: f"{value:,.0f}")
country_view["revenue_share_pct"] = country_view["revenue_share_pct"].map(lambda value: f"{value:.2f}%")
display(country_view)

products = pd.read_csv(PROJECT_ROOT / "reports" / "eda_tables" / "product_performance.csv").head(8)
product_view = products[["stock_code", "description", "units_sold", "revenue_gbp", "revenue_share_pct"]].copy()
product_view["units_sold"] = product_view["units_sold"].map(lambda value: f"{value:,.0f}")
product_view["revenue_gbp"] = product_view["revenue_gbp"].map(lambda value: f"GBP {value:,.2f}")
product_view["revenue_share_pct"] = product_view["revenue_share_pct"].map(lambda value: f"{value:.2f}%")
display(product_view)

orders = pd.read_csv(PROJECT_ROOT / "reports" / "eda_tables" / "order_summary.csv", usecols=["order_value_gbp"])
quantiles = orders["order_value_gbp"].quantile([0.25, 0.50, 0.75, 0.90, 0.99])
display(pd.DataFrame({"Order-value percentile": ["25%", "50%", "75%", "90%", "99%"],
                      "Order value": [f"GBP {value:,.2f}" for value in quantiles]}))
"""),
            code(r"""
for chart in [
    "images/eda/01_monthly_revenue.png",
    "images/eda/04_top_countries_revenue.png",
    "images/eda/05_top_products_revenue.png",
    "images/eda/08_order_value_distribution.png",
]:
    display(Image(filename=str(PROJECT_ROOT / chart), width=820))
"""),
            md("""
## Business Insights

- Confirmed completed-sales revenue is GBP 20.48 million across 40,077 orders; the United Kingdom contributes about 85% of revenue.
- Product and customer value are concentrated, so rankings should be interpreted with wholesale-like activity and non-product lines such as postage/manual adjustments in view.
- Anonymous transactions remain valid in aggregate sales and geographic/product EDA, but are excluded from customer analytics because they cannot be assigned to a stable customer history.
- December 2011 ends on 9 December and is explicitly marked partial; it should not be compared with full calendar months as if exposure were equal.

## Assumptions

- SQLite exports and EDA tables share the validated completed-sales definition.
- Country is taken from the transaction for order and geographic analysis.
- Monetary results are reported in GBP.

## Limitations

- Revenue is not profit: unit cost, shipping cost, and margin are unavailable.
- The observation period is historical and cannot establish current demand.
- Extreme orders are retained and flagged, not deleted, because legitimate wholesale activity is plausible.

## Next Steps

- Pair revenue with cost data before making profitability decisions.
- Track complete-month trends separately from partial refresh periods.
- Investigate concentrated products and customers with operational context.
"""),
        ],
    )


def rfm_notebook() -> nbformat.NotebookNode:
    return notebook(
        "03 — RFM and Cohort Analysis",
        [
            md("""
## Objective

Explain the validated customer RFM, eight rule-based segments, recommended actions, and monthly cohort-retention view without rebuilding customer logic.

## Business Questions

- How are recency, frequency, and monetary value defined and scored?
- Which customer groups dominate count and revenue?
- What actions are associated with each transparent rule-based segment?
- How should retention cohorts and the partial final month be interpreted?

## Inputs

- `data/processed/customer_rfm_segments.parquet`
- `reports/customer_analytics/segment_summary.csv`
- `reports/customer_analytics/segment_action_plan.csv`
- `reports/customer_analytics/cohort_retention.csv`
- Reusable segment rules from `retail_analytics.customer_analytics`

## Methodology

Read the production RFM table and aggregated customer reports. Only distributions and small samples are displayed; no full customer-level table is printed.

## Code
"""),
            code(COMMON_SETUP + r"""
from retail_analytics.customer_analytics import SEGMENT_ORDER, SEGMENT_RULES

summary = load_json("reports/customer_analytics_summary.json")
rfm_path = PROJECT_ROOT / "data" / "processed" / "customer_rfm_segments.parquet"
rfm = pd.read_parquet(
    rfm_path,
    columns=["recency_days", "frequency_orders", "monetary_value_gbp", "segment"],
)
print(f"Validated customer rows: {len(rfm):,.0f}")
print("Snapshot date:", summary["snapshot_date"])
"""),
            code(r"""
rfm_distribution = rfm[["recency_days", "frequency_orders", "monetary_value_gbp"]].describe(
    percentiles=[0.25, 0.50, 0.75, 0.90]
).loc[["count", "mean", "25%", "50%", "75%", "90%", "max"]]
rfm_distribution["monetary_value_gbp"] = rfm_distribution["monetary_value_gbp"].map(
    lambda value: f"GBP {value:,.2f}"
)
display(rfm_distribution)

rules = pd.DataFrame(
    [(segment, SEGMENT_RULES[segment]) for segment in SEGMENT_ORDER],
    columns=["Segment", "Ordered assignment rule"],
)
display(rules)
"""),
            md("""
RFM formulas use the 2011-12-10 snapshot date:

- **Recency:** days from the snapshot to the customer's last completed purchase; lower is better.
- **Frequency:** distinct completed invoices; higher is better.
- **Monetary value:** identified completed-sales revenue in GBP; higher is better.
- Each metric is converted to a 1–5 quantile score before the ordered, mutually exclusive business rules are applied.

Anonymous completed sales are excluded because a missing customer ID cannot support purchase history, repeat behavior, segment assignment, or cohort membership. Their revenue remains included in aggregate sales analysis.

## Results
"""),
            code(r"""
segments = pd.read_csv(PROJECT_ROOT / "reports" / "customer_analytics" / "segment_summary.csv")
segment_view = segments[
    ["segment", "customer_count", "customer_share_pct", "monetary_value_gbp", "revenue_share_pct",
     "median_recency_days", "average_frequency_orders"]
].copy()
segment_view["customer_count"] = segment_view["customer_count"].map(lambda value: f"{value:,.0f}")
segment_view["customer_share_pct"] = segment_view["customer_share_pct"].map(lambda value: f"{value:.2f}%")
segment_view["monetary_value_gbp"] = segment_view["monetary_value_gbp"].map(lambda value: f"GBP {value:,.2f}")
segment_view["revenue_share_pct"] = segment_view["revenue_share_pct"].map(lambda value: f"{value:.2f}%")
segment_view["average_frequency_orders"] = segment_view["average_frequency_orders"].map(lambda value: f"{value:.2f}")
display(segment_view)

actions = pd.read_csv(PROJECT_ROOT / "reports" / "customer_analytics" / "segment_action_plan.csv")
display(actions[["segment", "priority", "recommended_action"]])
"""),
            code(r"""
cohort = pd.read_csv(PROJECT_ROOT / "reports" / "customer_analytics" / "cohort_retention.csv")
cohort_preview = cohort.iloc[:8, :9].copy()
for column in cohort_preview.columns[1:]:
    cohort_preview[column] = cohort_preview[column].map(
        lambda value: "—" if pd.isna(value) else f"{value:.1f}%"
    )
display(cohort_preview)
print(summary["cohort_retention"]["partial_month_note"])
"""),
            code(r"""
for chart in [
    "images/customer_analytics/02_customer_count_by_segment.png",
    "images/customer_analytics/03_revenue_by_segment.png",
    "images/customer_analytics/04_cohort_retention_heatmap.png",
]:
    display(Image(filename=str(PROJECT_ROOT / chart), width=850))
"""),
            md("""
## Business Insights

- Champions account for about 22% of customers but 68% of identified-customer revenue, showing strong value concentration.
- Hibernating customers are numerous but contribute a small revenue share; low-cost testing is more proportionate than blanket discounting.
- Rule ordering matters: every customer receives exactly one interpretable segment and action.
- Cohort month 0 is 100% by construction. Cells whose purchase month is December 2011 are partial because data stop on 9 December and should not be compared with complete-month retention cells.

## Assumptions

- The snapshot is one day after the latest observed invoice date.
- Completed identified sales are the valid basis for RFM and cohort membership.
- Segment actions are hypotheses for business use, not measured treatment effects.

## Limitations

- The observation window gives customers unequal exposure time.
- No verified churn label, demographics, acquisition source, or campaign response is available.
- Cohort retention measures observed purchasing, not customer sentiment or profitability.

## Next Steps

- Validate segment actions through controlled experiments.
- Refresh RFM scores on a consistent cadence with a clearly documented snapshot.
- Track complete-month cohort cells separately from partial refresh periods.
"""),
        ],
    )


def statistics_notebook() -> nbformat.NotebookNode:
    return notebook(
        "04 — Statistical Analysis",
        [
            md("""
## Objective

Present the prespecified non-parametric hypotheses, Holm-adjusted evidence, effect sizes, and limitations from the reusable statistical-analysis phase.

## Business Questions

- Which customer metrics move together monotonically?
- How different are repeat and one-time customer-value distributions?
- How different are UK and international order-value distributions?
- Is repeat status associated with UK versus international geography?

## Inputs

- `reports/statistics/hypothesis_tests.csv`
- `reports/statistics/correlation_matrix.csv`
- `reports/statistics/statistical_summary.json`
- Existing charts under `images/statistics/`
- Statistical constants from `retail_analytics.statistical_analysis`

## Methodology

Read executed test outputs rather than rerunning them. Spearman tests address monotonic association, Mann–Whitney U tests compare distributions, and Pearson's chi-square test assesses categorical independence. Holm correction controls family-wise error within the correlation and confirmatory-test families.

## Code
"""),
            code(COMMON_SETUP + r"""
from retail_analytics.statistical_analysis import ALPHA, CORRELATION_FEATURES

tests = pd.read_csv(PROJECT_ROOT / "reports" / "statistics" / "hypothesis_tests.csv")
correlations = pd.read_csv(
    PROJECT_ROOT / "reports" / "statistics" / "correlation_matrix.csv", index_col=0
)
summary = load_json("reports/statistics/statistical_summary.json")
print(f"Tests reported: {len(tests)}; alpha={ALPHA}")
"""),
            code(r"""
confirmatory = tests.loc[tests["family"].eq("confirmatory_group_tests")].copy()
hypotheses = confirmatory[
    ["test_name", "comparison", "null_hypothesis", "alternative_hypothesis", "sample_size_total"]
]
display(hypotheses)
"""),
            code(r"""
display(correlations.round(3))
strongest = (
    tests.loc[tests["family"].eq("spearman_correlations")]
    .assign(abs_effect=lambda frame: frame["effect_size"].abs())
    .nlargest(8, "abs_effect")
    [["comparison", "statistic", "adjusted_p_value", "effect_magnitude"]]
    .copy()
)
strongest["statistic"] = strongest["statistic"].map(lambda value: f"{value:.3f}")
strongest["adjusted_p_value"] = strongest["adjusted_p_value"].map(
    lambda value: "< machine precision" if value == 0 else f"{value:.3e}"
)
display(strongest)
"""),
            md("""
## Results
"""),
            code(r"""
result_view = confirmatory[
    ["comparison", "sample_size_group_1", "sample_size_group_2", "group_1_summary", "group_2_summary",
     "statistic_name", "statistic", "raw_p_value", "adjusted_p_value", "effect_size_name",
     "effect_size", "effect_magnitude", "reject_null"]
].copy()
for column in ["raw_p_value", "adjusted_p_value"]:
    result_view[column] = result_view[column].map(
        lambda value: "< machine precision" if value == 0 else f"{value:.3e}"
    )
result_view["statistic"] = result_view["statistic"].map(lambda value: f"{value:,.3f}")
result_view["effect_size"] = result_view["effect_size"].map(lambda value: f"{value:.3f}")
display(result_view)

interpretations = confirmatory[["comparison", "business_interpretation", "limitations"]]
display(interpretations)
"""),
            code(r"""
for chart in [
    "images/statistics/01_spearman_correlation_heatmap.png",
    "images/statistics/02_repeat_customer_value_comparison.png",
    "images/statistics/04_geographic_repeat_rate.png",
]:
    display(Image(filename=str(PROJECT_ROOT / chart), width=850))
"""),
            md("""
## Business Insights

- Repeat customers have much higher observed monetary value than one-time customers, with a **large** rank-biserial effect; the result is commercially more informative than its extremely small p-value alone.
- International orders have a higher median value than UK orders, but the rank-biserial effect is **small**, so market volume, fulfilment cost, and mix remain important.
- UK versus international repeat rates are nearly identical; Cramer's V is negligible and the adjusted p-value does not support an association.
- Strong correlations among frequency, value, units, and active span reflect related behavior, not proof that changing one will cause another to change.

## Assumptions

- Observations meet the operational definitions in the validated RFM and order reports.
- Holm correction is applied within the two prespecified hypothesis families.
- Effect-size direction follows the documented group ordering.

## Limitations

- The analysis is observational and cannot identify causal effects.
- Repeat orders from the same customer weaken strict order-level independence.
- Large samples can make small effects statistically significant; effect magnitude and business cost must guide decisions.
- Unequal customer exposure time and wholesale-like activity can influence ranks.

## Next Steps

- Define practical effect thresholds before campaign decisions.
- Use experiments to estimate causal response to retention actions.
- Add margin and fulfilment measures before interpreting geographic value differences commercially.
"""),
        ],
    )


def clustering_notebook() -> nbformat.NotebookNode:
    return notebook(
        "05 — K-Means Customer Clustering",
        [
            md("""
## Objective

Explain feature preparation, K=2–10 evaluation, five-seed stability, the K=2 mathematical benchmark, and the operational K=4 customer profiles using existing clustering outputs.

## Business Questions

- How were skewed RFM features made suitable for K-Means?
- Which K is mathematically strongest, and why is a different K used operationally?
- Are the candidate solutions stable and free of tiny clusters?
- What do the final four descriptive profiles suggest for targeting?

## Inputs

- `reports/clustering/k_evaluation.csv`
- `reports/clustering/cluster_profiles.csv`
- `reports/clustering/rfm_cluster_comparison.csv`
- `reports/clustering/clustering_summary.json`
- Existing charts under `images/clustering/`
- Reusable constants from `retail_analytics.clustering`

## Methodology

Read evaluated and exported model outputs. The notebook does not refit K-Means. Production preprocessing applies `log1p` to recency, frequency, and monetary value, then standardises the transformed features. PCA is used only for two-dimensional visualisation.

## Code
"""),
            code(COMMON_SETUP + r"""
from retail_analytics.clustering import (
    CLUSTERING_FEATURES,
    FINAL_CLUSTER_LABELS,
    KMEANS_N_INIT,
    RANDOM_STATE,
    STABILITY_SEEDS,
)

evaluation = pd.read_csv(PROJECT_ROOT / "reports" / "clustering" / "k_evaluation.csv")
profiles = pd.read_csv(PROJECT_ROOT / "reports" / "clustering" / "cluster_profiles.csv")
summary = load_json("reports/clustering/clustering_summary.json")
print("Features:", CLUSTERING_FEATURES)
print("Seeds:", STABILITY_SEEDS)
print(f"Final fit contract: random_state={RANDOM_STATE}, n_init={KMEANS_N_INIT}")
"""),
            code(r"""
evaluation_view = evaluation[
    ["k", "inertia", "silhouette_score", "calinski_harabasz_score", "davies_bouldin_score",
     "minimum_cluster_share_pct", "mean_pairwise_ari", "minimum_pairwise_ari",
     "selection_rank_sum", "metric_optimal", "operational_chosen"]
].copy()
for column in ["silhouette_score", "davies_bouldin_score", "mean_pairwise_ari", "minimum_pairwise_ari"]:
    evaluation_view[column] = evaluation_view[column].map(lambda value: f"{value:.3f}")
evaluation_view["inertia"] = evaluation_view["inertia"].map(lambda value: f"{value:,.1f}")
evaluation_view["calinski_harabasz_score"] = evaluation_view["calinski_harabasz_score"].map(lambda value: f"{value:,.1f}")
evaluation_view["minimum_cluster_share_pct"] = evaluation_view["minimum_cluster_share_pct"].map(lambda value: f"{value:.2f}%")
display(evaluation_view)
"""),
            md("""
## Results

K=2 is preserved as the **metric benchmark** because it has the best composite rank sum. K=4 is the **operational solution** because it retains acceptable separation, excellent stability, a 20.48% minimum cluster share, no tiny clusters, and materially more targeting resolution. This is a documented business choice, not a claim that K=4 is mathematically superior to K=2.
"""),
            code(r"""
comparison = pd.DataFrame([
    {
        "Decision role": "Metric benchmark",
        "K": summary["metric_optimal_k"],
        "Composite rank": summary["metric_optimal_metrics"]["selection_rank_sum"],
        "Silhouette": summary["metric_optimal_metrics"]["silhouette_score"],
        "Davies-Bouldin": summary["metric_optimal_metrics"]["davies_bouldin_score"],
        "Mean ARI": summary["metric_optimal_metrics"]["mean_pairwise_ari"],
        "Minimum cluster share": f"{summary['metric_optimal_metrics']['minimum_cluster_share_pct']:.2f}%",
    },
    {
        "Decision role": "Operational solution",
        "K": summary["operational_chosen_k"],
        "Composite rank": summary["operational_chosen_metrics"]["selection_rank_sum"],
        "Silhouette": summary["operational_chosen_metrics"]["silhouette_score"],
        "Davies-Bouldin": summary["operational_chosen_metrics"]["davies_bouldin_score"],
        "Mean ARI": summary["operational_chosen_metrics"]["mean_pairwise_ari"],
        "Minimum cluster share": f"{summary['operational_chosen_metrics']['minimum_cluster_share_pct']:.2f}%",
    },
])
display(comparison)
"""),
            code(r"""
profile_view = profiles[
    ["cluster_id", "cluster_label", "customer_count", "customer_share_pct", "revenue_share_pct",
     "median_recency_days", "median_frequency_orders", "median_monetary_value_gbp",
     "repeat_customer_rate_pct", "dominant_rfm_segment", "recommended_action"]
].copy()
profile_view["customer_count"] = profile_view["customer_count"].map(lambda value: f"{value:,.0f}")
for column in ["customer_share_pct", "revenue_share_pct", "repeat_customer_rate_pct"]:
    profile_view[column] = profile_view[column].map(lambda value: f"{value:.2f}%")
profile_view["median_monetary_value_gbp"] = profile_view["median_monetary_value_gbp"].map(
    lambda value: f"GBP {value:,.2f}"
)
display(profile_view)

evidence = profiles[["cluster_id", "cluster_label", "label_basis"]]
display(evidence)
"""),
            code(r"""
for chart in [
    "images/clustering/01_k_evaluation.png",
    "images/clustering/02_cluster_size_and_revenue.png",
    "images/clustering/03_pca_cluster_projection.png",
    "images/clustering/04_rfm_cluster_comparison.png",
]:
    display(Image(filename=str(PROJECT_ROOT / chart), width=900))
"""),
            md("""
## Business Insights

- High-Value Champions are 20.48% of customers and contribute 74.00% of identified-customer revenue, supporting protective service and relevant loyalty treatment.
- Recent Growth Customers are comparatively recent but lower in frequency and value, supporting measured next-purchase nurturing.
- Lapsed Established Customers have meaningful prior frequency and value but much higher recency, making profile-based reactivation more proportionate than broad discounting.
- Dormant Low-Value Customers are the largest group but contribute 3.56% of revenue; low-cost re-engagement tests fit that profile.
- The five-seed mean ARI for K=4 is about 0.997, indicating highly stable assignments under the tested initialisations.

## Assumptions

- Recency, frequency, and monetary value are valid descriptive inputs for customer grouping.
- `log1p` and standardisation reduce scale/skew dominance without changing original-unit profile reporting.
- The 2% minimum-share and 0.80 stability floors define operational usability.

## Limitations

- K-Means imposes spherical partitions in transformed feature space.
- PCA is only a visual projection and is not used to fit or select clusters.
- Clusters are **descriptive, not causal or predictive**; labels do not establish campaign response, churn, or future value.
- The historical observation window and wholesale-like customers influence RFM measures.

## Next Steps

- Validate cluster actions through controlled experiments and future-period outcomes.
- Monitor cluster-size and profile drift after each refresh.
- Retain both K=2 benchmark metrics and K=4 operational evidence in governance reviews.
"""),
        ],
    )


NOTEBOOK_BUILDERS = {
    "01_data_validation_and_cleaning.ipynb": validation_notebook,
    "02_sql_and_exploratory_analysis.ipynb": sql_eda_notebook,
    "03_rfm_and_cohort_analysis.ipynb": rfm_notebook,
    "04_statistical_analysis.ipynb": statistics_notebook,
    "05_kmeans_customer_clustering.ipynb": clustering_notebook,
}


def build_all() -> list[Path]:
    NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for filename, builder in NOTEBOOK_BUILDERS.items():
        path = NOTEBOOK_DIR / filename
        nbformat.write(builder(), path)
        paths.append(path)
        print(f"Built {path.relative_to(PROJECT_ROOT)}")
    return paths


def execute_all(paths: list[Path]) -> None:
    for path in paths:
        print(f"Executing {path.relative_to(PROJECT_ROOT)}...")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "jupyter",
                "nbconvert",
                "--to",
                "notebook",
                "--execute",
                "--inplace",
                "--ExecutePreprocessor.timeout=180",
                str(path),
            ],
            cwd=PROJECT_ROOT,
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute each generated notebook in place with the current Python environment.",
    )
    args = parser.parse_args()
    paths = build_all()
    if args.execute:
        execute_all(paths)


if __name__ == "__main__":
    main()
