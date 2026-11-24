"""Tests du manifeste versionné des résultats."""

from pathlib import Path

from api.result_manifest import (
    build_result_manifest,
)


def create_result(
    job_dir: Path,
    relative_path: str,
    content: bytes = b"result",
) -> None:
    path = (
        job_dir
        / "data"
        / "output"
        / relative_path
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(content)


def test_empty_output_returns_empty_manifest(
    tmp_path: Path,
) -> None:
    manifest = build_result_manifest(
        "job-empty",
        tmp_path,
    )

    assert manifest == {
        "version": 1,
        "job_id": "job-empty",
        "results": [],
    }


def test_known_results_receive_scientific_metadata(
    tmp_path: Path,
) -> None:
    create_result(
        tmp_path,
        "molecules_per_sample.png",
    )

    create_result(
        tmp_path,
        "sample_similarity_heatmap_level1.png",
    )

    create_result(
        tmp_path,
        "feature_matrix/features_complete.parquet",
    )

    manifest = build_result_manifest(
        "job-known",
        tmp_path,
    )

    results = manifest["results"]

    assert [result["id"] for result in results] == [
        "molecules-per-sample",
        "sample-similarity-level1",
        "identified-features",
    ]

    assert results[0]["title"] == (
        "Molécules uniques par échantillon"
    )
    assert results[0]["group"] == "visualizations"
    assert results[0]["kind"] == "image"
    assert results[0]["format"] == "png"
    assert results[0]["relative_path"] == (
        "data/output/molecules_per_sample.png"
    )

    assert results[2]["group"] == "tables"
    assert results[2]["kind"] == "table"
    assert results[2]["format"] == "parquet"


def test_unknown_results_use_format_fallback(
    tmp_path: Path,
) -> None:
    create_result(
        tmp_path,
        "custom/new_heatmap.svg",
    )

    create_result(
        tmp_path,
        "custom/summary.csv",
    )

    manifest = build_result_manifest(
        "job-fallback",
        tmp_path,
    )

    results = {
        result["relative_path"]: result
        for result in manifest["results"]
    }

    image = results[
        "data/output/custom/new_heatmap.svg"
    ]
    table = results[
        "data/output/custom/summary.csv"
    ]

    assert image["kind"] == "image"
    assert image["group"] == "other"
    assert image["format"] == "svg"

    assert table["kind"] == "table"
    assert table["format"] == "csv"


def test_results_include_size_and_stable_order(
    tmp_path: Path,
) -> None:
    create_result(
        tmp_path,
        "categories_pie_charts.png",
        b"12345",
    )

    create_result(
        tmp_path,
        "cluster_statistics.png",
        b"123456789",
    )

    manifest = build_result_manifest(
        "job-order",
        tmp_path,
    )

    results = manifest["results"]

    assert results[0]["id"] == "cluster-statistics"
    assert results[0]["size_bytes"] == 9

    assert results[1]["id"] == "categories-pie-charts"
    assert results[1]["size_bytes"] == 5
