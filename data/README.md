# Data Directory

- `raw/`: untouched official source files; never manually edit.
- `interim/`: canonical but not fully analysis-ready data.
- `processed/`: validated analytical tables and Power BI exports.

Large data files are excluded from Git. Run `python scripts/download_data.py` to
retrieve the source workbook from UCI.

