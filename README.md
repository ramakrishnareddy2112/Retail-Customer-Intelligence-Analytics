# Retail Customer Intelligence and Retention Analytics

An end-to-end retail analytics project that turns Online Retail II transactions into
validated sales metrics, a SQLite star schema, SQL business outputs, EDA charts,
RFM customer segments, cohort retention matrices, and action-ready customer reports.

## Project Status

The first reproducible analytics release is complete and ready for an initial Git
commit.

| Area | Status |
|---|---|
| Raw validation and data-quality profile | Complete |
| Cleaning, deduplication, transaction classification, and partition reconciliation | Complete |
| SQLite star schema with dimensions, facts, indexes, and quality checks | Complete |
| SQL analysis exports | Complete: 13 CSV outputs |
| Exploratory data analysis | Complete: 14 PNG charts and 2 Plotly HTML charts |
| RFM customer segmentation and cohort retention | Complete |
| Automated tests | Passing: 11 tests |

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
```

Run tests:

```bash
.venv\Scripts\python.exe -m pytest -q
```

Expected result for the current repository state:

```text
11 passed
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
