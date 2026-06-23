"""Validate the raw Online Retail II workbook and write a profile report."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from retail_analytics.config import RAW_WORKBOOK_PATH  # noqa: E402
from retail_analytics.ingestion import load_workbook  # noqa: E402
from retail_analytics.validation import (  # noqa: E402
    profile_transactions,
    validate_minimum_contract,
)


REPORT_PATH = PROJECT_ROOT / "reports" / "raw_data_profile.json"


def main() -> None:
    transactions = load_workbook(RAW_WORKBOOK_PATH)
    failures = validate_minimum_contract(transactions)
    profile = profile_transactions(transactions)
    profile["validation"] = {
        "status": "failed" if failures else "passed",
        "failures": failures,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    print(json.dumps(profile, indent=2))
    print(f"\nSaved profile: {REPORT_PATH}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

