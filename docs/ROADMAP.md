# Advanced Project Roadmap

## Phase 1 - Foundation and Data Contract

**Target:** Meeting 3, 24 June 2026

- Confirm scope, stakeholders, and business questions.
- Create repository structure and reproducible environment.
- Acquire Online Retail II from UCI.
- Record dataset license, fields, limitations, and assumptions.
- Profile workbook sheets, date range, row count, and schema consistency.

**Evidence:** README, project charter, data dictionary, project plan, raw validation.

## Phase 2 - Data Preparation and SQL

**Target:** Meeting 4, 27 June 2026

- Combine both workbook years into one canonical transaction table.
- Standardise field names and data types.
- Identify duplicates, missing identifiers, invalid prices, cancellations, and returns.
- Create completed-sales, returns, anonymous-sales, and customer-sales datasets.
- Add date, revenue, order, and customer features.
- Create SQLite star schema and quality-reconciliation tables.
- Implement documented business queries with joins, CTEs, and windows.

**Evidence:** Cleaning notebook, validation report, SQLite database, SQL scripts.

## Phase 3 - EDA, Statistics, RFM, and Cohorts

**Target:** Meeting 5, 1 July 2026

- Complete univariate, bivariate, temporal, geographic, and product analysis.
- Produce at least 12 decision-focused static and interactive charts.
- Test repeat-versus-one-time customer value and selected geographic differences.
- Calculate RFM features using a documented snapshot date.
- Build named customer segments and segment action matrix.
- Build monthly acquisition cohorts and retention heatmap.
- Calculate repeat purchase, revenue concentration, and inactivity indicators.

**Evidence:** EDA, statistics, RFM and cohort notebooks; chart exports; findings report.

## Phase 4 - Advanced Segmentation

**Target:** Before dashboard freeze

- Engineer customer features without future leakage.
- Apply log transformations and robust scaling decisions.
- Evaluate K=2 through K=10 with inertia, silhouette, and cluster-size checks.
- Check stability across random seeds.
- Profile the chosen clusters in original business units.
- Compare K-Means clusters with business-defined RFM segments.

**Evidence:** Modeling notebook, evaluation table, cluster profile, comparison matrix.

## Phase 5 - Dashboard and Final Communication

**Target:** Meeting 6, 4 July 2026

- Export validated Power BI fact and dimension tables.
- Build Executive Overview, Customer Segmentation, and Retention/Product pages.
- Implement documented DAX measures and interactive filters.
- Write executive summary, recommendations, limitations, and future work.
- Complete README, 10-12 slide presentation, and speaking notes.
- Run the entire pipeline from a clean environment and verify outputs.

**Evidence:** PBIX file, dashboard screenshots, report, presentation, reproducibility log.

## Quality Gates

| Gate | Requirement |
|---|---|
| Data | Row and revenue reconciliation passes |
| Analysis | No unsupported demographic, profit, or causal claims |
| Statistics | Assumptions, effect size, and limitations reported |
| Segmentation | Every segment is mutually understandable and actionable |
| Modeling | Cluster choice is evaluated, stable, and interpretable |
| Dashboard | KPI definitions match Python and SQL outputs |
| Delivery | Fresh setup can reproduce processed outputs |

