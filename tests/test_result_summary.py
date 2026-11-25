"""Tests de la synthèse scientifique des résultats."""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from api.result_summary import (
    summarize_identified_features,
)


def create_identification_table(
    path: Path,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pq.write_table(
        pa.table(
            {
                "feature_idx": [
                    1,
                    1,
                    2,
                    3,
                    4,
                    5,
                ],
                "match_name": [
                    "Molecule A",
                    "Molecule B",
                    "Molecule C",
                    None,
                    "",
                    "Molecule A",
                ],
                "global_score": [
                    0.9,
                    0.8,
                    0.7,
                    None,
                    None,
                    0.6,
                ],
                "confidence_level": [
                    1.0,
                    2.0,
                    3.0,
                    None,
                    5.0,
                    2.0,
                ],
                "samples": [
                    "sample_a,sample_b",
                    "sample_a,sample_b",
                    "sample_b",
                    "sample_c",
                    "sample_c",
                    "sample_a",
                ],
            }
        ),
        path,
    )


def test_identification_summary(
    tmp_path: Path,
) -> None:
    path = tmp_path / "features_complete.parquet"

    create_identification_table(path)

    summary = summarize_identified_features(path)

    assert summary["row_count"] == 6
    assert summary["unique_feature_count"] == 5
    assert summary["identified_row_count"] == 4

    assert summary["identification_rate"] == pytest.approx(
        4 / 6
    )

    assert summary["identified_feature_count"] == 3

    assert summary[
        "feature_identification_rate"
    ] == pytest.approx(3 / 5)

    assert summary["distinct_molecule_count"] == 3
    assert summary["median_global_score"] == 0.75
    assert summary["sample_count"] == 3

    statistics = {
        item["sample_name"]: item
        for item in summary["sample_statistics"]
    }

    assert set(statistics) == {
        "sample_a",
        "sample_b",
        "sample_c",
    }

    assert statistics["sample_a"][
        "unique_feature_count"
    ] == 2

    assert statistics["sample_a"][
        "identified_feature_count"
    ] == 2

    assert statistics["sample_a"][
        "feature_identification_rate"
    ] == 1.0

    assert statistics["sample_c"][
        "unique_feature_count"
    ] == 2

    assert statistics["sample_c"][
        "identified_feature_count"
    ] == 0

    assert statistics["sample_c"][
        "feature_identification_rate"
    ] == 0.0

    assert summary["confidence_distribution"] == [
        {
            "confidence_level": 1,
            "row_count": 1,
            "feature_count": 1,
        },
        {
            "confidence_level": 2,
            "row_count": 2,
            "feature_count": 2,
        },
        {
            "confidence_level": 3,
            "row_count": 1,
            "feature_count": 1,
        },
        {
            "confidence_level": 5,
            "row_count": 1,
            "feature_count": 1,
        },
    ]


def test_identification_summary_rejects_missing_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        FileNotFoundError,
        match="features complètes introuvable",
    ):
        summarize_identified_features(
            tmp_path / "missing.parquet"
        )
