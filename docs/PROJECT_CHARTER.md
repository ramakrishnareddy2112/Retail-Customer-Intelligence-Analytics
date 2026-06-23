# Project Charter

## Project Title

Retail Customer Intelligence and Retention Analytics

## Curriculum Alignment

- Primary: Project 6 - Retail Customer Insights Platform
- Enhanced with: Project 13 - Power BI Executive Dashboard practices
- Optional advanced layer: K-Means clustering from Project 14 Option 2

This project is not presented as the complete Project 14 capstone because supervised
churn prediction and predictive CLV require validated targets and assumptions that the
selected dataset does not provide.

## Stakeholders

- Executive leadership: revenue and customer health
- Marketing: segment targeting and reactivation
- Customer retention team: inactivity risk and repeat purchasing
- Merchandising: product demand and return patterns
- Analytics team: reproducible metrics and dashboard data

## Business Questions

1. How are revenue, orders, customers, and average order value changing over time?
2. Which countries and products contribute most to sales and returns?
3. How concentrated is revenue among the customer base?
4. Which customers are Champions, Loyal, New, At Risk, Hibernating, or Lost?
5. Which acquisition cohorts retain customers most effectively?
6. How do repeat customers differ from one-time customers?
7. Which customer groups should receive retention, loyalty, or reactivation action?
8. Do data-driven clusters confirm or challenge the rule-based RFM segments?

## Success Measures

- Raw data can be acquired and processed from a clean checkout.
- Cleaning rules reconcile raw, completed, returned, and excluded transaction counts.
- SQL model supports documented queries using joins, CTEs, and window functions.
- At least 12 decision-focused visualisations are produced.
- Every customer segment has a definition, profile, and recommended action.
- Cohort retention is calculated without future-data leakage.
- Statistical results include effect sizes and business interpretation.
- K-Means selection is justified with stability and silhouette evidence.
- Power BI pages expose consistent KPIs with usable filters and drill-through.
- README, executive report, presentation, and limitations are complete.

## In Scope

- Data profiling and quality validation
- Completed-sale and return classification
- Sales, product, geographic, and temporal analysis
- SQL star schema and analytical queries
- RFM scoring and named business segments
- Cohort retention and repeat-purchase analysis
- Selected statistical tests
- K-Means clustering on customer features
- Power BI-ready exports and dashboard specification
- Business recommendations and presentation

## Out of Scope

- Profit analysis because product cost is unavailable
- Demographic analysis because age, gender, and income are unavailable
- Causal campaign measurement because exposure data is unavailable
- Real-time deployment
- Personally identifiable customer data
- Claims of verified churn or guaranteed future CLV

## Key Risks and Controls

| Risk | Control |
|---|---|
| Missing customer IDs | Keep for aggregate sales; exclude from customer analytics |
| Returns mixed with sales | Model returns separately and reconcile totals |
| Wholesale orders appear as outliers | Flag and sensitivity-test instead of deleting blindly |
| Last month is incomplete | Mark partial-period metrics and avoid unfair comparisons |
| RFM thresholds are subjective | Document quantiles, rules, and sensitivity |
| K-Means is sensitive to scale | Log-transform, standardise, and evaluate multiple seeds |
| Statistical significance from large samples | Report effect size and business magnitude |
