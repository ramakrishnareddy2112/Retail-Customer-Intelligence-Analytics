import tempfile
from pathlib import Path

from retail_analytics.sql_runner import parse_named_queries


def test_parse_named_queries() -> None:
    with tempfile.TemporaryDirectory() as directory:
        sql_path = Path(directory) / "queries.sql"
        sql_path.write_text(
            "-- name: first_query\nSELECT 1 AS value;\n\n"
            "-- name: second_query\nSELECT 2 AS value;\n",
            encoding="utf-8",
        )

        queries = parse_named_queries(sql_path)

    assert [name for name, _ in queries] == ["first_query", "second_query"]
    assert "SELECT 1" in queries[0][1]
