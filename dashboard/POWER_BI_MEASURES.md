# Power BI Measures

Create a dedicated table named `_Measures` with **Home > Enter data**, then place
the following measures in it. These formulas assume the relationships and data
types in `POWER_BI_BUILD_GUIDE.md`.

Monetary measures describe completed-sales revenue or **historical customer
value**. They are not profit, margin, predictive CLV, or forecast value.

## Core Sales Measures

```DAX
Total Revenue =
SUM ( fact_orders[order_revenue_gbp] )
```

```DAX
Total Orders =
DISTINCTCOUNT ( fact_orders[order_id] )
```

```DAX
Units Sold =
SUM ( fact_orders[units_sold] )
```

```DAX
Average Order Value =
DIVIDE ( [Total Revenue], [Total Orders] )
```

## Customer Measures

```DAX
Identified Customers =
CALCULATE (
    DISTINCTCOUNT ( fact_orders[customer_id] ),
    fact_orders[is_identified_customer] = TRUE ()
)
```

```DAX
Anonymous Revenue =
CALCULATE (
    [Total Revenue],
    fact_orders[is_identified_customer] = FALSE ()
)
```

```DAX
Anonymous Revenue Share =
DIVIDE ( [Anonymous Revenue], [Total Revenue] )
```

```DAX
Repeat Customers =
CALCULATE (
    COUNTROWS ( dim_customer ),
    dim_customer[is_repeat_customer] = TRUE ()
)
```

```DAX
Repeat Customer Rate =
DIVIDE ( [Repeat Customers], COUNTROWS ( dim_customer ) )
```

```DAX
At Risk Customers =
CALCULATE (
    COUNTROWS ( dim_customer ),
    dim_customer[rfm_segment] = "At Risk"
)
```

```DAX
Historical Customer Value =
SUM ( dim_customer[monetary_value_gbp] )
```

`Historical Customer Value` covers identified customers only. Anonymous sales
cannot be assigned to customer histories and remain represented in sales measures.

## Time-Intelligence Measures

```DAX
Previous Month Revenue =
CALCULATE (
    [Total Revenue],
    DATEADD ( dim_date[date], -1, MONTH )
)
```

```DAX
Month-over-Month Growth =
DIVIDE (
    [Total Revenue] - [Previous Month Revenue],
    [Previous Month Revenue]
)
```

These measures require `dim_date` to be marked as the model's date table and an
active one-to-many relationship from `dim_date[date]` to
`fact_orders[order_date]`.

## Returns Measures

```DAX
Return Value =
SUM ( fact_returns_month[absolute_return_value_gbp] )
```

```DAX
Return Value to Sales Ratio =
DIVIDE ( [Return Value], [Total Revenue] )
```

`Return Value` is shown as a positive magnitude for presentation. The signed
accounting value remains available in
`fact_returns_month[signed_return_value_gbp]` and reconciles to
GBP -1,462,050.61.

## Formatting

| Measure | Power BI format |
|---|---|
| Total Revenue | Currency, GBP, 2 decimals |
| Total Orders | Whole number, thousands separator |
| Units Sold | Whole number, thousands separator |
| Average Order Value | Currency, GBP, 2 decimals |
| Identified Customers | Whole number, thousands separator |
| Anonymous Revenue | Currency, GBP, 2 decimals |
| Anonymous Revenue Share | Percentage, 2 decimals |
| Repeat Customers | Whole number, thousands separator |
| Repeat Customer Rate | Percentage, 2 decimals |
| At Risk Customers | Whole number, thousands separator |
| Historical Customer Value | Currency, GBP, 2 decimals |
| Previous Month Revenue | Currency, GBP, 2 decimals |
| Month-over-Month Growth | Percentage, 2 decimals |
| Return Value | Currency, GBP, 2 decimals |
| Return Value to Sales Ratio | Percentage, 2 decimals |

## Validation Values

With no filters, the model should return:

| Measure | Expected value |
|---|---:|
| Total Revenue | GBP 20,476,260.45 |
| Total Orders | 40,077 |
| Units Sold | 11,205,148 |
| Average Order Value | GBP 510.92 |
| Identified Customers | 5,878 |
| Anonymous Revenue | GBP 3,101,456.18 |
| Anonymous Revenue Share | 15.15% |
| Repeat Customers | 4,255 |
| Repeat Customer Rate | 72.39% |
| Historical Customer Value | GBP 17,374,804.27 |
| Return Value | GBP 1,462,050.61 |
| Return Value to Sales Ratio | 7.14% |

Small display-level differences must not be “fixed” by changing source values;
confirm relationship direction, filter context, and formatting first.
