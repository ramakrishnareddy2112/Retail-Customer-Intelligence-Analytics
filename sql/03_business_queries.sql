-- Q1. Executive KPIs
-- name: executive_kpis
SELECT
    ROUND(SUM(line_revenue), 2) AS revenue_gbp,
    COUNT(DISTINCT invoice_no) AS orders,
    COUNT(DISTINCT customer_key) AS identified_customers,
    ROUND(SUM(line_revenue) / COUNT(DISTINCT invoice_no), 2) AS average_order_value_gbp,
    ROUND(
        SUM(CASE WHEN customer_key IS NOT NULL THEN line_revenue ELSE 0 END)
        / COUNT(DISTINCT customer_key),
        2
    ) AS revenue_per_identified_customer_gbp
FROM fact_sales;

-- Q2. Monthly revenue and month-over-month growth
-- name: monthly_revenue_growth
WITH monthly AS (
    SELECT
        d.year_month,
        ROUND(SUM(f.line_revenue), 2) AS revenue_gbp,
        COUNT(DISTINCT f.invoice_no) AS orders
    FROM fact_sales f
    JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY d.year_month
), compared AS (
    SELECT
        *,
        LAG(revenue_gbp) OVER (ORDER BY year_month) AS previous_month_revenue
    FROM monthly
)
SELECT
    year_month,
    revenue_gbp,
    orders,
    ROUND(100.0 * (revenue_gbp - previous_month_revenue) / previous_month_revenue, 2)
        AS month_over_month_growth_pct
FROM compared
ORDER BY year_month;

-- Q3. Country performance
-- name: country_performance
SELECT
    c.country_name,
    ROUND(SUM(f.line_revenue), 2) AS revenue_gbp,
    COUNT(DISTINCT f.invoice_no) AS orders,
    COUNT(DISTINCT f.customer_key) AS identified_customers,
    ROUND(SUM(f.line_revenue) / COUNT(DISTINCT f.invoice_no), 2) AS average_order_value_gbp
FROM fact_sales f
JOIN dim_country c ON f.country_key = c.country_key
GROUP BY c.country_name
ORDER BY revenue_gbp DESC;

-- Q4. Top products by revenue and volume
-- name: top_products
SELECT
    p.stock_code,
    p.product_description,
    SUM(f.quantity) AS units_sold,
    ROUND(SUM(f.line_revenue), 2) AS revenue_gbp,
    COUNT(DISTINCT f.invoice_no) AS order_count
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
GROUP BY p.product_key, p.stock_code, p.product_description
ORDER BY revenue_gbp DESC
LIMIT 20;

-- Q5. Top identified customers
-- name: top_customers
SELECT
    c.customer_id,
    c.primary_country,
    COUNT(DISTINCT f.invoice_no) AS orders,
    ROUND(SUM(f.line_revenue), 2) AS customer_revenue_gbp,
    ROUND(SUM(f.line_revenue) / COUNT(DISTINCT f.invoice_no), 2) AS average_order_value_gbp,
    MIN(d.full_date) AS first_purchase,
    MAX(d.full_date) AS last_purchase
FROM fact_sales f
JOIN dim_customer c ON f.customer_key = c.customer_key
JOIN dim_date d ON f.date_key = d.date_key
GROUP BY c.customer_key, c.customer_id, c.primary_country
ORDER BY customer_revenue_gbp DESC
LIMIT 20;

-- Q6. Repeat-customer rate among identified customers
-- name: repeat_customer_rate
WITH customer_orders AS (
    SELECT customer_key, COUNT(DISTINCT invoice_no) AS order_count
    FROM fact_sales
    WHERE customer_key IS NOT NULL
    GROUP BY customer_key
)
SELECT
    COUNT(*) AS identified_customers,
    SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) AS repeat_customers,
    ROUND(100.0 * SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) / COUNT(*), 2)
        AS repeat_customer_rate_pct
FROM customer_orders;

-- Q7. Products with the highest absolute return value
-- name: product_returns
SELECT
    p.stock_code,
    p.product_description,
    COUNT(DISTINCT r.invoice_no) AS return_invoices,
    SUM(ABS(r.quantity)) AS returned_units,
    ROUND(ABS(SUM(r.signed_return_value)), 2) AS absolute_return_value_gbp
FROM fact_returns r
JOIN dim_product p ON r.product_key = p.product_key
GROUP BY p.product_key, p.stock_code, p.product_description
ORDER BY absolute_return_value_gbp DESC
LIMIT 20;

-- Q8. Revenue concentration by customer decile
-- name: customer_revenue_deciles
WITH customer_value AS (
    SELECT customer_key, SUM(line_revenue) AS revenue
    FROM fact_sales
    WHERE customer_key IS NOT NULL
    GROUP BY customer_key
), ranked AS (
    SELECT
        customer_key,
        revenue,
        NTILE(10) OVER (ORDER BY revenue DESC) AS value_decile
    FROM customer_value
)
SELECT
    value_decile,
    COUNT(*) AS customers,
    ROUND(SUM(revenue), 2) AS revenue_gbp,
    ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 2) AS revenue_share_pct
FROM ranked
GROUP BY value_decile
ORDER BY value_decile;

-- Q9. Sales lines flagged as possible wholesale/high-value outliers
-- name: outlier_profile
SELECT
    SUM(is_quantity_outlier) AS quantity_outlier_lines,
    SUM(is_unit_price_outlier) AS price_outlier_lines,
    SUM(is_line_revenue_outlier) AS revenue_outlier_lines,
    ROUND(SUM(CASE WHEN is_line_revenue_outlier = 1 THEN line_revenue ELSE 0 END), 2)
        AS flagged_revenue_gbp
FROM fact_sales;
