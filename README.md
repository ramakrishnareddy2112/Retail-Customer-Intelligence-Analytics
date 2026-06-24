# Retail Customer Intelligence and Retention Analytics

An end-to-end retail analytics project that turns Online Retail II transactions into
validated sales metrics, a SQLite star schema, SQL business outputs, EDA charts,
RFM customer segments, cohort retention matrices, non-parametric hypothesis tests,
and stable evidence-selected customer clusters.

## Project Status

The reproducible analytics project is published on GitHub and continues to evolve
through validated analytical phases.

| Area | Status |
|---|---|
| Raw validation and data-quality profile | Complete |
| Cleaning, deduplication, transaction classification, and partition reconciliation | Complete |
| SQLite star schema with dimensions, facts, indexes, and quality checks | Complete |
| SQL analysis exports | Complete: 13 CSV outputs |
| Exploratory data analysis | Complete: 14 PNG charts and 2 Plotly HTML charts |
| RFM customer segmentation and cohort retention | Complete |
| Statistical analysis with Holm-adjusted hypothesis tests | Complete |
| K-Means customer clustering with multi-seed stability evaluation | Complete |
| Automated tests | Passing: 22 tests |

December 2011 is a partial month. The source data ends on 2011-12-09, so December
2011 is labelled as partial and should not be compared with complete months as a
normal full-period result.

## Confirmed Core KPIs

These values are produced from the validated completed-sales pipeline.

| Metric | Value |
|---|---:|
| Unique cleaned transaction lines | 1,033,036 |
| Completed-sales lines | 1,007,913 |
| Completed-sales value | GBP 20,476,260.45 |
| Completed orders | 40,077 |
| Units sold | 11,205,148 |
| Average order value | GBP 510.92 |
| Median order value | GBP 302.22 |
| Identified customers | 5,878 |
| Identified customer revenue | GBP 17,374,804.27 |
| Anonymous revenue | GBP 3,101,456.18 |
| Repeat customers | 4,255 |
| Repeat customer rate | 72.39% |
| Signed returns/cancellations value | GBP -1,462,050.61 |

## Customer Segments

RFM segmentation uses identified completed sales only. The snapshot date is
2011-12-10, calculated as the maximum invoice date plus one day.

| Segment | Customers |
|---|---:|
| Champions | 1,290 |
| Loyal Customers | 656 |
| Potential Loyalists | 580 |
| New Customers | 235 |
| Cannot Lose Them | 223 |
| At Risk | 846 |
| Hibernating | 1,282 |
| Need Attention | 766 |

Segment definitions and recommended actions are exported to
`reports/customer_analytics/segment_action_plan.csv`.

## K-Means Customer Clustering

K=2 remains the mathematical metric-optimal benchmark with the lowest composite
rank sum (6). K=4 is the documented operational solution because it has the
second-best rank sum (9), acceptable separation (silhouette 0.366 and
Davies-Bouldin 0.929), very high five-seed stability (mean ARI 0.997), a 20.48%
minimum cluster share, no tiny clusters, diminishing inertia gains after K=4, and
more useful targeting resolution than a binary split.

The exported model uses K=4, `random_state=42`, and `n_init=20`. Labels describe
original-unit median recency, frequency, and monetary profiles; they do not imply
causal or predictive performance.

| ID | Business label | Customers | Customer share | Revenue share | Median R / F / M | Recommended action |
|---:|---|---:|---:|---:|---|---|
| 1 | High-Value Champions | 1,204 | 20.48% | 74.00% | 17 days / 13 orders / GBP 4,965.48 | Protect current value with recognition and relevant loyalty offers. |
| 2 | Recent Growth Customers | 1,261 | 21.45% | 6.15% | 25 days / 3 orders / GBP 729.25 | Nurture the next purchase with timely cross-sell and replenishment prompts. |
| 3 | Lapsed Established Customers | 1,455 | 24.75% | 16.29% | 186 days / 4 orders / GBP 1,447.74 | Prioritise profile-based reactivation using known categories. |
| 4 | Dormant Low-Value Customers | 1,958 | 33.31% | 3.56% | 404.5 days / 1 order / GBP 272.04 | Use low-cost re-engagement tests and suppress outreach if inactivity persists. |

## Notebooks

Five compact, executed notebooks provide stakeholder-readable walkthroughs of the
validated pipeline. They read reusable source contracts and generated reports;
they do not duplicate production analytics or reopen the raw workbook.

1. `notebooks/01_data_validation_and_cleaning.ipynb`
2. `notebooks/02_sql_and_exploratory_analysis.ipynb`
3. `notebooks/03_rfm_and_cohort_analysis.ipynb`
4. `notebooks/04_statistical_analysis.ipynb`
5. `notebooks/05_kmeans_customer_clustering.ipynb`

Rebuild and execute all five with the project Python 3.12 environment:

```bash
.venv\Scripts\python.exe scripts/build_notebooks.py --execute
```

## Dataset Attribution

This project uses **Online Retail II** from the UCI Machine Learning Repository.
The dataset contains transactions from a UK-based non-store retailer between
December 2009 and December 2011.

- Dataset page: https://archive.ics.uci.edu/dataset/502/online+retail+ii
- DOI: https://doi.org/10.24432/C5CG6D
- Dataset license: CC BY 4.0

The raw workbook is not committed to Git because of its size and source-data
ownership. Reproduce it with `python scripts/download_data.py`.

## Reproduce The Pipeline

Create and activate a Python environment, then install dependencies:

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the pipeline stages in order:

```bash
python scripts/download_data.py
python scripts/validate_raw_data.py
python scripts/clean_data.py
python scripts/build_sql_database.py
python scripts/run_sql_analysis.py
python scripts/run_eda.py
python scripts/run_customer_analytics.py
python scripts/run_statistical_analysis.py
python scripts/run_clustering.py
```

Run tests:

```bash
.venv\Scripts\python.exe -m pytest -q
```

Expected result for the current repository state:

```text
22 passed
```

## Key Outputs

- Raw profile: `reports/raw_data_profile.json`
- Cleaning summary: `reports/cleaning_summary.json`
- SQLite model summary: `reports/sql_model_summary.json`
- SQL outputs: `reports/sql_results/*.csv`
- EDA summary and tables: `reports/eda_summary.json`, `reports/eda_tables/*.csv`
- EDA charts: `images/eda/`
- RFM customer table: `data/processed/customer_rfm_segments.parquet` and `.csv`
- Customer analytics reports: `reports/customer_analytics/*.csv`
- Customer analytics summary: `reports/customer_analytics_summary.json`
- Customer analytics charts: `images/customer_analytics/`
- Statistical reports and summary: `reports/statistics/`
- Statistical charts: `images/statistics/`
- Customer cluster table: `data/processed/customer_clusters.parquet` and `.csv`
- Clustering evaluation, profiles, and summary: `reports/clustering/`
- Clustering charts: `images/clustering/`

Large raw, interim, and processed data files are intentionally excluded from Git.

## Analytical Scope

The project distinguishes four important transaction concepts:

- **Completed sales:** positive quantity and price, excluding cancelled invoices.
- **Returns/cancellations:** cancelled invoices or negative quantities.
- **Anonymous transactions:** valid sales without a customer identifier; included in
  aggregate sales analysis but excluded from RFM and cohort analysis.
- **Outliers:** investigated as possible wholesale activity; flagged but not
  automatically deleted.

The dataset does not contain demographics, unit cost, profit, marketing exposure,
or a verified churn label. Inactivity risk is derived transparently from recency
and purchase history.

## Repository Structure

```text
data/          Raw, interim, and processed data placeholders
dashboard/     Power BI file, dashboard guide, and screenshots
docs/          Project charter, roadmap, and data documentation
images/        Exported analytical charts
notebooks/     Numbered analysis notebooks
presentation/  Final presentation and speaking notes
reports/       Reproducible summaries, tables, and findings
scripts/       Command-line pipeline stages
sql/           Schema, quality checks, and business queries
src/           Reusable analytics package
tests/         Data-quality and logic tests
```

## License

Project code is released under the MIT License. See `LICENSE`.

The Online Retail II dataset is separately licensed by UCI under CC BY 4.0 and is
not included in this repository.
