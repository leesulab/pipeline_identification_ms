"""Synthèse scientifique des résultats d’identification."""

from pathlib import Path
from typing import Any, Dict, Optional

import duckdb


def _safe_integer(value: Any) -> int:
    """Convertit une valeur agrégée absente en zéro."""
    return int(value) if value is not None else 0


def _safe_float(
    value: Any,
) -> Optional[float]:
    """Convertit une valeur agrégée en nombre flottant."""
    return float(value) if value is not None else None


def summarize_identified_features(
    parquet_path: Path,
) -> Dict[str, Any]:
    """
    Calcule les indicateurs principaux sans charger le Parquet
    complet dans pandas.

    Une même feature peut produire plusieurs lignes lorsqu’elle
    possède plusieurs correspondances dans la base.
    """
    if not parquet_path.is_file():
        raise FileNotFoundError(
            "Table des features complètes introuvable : "
            f"{parquet_path}."
        )

    connection = duckdb.connect()

    try:
        aggregate = connection.execute(
            """
            SELECT
                COUNT(*) AS row_count,
                COUNT(DISTINCT feature_idx)
                    AS unique_feature_count,
                COUNT(*) FILTER (
                    WHERE match_name IS NOT NULL
                      AND TRIM(match_name) <> ''
                ) AS identified_row_count,
                COUNT(DISTINCT feature_idx) FILTER (
                    WHERE match_name IS NOT NULL
                      AND TRIM(match_name) <> ''
                ) AS identified_feature_count,
                COUNT(DISTINCT match_name) FILTER (
                    WHERE match_name IS NOT NULL
                      AND TRIM(match_name) <> ''
                ) AS distinct_molecule_count,
                MEDIAN(global_score) FILTER (
                    WHERE global_score IS NOT NULL
                ) AS median_global_score
            FROM read_parquet(?)
            """,
            [str(parquet_path)],
        ).fetchone()

        confidence_rows = connection.execute(
            """
            SELECT
                CAST(confidence_level AS INTEGER)
                    AS confidence_level,
                COUNT(*) AS row_count,
                COUNT(DISTINCT feature_idx)
                    AS feature_count
            FROM read_parquet(?)
            WHERE confidence_level IS NOT NULL
            GROUP BY confidence_level
            ORDER BY confidence_level
            """,
            [str(parquet_path)],
        ).fetchall()

        sample_statistics_rows = connection.execute(
            """
            WITH expanded_samples AS (
                SELECT
                    feature_idx,
                    match_name,
                    global_score,
                    TRIM(sample_name) AS sample_name
                FROM read_parquet(?),
                UNNEST(
                    STRING_SPLIT(samples, ',')
                ) AS expanded(sample_name)
                WHERE samples IS NOT NULL
                  AND TRIM(samples) <> ''
                  AND TRIM(sample_name) <> ''
            )
            SELECT
                sample_name,
                COUNT(DISTINCT feature_idx)
                    AS unique_feature_count,
                COUNT(DISTINCT feature_idx) FILTER (
                    WHERE match_name IS NOT NULL
                      AND TRIM(match_name) <> ''
                ) AS identified_feature_count,
                COUNT(*) FILTER (
                    WHERE match_name IS NOT NULL
                      AND TRIM(match_name) <> ''
                ) AS identified_row_count,
                MEDIAN(global_score) FILTER (
                    WHERE global_score IS NOT NULL
                ) AS median_global_score
            FROM expanded_samples
            GROUP BY sample_name
            ORDER BY sample_name
            """,
            [str(parquet_path)],
        ).fetchall()

        sample_rows = connection.execute(
            """
            SELECT DISTINCT
                TRIM(sample_name) AS sample_name
            FROM (
                SELECT
                    UNNEST(
                        STRING_SPLIT(samples, ',')
                    ) AS sample_name
                FROM read_parquet(?)
                WHERE samples IS NOT NULL
                  AND TRIM(samples) <> ''
            )
            WHERE TRIM(sample_name) <> ''
            """,
            [str(parquet_path)],
        ).fetchall()
    finally:
        connection.close()

    (
        row_count,
        unique_feature_count,
        identified_row_count,
        identified_feature_count,
        distinct_molecule_count,
        median_global_score,
    ) = aggregate

    row_count = _safe_integer(row_count)
    identified_row_count = _safe_integer(
        identified_row_count
    )
    identified_feature_count = _safe_integer(
        identified_feature_count
    )
    unique_feature_count = _safe_integer(
        unique_feature_count
    )

    identification_rate = (
        identified_row_count / row_count
        if row_count > 0
        else 0.0
    )

    feature_identification_rate = (
        identified_feature_count
        / unique_feature_count
        if unique_feature_count > 0
        else 0.0
    )

    sample_statistics = []

    for (
        sample_name,
        sample_feature_count,
        sample_identified_feature_count,
        sample_identified_row_count,
        sample_median_global_score,
    ) in sample_statistics_rows:
        sample_feature_count = _safe_integer(
            sample_feature_count
        )

        sample_identified_feature_count = (
            _safe_integer(
                sample_identified_feature_count
            )
        )

        sample_feature_identification_rate = (
            sample_identified_feature_count
            / sample_feature_count
            if sample_feature_count > 0
            else 0.0
        )

        sample_statistics.append(
            {
                "sample_name": str(sample_name),
                "unique_feature_count":
                    sample_feature_count,
                "identified_feature_count":
                    sample_identified_feature_count,
                "feature_identification_rate":
                    sample_feature_identification_rate,
                "identified_row_count":
                    _safe_integer(
                        sample_identified_row_count
                    ),
                "median_global_score":
                    _safe_float(
                        sample_median_global_score
                    ),
            }
        )

    confidence_distribution = [
        {
            "confidence_level": int(level),
            "row_count": _safe_integer(level_rows),
            "feature_count": _safe_integer(
                feature_count
            ),
        }
        for (
            level,
            level_rows,
            feature_count,
        ) in confidence_rows
    ]

    return {
        "row_count": row_count,
        "unique_feature_count": unique_feature_count,
        "identified_row_count": identified_row_count,
        "identification_rate": identification_rate,
        "identified_feature_count":
            identified_feature_count,
        "feature_identification_rate":
            feature_identification_rate,
        "distinct_molecule_count": _safe_integer(
            distinct_molecule_count
        ),
        "median_global_score": _safe_float(
            median_global_score
        ),
        "sample_count": len(sample_rows),
        "sample_statistics": sample_statistics,
        "confidence_distribution":
            confidence_distribution,
    }
