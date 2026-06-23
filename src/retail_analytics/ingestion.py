"""Schema-aware ingestion for the UCI Online Retail II workbook."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd


CANONICAL_COLUMNS = (
    "invoice_no",
    "stock_code",
    "description",
    "quantity",
    "invoice_date",
    "unit_price",
    "customer_id",
    "country",
)

COLUMN_ALIASES = {
    "invoice": "invoice_no",
    "invoiceno": "invoice_no",
    "invoice_no": "invoice_no",
    "stockcode": "stock_code",
    "stock_code": "stock_code",
    "description": "description",
    "quantity": "quantity",
    "invoicedate": "invoice_date",
    "invoice_date": "invoice_date",
    "price": "unit_price",
    "unitprice": "unit_price",
    "unit_price": "unit_price",
    "customerid": "customer_id",
    "customer_id": "customer_id",
    "country": "country",
}


def normalise_label(label: object) -> str:
    """Normalise a column label for alias matching."""
    return "".join(character for character in str(label).lower() if character.isalnum() or character == "_")


def canonicalise_columns(columns: Iterable[object]) -> dict[object, str]:
    """Build a raw-to-canonical rename map and reject unknown schemas."""
    rename_map: dict[object, str] = {}
    for column in columns:
        normalised = normalise_label(column)
        if normalised in COLUMN_ALIASES:
            rename_map[column] = COLUMN_ALIASES[normalised]

    canonical_found = set(rename_map.values())
    missing = set(CANONICAL_COLUMNS) - canonical_found
    if missing:
        raise ValueError(
            "Workbook schema is missing required canonical columns: "
            f"{sorted(missing)}. Raw columns: {list(columns)}"
        )
    return rename_map


def standardise_frame(frame: pd.DataFrame, source_sheet: str) -> pd.DataFrame:
    """Return a canonical transaction frame without applying business exclusions."""
    canonical = frame.rename(columns=canonicalise_columns(frame.columns)).copy()
    canonical = canonical.loc[:, list(CANONICAL_COLUMNS)]

    canonical["invoice_no"] = canonical["invoice_no"].astype("string").str.strip()
    canonical["stock_code"] = canonical["stock_code"].astype("string").str.strip()
    canonical["description"] = (
        canonical["description"].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    )
    canonical["quantity"] = pd.to_numeric(canonical["quantity"], errors="coerce")
    canonical["invoice_date"] = pd.to_datetime(canonical["invoice_date"], errors="coerce")
    canonical["unit_price"] = pd.to_numeric(canonical["unit_price"], errors="coerce")
    canonical["customer_id"] = (
        canonical["customer_id"]
        .astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
    )
    canonical["country"] = canonical["country"].astype("string").str.strip()
    canonical["source_sheet"] = source_sheet

    canonical["line_revenue"] = canonical["quantity"] * canonical["unit_price"]
    canonical["is_cancelled"] = canonical["invoice_no"].str.upper().str.startswith("C", na=False)
    canonical["is_return"] = canonical["is_cancelled"] | canonical["quantity"].lt(0)
    canonical["is_completed_sale"] = (
        ~canonical["is_cancelled"]
        & canonical["quantity"].gt(0)
        & canonical["unit_price"].gt(0)
    )
    canonical["has_customer_id"] = canonical["customer_id"].notna()
    return canonical


def workbook_sheet_names(path: Path) -> list[str]:
    """List workbook sheets without loading all transaction rows."""
    with pd.ExcelFile(path, engine="openpyxl") as workbook:
        return workbook.sheet_names


def load_workbook(path: Path) -> pd.DataFrame:
    """Load and combine every worksheet that matches the transaction schema."""
    if not path.exists():
        raise FileNotFoundError(
            f"Raw workbook not found at {path}. Run scripts/download_data.py first."
        )

    frames: list[pd.DataFrame] = []
    with pd.ExcelFile(path, engine="openpyxl") as workbook:
        for sheet_name in workbook.sheet_names:
            raw = pd.read_excel(workbook, sheet_name=sheet_name)
            try:
                frames.append(standardise_frame(raw, source_sheet=sheet_name))
            except ValueError as error:
                raise ValueError(f"Invalid schema in sheet '{sheet_name}': {error}") from error

    if not frames:
        raise ValueError("No transaction worksheets were found in the workbook.")
    return pd.concat(frames, ignore_index=True)

