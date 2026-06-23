# Raw Data Quality Review

## Validation Status

The official UCI Online Retail II workbook passed the minimum data contract. Both
yearly worksheets loaded successfully and every invoice timestamp was parsed.

## Raw Profile

| Metric | Result |
|---|---:|
| Raw transaction lines | 1,067,371 |
| Exact duplicates within individual sheets | 12,133 |
| Exact duplicates across the complete workbook | 34,335 |
| Expected unique transaction lines | 1,033,036 |
| Completed-sale rows before deduplication | 1,041,670 |
| Return/cancellation rows before deduplication | 22,951 |
| Anonymous rows | 243,007 (22.7669%) |
| Missing descriptions | 4,382 (0.4105%) |
| Customers | 5,942 |
| Products | 5,304 |
| Countries | 43 |
| Invoices | 53,628 |
| Date coverage | 1 Dec 2009 to 9 Dec 2011 |

## Financial Reconciliation Before Cleaning

| Measure | Value |
|---|---:|
| Completed-sales line value | GBP 20,972,594.57 |
| Return/cancellation signed value | GBP -1,526,667.86 |
| All signed transaction value | GBP 19,287,250.57 |

These are raw, pre-deduplication values and must not be published as final KPIs.

## Cleaning Decisions

1. Remove only exact duplicates based on the eight original transaction fields.
2. Ignore `source_sheet` when finding duplicates so repeated records across yearly
   worksheets are detected; retain it afterward for lineage.
3. Keep completed sales with missing customer IDs for aggregate sales analysis.
4. Exclude anonymous sales from RFM, cohort, and customer-level analysis.
5. Preserve returns and cancellations in a separate analytical table.
6. Preserve non-sale records with zero/non-positive prices in an exclusions table.
7. Flag IQR outliers but do not remove them automatically because wholesale orders
   may be legitimate business activity.
8. Reconcile every unique record to exactly one primary transaction partition.

## Interpretation Limits

- Missing customer IDs reduce customer-level coverage but do not invalidate aggregate
  sales analysis.
- Exact-row deduplication assumes identical repeated lines are data duplication. A
  sensitivity note will accompany customer and revenue results.
- The final month is partial and will be labelled in time-trend reporting.
- Profit cannot be calculated because product cost is unavailable.

