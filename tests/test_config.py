from retail_analytics.config import PROJECT_ROOT, RAW_DATA_DIR


def test_project_root_contains_readme() -> None:
    assert (PROJECT_ROOT / "README.md").exists()


def test_raw_data_directory_is_inside_project() -> None:
    assert RAW_DATA_DIR.parent == PROJECT_ROOT / "data"

