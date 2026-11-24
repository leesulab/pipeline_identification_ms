"""Construction du manifeste versionné des résultats d'un job."""

from pathlib import Path
from typing import Any, Dict, Iterable, List


RESULT_CATALOG: Dict[str, Dict[str, Any]] = {
    "molecules_per_sample.png": {
        "id": "molecules-per-sample",
        "title": "Molécules uniques par échantillon",
        "group": "visualizations",
        "kind": "image",
        "order": 10,
    },
    "level1_molecules_per_sample.png": {
        "id": "level1-molecules-per-sample",
        "title": "Molécules de niveau 1 par échantillon",
        "group": "visualizations",
        "kind": "image",
        "order": 20,
    },
    "level1_molecule_distribution_bubble.png": {
        "id": "level1-molecule-distribution",
        "title": "Distribution des molécules de niveau 1",
        "group": "visualizations",
        "kind": "image",
        "order": 30,
    },
    "sample_similarity_heatmap_all.png": {
        "id": "sample-similarity-all",
        "title": "Similarité entre échantillons, tous niveaux",
        "group": "similarities",
        "kind": "image",
        "order": 40,
    },
    "sample_similarity_heatmap_level1.png": {
        "id": "sample-similarity-level1",
        "title": "Similarité entre échantillons, niveau 1",
        "group": "similarities",
        "kind": "image",
        "order": 50,
    },
    "sample_similarity_heatmap_level12.png": {
        "id": "sample-similarity-level12",
        "title": "Similarité entre échantillons, niveaux 1 et 2",
        "group": "similarities",
        "kind": "image",
        "order": 60,
    },
    "sample_similarity_heatmap_level123.png": {
        "id": "sample-similarity-level123",
        "title": "Similarité entre échantillons, niveaux 1 à 3",
        "group": "similarities",
        "kind": "image",
        "order": 70,
    },
    "cluster_statistics.png": {
        "id": "cluster-statistics",
        "title": "Statistiques des clusters",
        "group": "similarities",
        "kind": "image",
        "order": 80,
    },
    "cluster_analysis.txt": {
        "id": "cluster-analysis",
        "title": "Analyse textuelle des clusters",
        "group": "similarities",
        "kind": "text",
        "order": 90,
    },
    "categories_distribution_level1.png": {
        "id": "categories-level1",
        "title": "Catégories, niveau 1",
        "group": "categories",
        "kind": "image",
        "order": 100,
    },
    "categories_distribution_level12.png": {
        "id": "categories-level12",
        "title": "Catégories, niveaux 1 et 2",
        "group": "categories",
        "kind": "image",
        "order": 110,
    },
    "categories_distribution_level123.png": {
        "id": "categories-level123",
        "title": "Catégories, niveaux 1 à 3",
        "group": "categories",
        "kind": "image",
        "order": 120,
    },
    "categories_pie_charts.png": {
        "id": "categories-pie-charts",
        "title": "Répartition globale des catégories",
        "group": "categories",
        "kind": "image",
        "order": 130,
    },
    "tic_ms1_comparison.html": {
        "id": "tic-ms1-interactive",
        "title": "Comparaison interactive des TIC MS1",
        "group": "visualizations",
        "kind": "html",
        "order": 140,
    },
    "tic_ms1_comparison.png": {
        "id": "tic-ms1-image",
        "title": "Comparaison des TIC MS1",
        "group": "visualizations",
        "kind": "image",
        "order": 150,
    },
    "feature_matrix/feature_matrix.parquet": {
        "id": "feature-matrix",
        "title": "Matrice des features",
        "group": "tables",
        "kind": "table",
        "order": 200,
    },
    "feature_matrix/features_complete.parquet": {
        "id": "identified-features",
        "title": "Features complètes et identifiées",
        "group": "tables",
        "kind": "table",
        "order": 210,
    },
    "feature_matrix/feature_matrix.csv": {
        "id": "feature-matrix-csv",
        "title": "Matrice des features, CSV",
        "group": "tables",
        "kind": "table",
        "order": 220,
    },
    "feature_matrix/features_complete.csv": {
        "id": "identified-features-csv",
        "title": "Features complètes, CSV",
        "group": "tables",
        "kind": "table",
        "order": 230,
    },
}


def _fallback_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".svg"}:
        return "image"
    if suffix == ".html":
        return "html"
    if suffix in {".csv", ".parquet"}:
        return "table"
    if suffix in {".txt", ".log"}:
        return "text"
    return "file"


def _result_entry(output_dir: Path, path: Path) -> Dict[str, Any]:
    relative_path = path.relative_to(output_dir).as_posix()
    metadata = RESULT_CATALOG.get(relative_path, {})
    return {
        "id": metadata.get("id", relative_path.replace("/", "-").replace(".", "-")),
        "title": metadata.get("title", path.stem.replace("_", " ").capitalize()),
        "group": metadata.get("group", "other"),
        "kind": metadata.get("kind", _fallback_kind(path)),
        "format": path.suffix.lower().lstrip("."),
        "relative_path": f"data/output/{relative_path}",
        "size_bytes": path.stat().st_size,
        "order": metadata.get("order", 1000),
    }


def build_result_manifest(job_id: str, job_dir: Path) -> Dict[str, Any]:
    """Décrit tous les résultats réellement présents dans le job."""
    output_dir = job_dir / "data" / "output"
    files: Iterable[Path] = ()
    if output_dir.is_dir():
        files = sorted(path for path in output_dir.rglob("*") if path.is_file())
    results: List[Dict[str, Any]] = [
        _result_entry(output_dir, path) for path in files
    ]
    results.sort(key=lambda item: (item["order"], item["title"]))
    return {
        "version": 1,
        "job_id": job_id,
        "results": results,
    }
