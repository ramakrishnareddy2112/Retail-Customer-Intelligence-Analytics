# Power BI Build Guide

This guide builds a report from the UTF-8 CSV package in `dashboard/data/`.
The package contains validated historical sales and customer analytics. It does
not contain profit, margin, demographics, churn probability, or predictive CLV.

## 1. Generate and Import the Data

Regenerate the package from existing processed outputs:

```powershell
python scripts/build_dashboard_exports.py
```

In Power BI Desktop:

1. Open **File > Options and settings > Options > Data Load**.
2. Clear **Auto date/time for new files**. The supplied `dim_date` table is the
   only supported date dimension.
3. Select **Get data > Text/CSV** and import each file from `dashboard/data/`:
   - `dim_date.csv`
   - `fact_orders.csv`
   - `dim_customer.csv`
   - `fact_product_month.csv`
   - `fact_country_month.csv`
   - `fact_returns_month.csv`
   - `cohort_retention.csv`
   - `segment_summary.csv`
   - `cluster_summary.csv`
   - `kpi_snapshot.csv`
4. Confirm **File origin = 65001: Unicode (UTF-8)** for every file.
5. Choose **Transform Data**, not Load, and rename each query to the filename
   without `.csv`.
6. Apply `dashboard/retail_intelligence_theme.json` with
   **View > Themes > Browse for themes**.

Do not append the raw workbook or the processed line-level Parquet files to this
model. The export script is the governed semantic boundary.

## 2. Set Column Data Types

Use `dashboard/DATA_DICTIONARY.md` for every field. The critical settings are:

| Table / columns | Power BI type |
|---|---|
| All `*_date`, `date`, `month_start`, `acquisition_month`, `purchase_month`, `data_through_date` | Date |
| IDs, country, labels, descriptions, notes | Text |
| Counts, scores, units, month/quarter numbers, cluster ID | Whole number |
| GBP values and retention/customer/value shares | Decimal number |
| `is_*` fields | True/False |

Keep `customer_id`, `order_id`, and `stock_code` as **Text**. Do not allow Power
Query to convert customer IDs to decimal numbers.

Percentage columns ending `_pct` contain values on a 0–100 scale. If used as raw
columns, divide by 100 in a display measure before applying Power BI percentage
formatting. Measures in `POWER_BI_MEASURES.md` already return ratios on a 0–1
scale and should be formatted directly as percentages.

## 3. Date Table and Sorting

1. In Model view, select `dim_date`.
2. Choose **Table tools > Mark as date table > date**.
3. Set `dim_date[month_name]` to **Sort by column > month_number**.
4. Set `dim_date[year_month]` to **Sort by column > month_start**.
5. Hide `year`, `quarter`, and `month_number` from report view only if report
   authors will use the hierarchy instead.

December 2011 contains data only through 9 December. Keep
`dim_date[is_partial_period]` available for filters and annotations; do not hide
the period or extrapolate it to a full month.

## 4. Relationships and Cardinality

Create these active, single-direction relationships:

| One side | Many side | Cardinality | Active | Direction |
|---|---|---|---|---|
| `dim_date[date]` | `fact_orders[order_date]` | 1:* | Yes | Single |
| `dim_date[date]` | `fact_product_month[month_start]` | 1:* | Yes | Single |
| `dim_date[date]` | `fact_country_month[month_start]` | 1:* | Yes | Single |
| `dim_date[date]` | `fact_returns_month[month_start]` | 1:* | Yes | Single |
| `dim_customer[customer_id]` | `fact_orders[customer_id]` | 1:* | Yes | Single |
| `segment_summary[rfm_segment]` | `dim_customer[rfm_segment]` | 1:* | Yes | Single |
| `cluster_summary[cluster_id]` | `dim_customer[cluster_id]` | 1:* | Yes | Single |

Anonymous orders have a blank `customer_id` and therefore do not join to
`dim_customer`. This is deliberate: they remain in aggregate sales measures but
cannot support customer history, RFM, cohort, or cluster analysis.

For `cohort_retention`, use its native `acquisition_month`, `purchase_month`, and
`cohort_month_index` fields in cohort visuals. Keep it disconnected by default so
ordinary sales-date slicers do not unintentionally remove cohort cells. If a
governed use case requires date interaction, create an **inactive** relationship
from `dim_date[date]` to `cohort_retention[purchase_month]` and activate it only in
an explicit measure.

Keep `kpi_snapshot` disconnected. It is a validation reference, not a fact table.
Avoid bidirectional filters and fact-to-fact relationships.

## 5. Measures and Formatting

Create the `_Measures` table and copy the DAX from
`dashboard/POWER_BI_MEASURES.md`.

- Format GBP measures with the `£` symbol, thousands separators, and two decimals.
- Format whole-number KPIs with thousands separators and no decimals.
- Format ratio measures as percentages with two decimals.
- Use display units only on axes where space is constrained; tooltips should show
  complete values.
- Label customer monetary fields as **Historical Customer Value**, never CLV.

## 6. Report Canvas and Navigation

Use a 16:9 canvas. Add a consistent top bar containing the page title, data-through
date (`09 Dec 2011`), and page navigation. Place this annotation on every page:

> December 2011 is partial and contains data only through 9 December 2011.

Use blue for primary sales, teal/green for positive supporting series, amber for
attention, and red for risk/returns. Do not use gradients, shadows, decorative
icons, or color as the only carrier of meaning.

## 7. Page 1 — Executive Overview

### Slicers

- `dim_date[year]`
- `dim_date[month_name]`
- `fact_orders[country]`
- `fact_orders[is_identified_customer]`

Synchronise the year and country slicers across Pages 1 and 3.

### Visuals

1. **Six KPI cards:** `[Total Revenue]`, `[Total Orders]`, `[Units Sold]`,
   `[Average Order Value]`, `[Identified Customers]`, and
   `[Repeat Customer Rate]`.
2. **Line chart — Monthly revenue:**
   - X-axis: `dim_date[year_month]`
   - Y-axis: `[Total Revenue]`
   - Tooltip: `[Previous Month Revenue]`, `[Month-over-Month Growth]`,
     `[Total Orders]`, `[Average Order Value]`
   - Add a visible annotation at December 2011 rather than treating it as a full
     comparison month.
3. **Clustered column chart — Revenue and orders by month:**
   - X-axis: `dim_date[year_month]`
   - Column: `[Total Revenue]`
   - Line: `[Total Orders]`
4. **Horizontal bar — Top countries by revenue:**
   - Category: `fact_country_month[country]`
   - Value: `SUM(fact_country_month[revenue_gbp])`
   - Top N: 10 by revenue
5. **100% stacked bar — Identified versus anonymous revenue:**
   - Category: `fact_orders[is_identified_customer]`
   - Value: `[Total Revenue]`
6. **Validation card:** show `kpi_snapshot[data_through_date]` and the partial-note
   text in a small bordered information panel.

### Tooltip

Create a hidden **Month Tooltip** page with year-month, total revenue, orders,
AOV, MoM growth, return value, and return-value-to-sales ratio.

## 8. Page 2 — Customer Segmentation

### Slicers

- `dim_customer[rfm_segment]`
- `dim_customer[cluster_label]`
- `dim_customer[is_repeat_customer]`

### Visuals

1. **Four KPI cards:** `[Historical Customer Value]`, `[Repeat Customers]`,
   `[Repeat Customer Rate]`, and `[At Risk Customers]`.
2. **Horizontal bar — Customers by RFM segment:**
   - Category: `segment_summary[rfm_segment]`
   - Value: `SUM(segment_summary[customer_count])`
   - Tooltip: customer share, historical value share, median recency,
     recommended action
3. **Horizontal bar — Historical value by RFM segment:**
   - Category: `segment_summary[rfm_segment]`
   - Value: `SUM(segment_summary[historical_customer_value_gbp])`
4. **Clustered bar — Customer share versus historical-value share by cluster:**
   - Category: `cluster_summary[cluster_label]`
   - Values: `SUM(cluster_summary[customer_share_pct])` and
     `SUM(cluster_summary[historical_value_share_pct])`
   - Show labels as percentages; divide the raw fields by 100 in display measures.
5. **Scatter — Customer recency and frequency:**
   - X-axis: `dim_customer[recency_days]`
   - Y-axis: `dim_customer[frequency_orders]`
   - Size: `dim_customer[monetary_value_gbp]`
   - Legend: `dim_customer[cluster_label]`
   - Details: `dim_customer[customer_id]`
   - Tooltip: RFM segment, historical monetary value, AOV, repeat status
6. **Action matrix:** RFM segment, priority, segment rule, recommended action.

### Drill-through and Tooltip

Create a hidden **Customer Detail** drill-through page using
`dim_customer[customer_id]`. Include first/last purchase dates, historical value,
frequency, AOV, RFM segment, cluster label, and an order table with order date,
country, revenue, units, and distinct products.

Create a **Customer Profile Tooltip** using the same profile fields but no order
table. Do not label historical value as predicted future value.

## 9. Page 3 — Product, Geography and Returns

### Slicers

- `dim_date[year]`
- `dim_date[month_name]`
- `fact_country_month[country]`
- `fact_product_month[stock_code]`

### Visuals

1. **Horizontal bar — Top 15 products by revenue:**
   - Category: `fact_product_month[description]`
   - Value: `SUM(fact_product_month[revenue_gbp])`
   - Tooltip: stock code, units, orders, identified customers
2. **Matrix — Product performance by month:**
   - Rows: description, stock code
   - Columns: month start
   - Values: revenue, units, orders
3. **Horizontal bar — Country revenue:**
   - Category: country
   - Value: revenue
   - Tooltip: orders, units, identified customers
4. **Line chart — Monthly return value:**
   - X-axis: `fact_returns_month[month_start]`
   - Y-axis: `[Return Value]`
   - Tooltip: signed return value, return lines, returned units,
     `[Return Value to Sales Ratio]`
5. **Order-value distribution:** use a binned column derived from
   `fact_orders[order_revenue_gbp]`; show order count by bin and keep full values in
   the tooltip.
6. **Two cards:** `[Return Value]` and `[Return Value to Sales Ratio]`.

Outliers remain included in every visual. The validated source flags unusual
quantity, price, and revenue lines rather than deleting plausible wholesale
activity. Do not apply arbitrary visual-level exclusions to “clean up” charts.

### Drill-through

Create a hidden **Product Detail** drill-through page using
`fact_product_month[stock_code]`. Include description, monthly revenue, units,
orders, and identified customers. A country drill-through may use
`fact_country_month[country]` with the equivalent monthly trend.

## 10. Page 4 — Retention and Advanced Analytics

### Slicers

- `cohort_retention[acquisition_month]`
- `cohort_retention[cohort_month_index]`
- `cluster_summary[cluster_label]`

### Visuals

1. **Cohort heatmap matrix:**
   - Rows: `cohort_retention[acquisition_month]`
   - Columns: `cohort_retention[cohort_month_index]`
   - Values: `MAX(cohort_retention[retention_pct])`
   - Apply a restrained single-hue blue conditional-format scale and show values.
   - Use `is_partial_period` in the tooltip and annotate partial December cells.
2. **Line chart — Retention curve:**
   - X-axis: cohort month index
   - Y-axis: average retention percentage
   - Legend: acquisition year or selected acquisition month
3. **Cluster profile table:** label, customer count/share, historical value/share,
   median R/F/M, repeat rate, dominant RFM segment, recommended action.
4. **Cluster contribution bar:** cluster label with customer share and historical
   value share.
5. **Two evidence cards/text panels:**
   - Metric benchmark: K=2, composite rank 6, silhouette 0.438.
   - Operational solution: K=4, composite rank 9, silhouette 0.366, mean stability
     ARI 0.997, minimum cluster share 20.48%.
6. **Methodology note:** clusters are descriptive, not causal or predictive; PCA
   is used only for visualisation in the analytical report, not model fitting.

## 11. Accessibility and Professional Formatting

- Minimum body font: 10 pt; titles: 12–14 pt; KPI callouts: 24–32 pt.
- Maintain at least 4.5:1 text contrast. Use dark text on white backgrounds.
- Add descriptive alt text to every visual.
- Set logical keyboard tab order from slicers to KPIs to detail visuals.
- Pair red/amber/green with labels or icons; never rely on color alone.
- Limit each chart to a decision-relevant number of categories.
- Use consistent two-decimal GBP and percentage formatting.
- Keep visual borders subtle and backgrounds flat; avoid gradients and decoration.
- Use the full cluster names: High-Value Champions, Recent Growth Customers,
  Lapsed Established Customers, and Dormant Low-Value Customers.

## 12. Final Validation Checklist

Before publishing, clear all filters and verify:

- [ ] Total Revenue = GBP 20,476,260.45
- [ ] Total Orders = 40,077
- [ ] Units Sold = 11,205,148
- [ ] Identified Customers = 5,878
- [ ] Repeat Customers = 4,255
- [ ] Historical Customer Value = GBP 17,374,804.27
- [ ] Signed return value in the fact = GBP -1,462,050.61
- [ ] RFM segment customer total = 5,878
- [ ] Cluster customer total = 5,878
- [ ] December 2011 is visibly labelled partial
- [ ] No customer or order IDs are formatted as decimal numbers
- [ ] No report filter removes flagged outlier activity by default
- [ ] Relationships are single-direction with no ambiguous paths
- [ ] Percentage columns/measures use the correct 0–100 versus 0–1 convention

## 13. Screenshot Checklist

Capture a 16:9 screenshot of each navigational page after validation:

- [ ] Executive Overview — KPI cards, trend, country, identity split, partial note
- [ ] Customer Segmentation — segment/cluster profiles, scatter, actions
- [ ] Product, Geography and Returns — product, country, returns, order distribution
- [ ] Retention and Advanced Analytics — cohort matrix, curve, K=2/K=4 evidence
- [ ] Customer Detail drill-through with a non-sensitive example customer ID
- [ ] Product Detail drill-through
- [ ] Month and customer tooltip pages in tooltip preview mode

Do not publish screenshots containing filters that make the headline values appear
to be project-wide totals when they are filtered subsets.
