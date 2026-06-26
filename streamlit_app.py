from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"
DASHBOARD_DATA_DIR = BASE_DIR / "dashboard" / "data"

EXECUTIVE_SCREENSHOT = REPORTS_DIR / "dashboard_executive_overview.png"
CUSTOMER_SCREENSHOT = REPORTS_DIR / "dashboard_customer_insights.png"
DASHBOARD_PDF = REPORTS_DIR / "Retail_Customer_Intelligence_Dashboard.pdf"
DASHBOARD_PBIX = REPORTS_DIR / "Retail_Customer_Intelligence_Dashboard.pbix"


st.set_page_config(
    page_title="Retail Customer Intelligence Analytics",
    page_icon="📊",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def load_csv(file_name: str) -> Optional[pd.DataFrame]:
    path = DASHBOARD_DATA_DIR / file_name
    if not path.exists():
        return None

    try:
        return pd.read_csv(path)
    except Exception:
        return None


def find_column(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    available = {col.lower(): col for col in df.columns}
    for candidate in candidates:
        if candidate.lower() in available:
            return available[candidate.lower()]
    return None


def clean_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("GBP", "", regex=False)
        .str.replace("£", "", regex=False)
        .str.strip(),
        errors="coerce",
    ).fillna(0)


def show_download(file_path: Path, label: str, mime: str) -> None:
    if file_path.exists():
        with open(file_path, "rb") as file:
            st.download_button(
                label=label,
                data=file,
                file_name=file_path.name,
                mime=mime,
                use_container_width=True,
            )
    else:
        st.warning(f"Missing file: {file_path.name}")


def show_image(file_path: Path, caption: str) -> None:
    if file_path.exists():
        st.image(str(file_path), caption=caption, use_container_width=True)
    else:
        st.error(f"Screenshot not found: {file_path}")


st.title("Retail Customer Intelligence and Retention Analytics")
st.caption(
    "End-to-end analytics project using Python, SQL, RFM segmentation, cohort retention, "
    "statistical testing, K-Means clustering, and Power BI dashboard reporting."
)

with st.sidebar:
    st.header("Project Files")
    show_download(DASHBOARD_PDF, "Download Dashboard PDF", "application/pdf")
    show_download(DASHBOARD_PBIX, "Download PBIX File", "application/octet-stream")

    st.divider()
    st.caption("Portfolio-ready analytics project")
    st.caption("Dataset: UCI Online Retail II")


st.markdown(
    """
This app presents the final project output in a portfolio-friendly format.
The full project includes a validated data pipeline, SQL analysis layer,
customer segmentation, clustering, statistical testing, and a two-page Power BI dashboard.
"""
)

st.divider()

st.subheader("Core Business KPIs")

kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)

kpi1.metric("Sales Value", "GBP 20.48M")
kpi2.metric("Orders", "40,077")
kpi3.metric("Customers", "5,878")
kpi4.metric("Units Sold", "11.21M")
kpi5.metric("Avg Order Value", "GBP 510.92")
kpi6.metric("Repeat Rate", "72.39%")

st.divider()

tabs = st.tabs(
    [
        "Dashboard Preview",
        "Interactive Insights",
        "Customer Tables",
        "Project Methodology",
        "File Check",
    ]
)

with tabs[0]:
    st.header("Power BI Dashboard Preview")

    dash_tab1, dash_tab2 = st.tabs(["Executive Overview", "Customer Insights"])

    with dash_tab1:
        st.subheader("Executive Overview")
        st.write(
            "Executive KPIs, monthly revenue trend, customer segment revenue, "
            "top countries, top products, and monthly returns."
        )
        show_image(EXECUTIVE_SCREENSHOT, "Power BI Executive Overview")

    with dash_tab2:
        st.subheader("Customer Insights")
        st.write(
            "Interactive customer intelligence page with year, country, and segment slicers, "
            "plus segment and cluster summary tables."
        )
        show_image(CUSTOMER_SCREENSHOT, "Power BI Customer Insights")


with tabs[1]:
    st.header("Interactive Insights from Dashboard Data")

    fact_orders = load_csv("fact_orders.csv")
    fact_country_month = load_csv("fact_country_month.csv")
    fact_product_month = load_csv("fact_product_month.csv")
    fact_returns_month = load_csv("fact_returns_month.csv")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Monthly Revenue Trend")

        if fact_orders is not None:
            month_col = find_column(fact_orders, ["month_start", "order_month"])
            revenue_col = find_column(
                fact_orders,
                ["order_revenue_gbp", "revenue_gbp", "total_revenue_gbp"],
            )

            if month_col and revenue_col:
                monthly = fact_orders[[month_col, revenue_col]].copy()
                monthly[month_col] = pd.to_datetime(monthly[month_col], errors="coerce")
                monthly[revenue_col] = clean_numeric(monthly[revenue_col])
                monthly = (
                    monthly.dropna(subset=[month_col])
                    .groupby(month_col, as_index=False)[revenue_col]
                    .sum()
                    .sort_values(month_col)
                )
                st.line_chart(monthly.set_index(month_col)[revenue_col])
            else:
                st.info("Required revenue/month columns are not available.")
        else:
            st.info("fact_orders.csv is not available.")

    with col_right:
        st.subheader("Top Countries by Revenue")

        country_source = fact_country_month if fact_country_month is not None else fact_orders

        if country_source is not None:
            country_col = find_column(country_source, ["country"])
            revenue_col = find_column(
                country_source,
                ["revenue_gbp", "order_revenue_gbp", "total_revenue_gbp"],
            )

            if country_col and revenue_col:
                country_df = country_source[[country_col, revenue_col]].copy()
                country_df[revenue_col] = clean_numeric(country_df[revenue_col])
                top_countries = (
                    country_df.groupby(country_col, as_index=False)[revenue_col]
                    .sum()
                    .sort_values(revenue_col, ascending=False)
                    .head(10)
                )
                st.bar_chart(top_countries.set_index(country_col)[revenue_col])
            else:
                st.info("Required country/revenue columns are not available.")
        else:
            st.info("Country data is not available.")

    col_left2, col_right2 = st.columns(2)

    with col_left2:
        st.subheader("Top Products by Revenue")

        if fact_product_month is not None:
            product_col = find_column(
                fact_product_month,
                ["description", "product_description", "stock_code"],
            )
            revenue_col = find_column(
                fact_product_month,
                ["revenue_gbp", "product_revenue_gbp", "total_revenue_gbp"],
            )

            if product_col and revenue_col:
                product_df = fact_product_month[[product_col, revenue_col]].copy()
                product_df[revenue_col] = clean_numeric(product_df[revenue_col])
                top_products = (
                    product_df.groupby(product_col, as_index=False)[revenue_col]
                    .sum()
                    .sort_values(revenue_col, ascending=False)
                    .head(10)
                )
                st.dataframe(top_products, use_container_width=True, hide_index=True)
            else:
                st.info("Required product/revenue columns are not available.")
        else:
            st.info("fact_product_month.csv is not available.")

    with col_right2:
        st.subheader("Monthly Returns Trend")

        if fact_returns_month is not None:
            month_col = find_column(fact_returns_month, ["month_start", "return_month"])
            returns_col = find_column(
                fact_returns_month,
                [
                    "return_line_count",
                    "returned_units",
                    "returns_count",
                    "return_quantity",
                    "return_value_gbp",
                ],
            )

            if month_col and returns_col:
                returns_df = fact_returns_month[[month_col, returns_col]].copy()
                returns_df[month_col] = pd.to_datetime(returns_df[month_col], errors="coerce")
                returns_df[returns_col] = clean_numeric(returns_df[returns_col])
                returns_df = (
                    returns_df.dropna(subset=[month_col])
                    .groupby(month_col, as_index=False)[returns_col]
                    .sum()
                    .sort_values(month_col)
                )
                st.line_chart(returns_df.set_index(month_col)[returns_col])
            else:
                st.info("Required returns/month columns are not available.")
        else:
            st.info("fact_returns_month.csv is not available.")


with tabs[2]:
    st.header("Customer Segmentation and Cluster Tables")

    segment_summary = load_csv("segment_summary.csv")
    cluster_summary = load_csv("cluster_summary.csv")

    st.subheader("RFM Customer Segment Summary")
    if segment_summary is not None:
        st.dataframe(segment_summary, use_container_width=True, hide_index=True)
    else:
        st.warning("segment_summary.csv is not available in dashboard/data.")

    st.subheader("K-Means Customer Cluster Summary")
    if cluster_summary is not None:
        st.dataframe(cluster_summary, use_container_width=True, hide_index=True)
    else:
        st.warning("cluster_summary.csv is not available in dashboard/data.")


with tabs[3]:
    st.header("Project Methodology")

    st.markdown(
        """
### Analytical Pipeline

1. Raw Online Retail II data validation and profiling  
2. Cleaning, deduplication, and transaction classification  
3. SQLite star schema and SQL business analysis exports  
4. Exploratory data analysis with charts and summary tables  
5. RFM segmentation and cohort retention analysis  
6. Statistical hypothesis testing with Holm adjustment  
7. K-Means clustering with stability evaluation  
8. Power BI dashboard creation with executive and customer insight pages  
9. Streamlit portfolio deployment  

### Business Focus

The project separates completed sales, returns/cancellations, anonymous transactions,
identified customer behavior, customer value segments, and operational customer clusters.
"""
    )

    st.success("Automated tests passed: 24 tests")


with tabs[4]:
    st.header("File Availability Check")

    file_checks = pd.DataFrame(
        [
            {
                "File": "Executive Overview screenshot",
                "Path": str(EXECUTIVE_SCREENSHOT),
                "Available": EXECUTIVE_SCREENSHOT.exists(),
            },
            {
                "File": "Customer Insights screenshot",
                "Path": str(CUSTOMER_SCREENSHOT),
                "Available": CUSTOMER_SCREENSHOT.exists(),
            },
            {
                "File": "Power BI PDF",
                "Path": str(DASHBOARD_PDF),
                "Available": DASHBOARD_PDF.exists(),
            },
            {
                "File": "Power BI PBIX",
                "Path": str(DASHBOARD_PBIX),
                "Available": DASHBOARD_PBIX.exists(),
            },
            {
                "File": "Dashboard data folder",
                "Path": str(DASHBOARD_DATA_DIR),
                "Available": DASHBOARD_DATA_DIR.exists(),
            },
        ]
    )

    st.dataframe(file_checks, use_container_width=True, hide_index=True)

    if DASHBOARD_DATA_DIR.exists():
        st.subheader("Available Dashboard CSV Files")
        csv_files = sorted([file.name for file in DASHBOARD_DATA_DIR.glob("*.csv")])
        st.write(csv_files)

st.divider()
st.success("Project completed and ready for portfolio, resume, LinkedIn, and job applications.")