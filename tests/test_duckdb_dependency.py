"""Contrôle de la dépendance DuckDB requise par les tables."""

import duckdb


def test_duckdb_version() -> None:
    assert duckdb.__version__ == "1.4.5"


def test_duckdb_can_query_parquet(tmp_path) -> None:
    parquet_file = tmp_path / "test.parquet"

    connection = duckdb.connect()

    try:
        connection.execute(
            """
            COPY (
                SELECT
                    range AS feature_id,
                    CAST(
                        range * 0.1
                        AS DOUBLE
                    ) AS score
                FROM range(100)
            )
            TO ?
            (
                FORMAT PARQUET
            )
            """,
            [str(parquet_file)],
        )

        rows = connection.execute(
            """
            SELECT feature_id, score
            FROM read_parquet(?)
            ORDER BY score DESC NULLS LAST
            LIMIT 3
            """,
            [str(parquet_file)],
        ).fetchall()
    finally:
        connection.close()

    assert rows == [
        (99, 9.9),
        (98, 9.8),
        (97, 9.7),
    ]
