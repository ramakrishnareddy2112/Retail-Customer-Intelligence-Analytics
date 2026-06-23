-- Every fact foreign key must resolve to its dimension.
-- name: foreign_key_resolution
SELECT 'orphan_sales_dates' AS check_name, COUNT(*) AS failure_count
FROM fact_sales f LEFT JOIN dim_date d ON f.date_key = d.date_key
WHERE d.date_key IS NULL
UNION ALL
SELECT 'orphan_sales_products', COUNT(*)
FROM fact_sales f LEFT JOIN dim_product p ON f.product_key = p.product_key
WHERE p.product_key IS NULL
UNION ALL
SELECT 'orphan_sales_countries', COUNT(*)
FROM fact_sales f LEFT JOIN dim_country c ON f.country_key = c.country_key
WHERE c.country_key IS NULL
UNION ALL
SELECT 'orphan_return_dates', COUNT(*)
FROM fact_returns f LEFT JOIN dim_date d ON f.date_key = d.date_key
WHERE d.date_key IS NULL
UNION ALL
SELECT 'orphan_return_products', COUNT(*)
FROM fact_returns f LEFT JOIN dim_product p ON f.product_key = p.product_key
WHERE p.product_key IS NULL;

-- Primary partition reconciliation after exact deduplication.
-- name: partition_reconciliation
SELECT
    (SELECT COUNT(*) FROM fact_sales) AS completed_sales,
    (SELECT COUNT(*) FROM fact_returns) AS returns_or_cancellations,
    (SELECT COUNT(*) FROM audit_exclusions) AS excluded_non_sales,
    (SELECT COUNT(*) FROM fact_sales)
      + (SELECT COUNT(*) FROM fact_returns)
      + (SELECT COUNT(*) FROM audit_exclusions) AS reconciled_unique_rows;

-- SQL values must match the Python cleaning summary to rounding tolerance.
-- name: sales_value_reconciliation
SELECT
    ROUND(SUM(line_revenue), 2) AS completed_sales_value_gbp,
    COUNT(DISTINCT invoice_no) AS completed_orders,
    COUNT(DISTINCT customer_key) AS identified_customers,
    SUM(CASE WHEN customer_key IS NULL THEN 1 ELSE 0 END) AS anonymous_sales_lines
FROM fact_sales;

-- name: returns_value_reconciliation
SELECT
    ROUND(SUM(signed_return_value), 2) AS signed_returns_value_gbp,
    COUNT(DISTINCT invoice_no) AS return_or_cancellation_invoices
FROM fact_returns;
