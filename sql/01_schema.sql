PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date TEXT NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name TEXT NOT NULL,
    year_month TEXT NOT NULL,
    day_of_month INTEGER NOT NULL,
    day_of_week TEXT NOT NULL,
    day_of_week_number INTEGER NOT NULL,
    is_weekend INTEGER NOT NULL CHECK (is_weekend IN (0, 1))
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_key INTEGER PRIMARY KEY,
    stock_code TEXT NOT NULL UNIQUE,
    product_description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key INTEGER PRIMARY KEY,
    customer_id TEXT NOT NULL UNIQUE,
    primary_country TEXT NOT NULL,
    first_purchase_date TEXT,
    last_purchase_date TEXT
);

CREATE TABLE IF NOT EXISTS dim_country (
    country_key INTEGER PRIMARY KEY,
    country_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS fact_sales (
    transaction_line_id INTEGER PRIMARY KEY,
    invoice_no TEXT NOT NULL,
    date_key INTEGER NOT NULL,
    product_key INTEGER NOT NULL,
    customer_key INTEGER,
    country_key INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL CHECK (unit_price > 0),
    line_revenue REAL NOT NULL CHECK (line_revenue > 0),
    is_quantity_outlier INTEGER NOT NULL CHECK (is_quantity_outlier IN (0, 1)),
    is_unit_price_outlier INTEGER NOT NULL CHECK (is_unit_price_outlier IN (0, 1)),
    is_line_revenue_outlier INTEGER NOT NULL CHECK (is_line_revenue_outlier IN (0, 1)),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (product_key) REFERENCES dim_product(product_key),
    FOREIGN KEY (customer_key) REFERENCES dim_customer(customer_key),
    FOREIGN KEY (country_key) REFERENCES dim_country(country_key)
);

CREATE TABLE IF NOT EXISTS fact_returns (
    transaction_line_id INTEGER PRIMARY KEY,
    invoice_no TEXT NOT NULL,
    date_key INTEGER NOT NULL,
    product_key INTEGER NOT NULL,
    customer_key INTEGER,
    country_key INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL,
    signed_return_value REAL,
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (product_key) REFERENCES dim_product(product_key),
    FOREIGN KEY (customer_key) REFERENCES dim_customer(customer_key),
    FOREIGN KEY (country_key) REFERENCES dim_country(country_key)
);

CREATE TABLE IF NOT EXISTS audit_exclusions (
    transaction_line_id INTEGER PRIMARY KEY,
    invoice_no TEXT,
    stock_code TEXT,
    invoice_date TEXT,
    quantity INTEGER,
    unit_price REAL,
    exclusion_reason TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sales_invoice ON fact_sales(invoice_no);
CREATE INDEX IF NOT EXISTS idx_sales_date ON fact_sales(date_key);
CREATE INDEX IF NOT EXISTS idx_sales_customer ON fact_sales(customer_key);
CREATE INDEX IF NOT EXISTS idx_sales_product ON fact_sales(product_key);
CREATE INDEX IF NOT EXISTS idx_sales_country ON fact_sales(country_key);
CREATE INDEX IF NOT EXISTS idx_returns_date ON fact_returns(date_key);
CREATE INDEX IF NOT EXISTS idx_returns_product ON fact_returns(product_key);
CREATE INDEX IF NOT EXISTS idx_returns_customer ON fact_returns(customer_key);

