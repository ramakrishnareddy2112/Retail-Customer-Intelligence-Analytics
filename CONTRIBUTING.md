# Contributing

## Reproducing the Pipeline

1. Clone the repository.
2. Create and activate a Python 3.12 virtual environment.
3. Install dependencies with `pip install -r requirements.txt`.
4. Download the raw data with `python scripts/download_data.py`.
5. Run the pipeline stages in the order listed in the README.
6. Run tests with `python -m pytest -q`.

## Extending the Project

- Reusable analytics logic lives in `src/retail_analytics/`.
- Pipeline stages are individual scripts in `scripts/`.
- Dashboard export data lives in `dashboard/data/`.
- Add new tests to `tests/` following the existing pattern.

## Code Style

- Use Python 3.12.
- Keep scripts runnable from the project root.
- Keep generated large raw and processed data out of Git.