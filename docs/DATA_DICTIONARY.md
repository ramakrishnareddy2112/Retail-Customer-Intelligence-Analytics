# Data Dictionary and Contract

## Raw UCI Fields

| Field | Expected type | Meaning | Validation |
|---|---|---|---|
| Invoice | string | Transaction identifier; `C` prefix indicates cancellation | Non-empty |
| StockCode | string | Product identifier | Non-empty |
| Description | string | Product description | May be missing |
| Quantity | integer | Units on the transaction line | Negative values indicate returns |
| InvoiceDate | datetime | Transaction timestamp | Must parse |
| Price | numeric | Unit price in GBP | Investigate zero/negative values |
| Customer ID | nullable string | Customer identifier | Missing IDs expected |
| Country | string | Customer country | Standardise whitespace |

The workbook may use slightly different labels between sheets. The ingestion layer
will map raw labels into the canonical names below.

## Canonical Transaction Fields

| Field | Type | Derivation |
|---|---|---|
| invoice_no | string | Standardised invoice identifier |
| stock_code | string | Standardised product identifier |
| description | string | Trimmed product description |
| quantity | integer | Raw quantity |
| invoice_date | datetime | Parsed transaction timestamp |
| unit_price | float | Raw unit price in GBP |
| customer_id | nullable string | Identifier without decimal suffix |
| country | category/string | Trimmed country label |
| line_revenue | float | `quantity * unit_price` |
| is_cancelled | boolean | Invoice starts with `C`, case-insensitive |
| is_return | boolean | Cancelled invoice or negative quantity |
| is_completed_sale | boolean | Positive quantity and price, not cancelled |
| has_customer_id | boolean | Customer identifier is present |
| source_sheet | string | Workbook sheet used for lineage |

## Customer Analytics Fields

| Field | Meaning |
|---|---|
| recency_days | Days from snapshot date to last completed purchase |
| frequency_orders | Distinct completed invoices |
| monetary_value | Completed-sales revenue |
| first_purchase | First observed completed purchase |
| last_purchase | Last observed completed purchase |
| active_span_days | Days between first and last observed purchase |
| average_order_value | Monetary value divided by distinct orders |
| r_score | Quantile-based recency score, 5 is best |
| f_score | Quantile-based frequency score, 5 is best |
| m_score | Quantile-based monetary score, 5 is best |
| rfm_score | Concatenated or summed RFM score |
| rfm_segment | Named, rule-based business segment |
| cluster | K-Means segment selected after evaluation |

## Exclusion and Interpretation Rules

1. Missing customer IDs are excluded only from customer-level analysis.
2. Returns remain available for return-rate and product-quality analysis.
3. Completed-sales KPIs exclude cancellations, negative quantities, and non-positive prices.
4. Duplicate removal will distinguish exact duplicates from legitimate repeated lines.
5. The final month is checked for incomplete-period bias.
6. Extreme values are flagged and sensitivity-tested; genuine wholesale activity is retained.
7. Monetary fields are GBP and are not converted without an explicit exchange-rate source.

