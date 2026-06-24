from pathlib import Path

import nbformat


NOTEBOOK_PATHS = [
    Path("notebooks/01_data_validation_and_cleaning.ipynb"),
    Path("notebooks/02_sql_and_exploratory_analysis.ipynb"),
    Path("notebooks/03_rfm_and_cohort_analysis.ipynb"),
    Path("notebooks/04_statistical_analysis.ipynb"),
    Path("notebooks/05_kmeans_customer_clustering.ipynb"),
]
REQUIRED_SECTIONS = [
    "## Objective",
    "## Business Questions",
    "## Inputs",
    "## Methodology",
    "## Code",
    "## Results",
    "## Business Insights",
    "## Assumptions",
    "## Limitations",
    "## Next Steps",
]


def test_all_notebooks_exist_with_required_markdown_sections() -> None:
    for path in NOTEBOOK_PATHS:
        assert path.exists(), f"Missing notebook: {path}"
        notebook = nbformat.read(path, as_version=4)
        markdown = "\n".join(
            cell.source for cell in notebook.cells if cell.cell_type == "markdown"
        )
        for section in REQUIRED_SECTIONS:
            assert section in markdown, f"{path} is missing {section}"


def test_notebooks_are_executed_without_errors_on_python_312() -> None:
    for path in NOTEBOOK_PATHS:
        notebook = nbformat.read(path, as_version=4)
        code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
        assert code_cells, f"{path} has no code cells"
        assert all(cell.execution_count is not None for cell in code_cells), (
            f"{path} contains an unexecuted code cell"
        )
        error_outputs = [
            output
            for cell in code_cells
            for output in cell.get("outputs", [])
            if output.get("output_type") == "error"
        ]
        assert not error_outputs, f"{path} contains execution errors"

        kernelspec = notebook.metadata.get("kernelspec", {})
        language_info = notebook.metadata.get("language_info", {})
        assert kernelspec.get("name") == "python3"
        assert kernelspec.get("language", "python").lower() == "python"
        assert str(language_info.get("version", "")).startswith("3.12")
