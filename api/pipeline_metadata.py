"""Métadonnées d’affichage des paramètres de la pipeline."""

from typing import Any, Dict


PARAMETER_METADATA: Dict[str, Dict[str, Any]] = {
    "threshold": {
        "label": "Seuil d’intensité",
        "minimum": 0,
        "step": 1,
        "unit": "intensité",
    },
    "smooth_iterations": {
        "label": "Itérations de lissage",
        "minimum": 0,
        "step": 1,
    },
    "mz_ppm": {
        "label": "Tolérance m/z",
        "minimum": 0.01,
        "maximum": 100.0,
        "step": 0.1,
        "unit": "ppm",
    },
    "dt_tolerance": {
        "label": "Tolérance du temps de dérive",
        "minimum": 0.0,
        "step": 0.01,
        "unit": "ms",
    },
    "rt_tolerance": {
        "label": "Tolérance du temps de rétention",
        "minimum": 0.0,
        "step": 0.001,
        "unit": "min",
    },
    "dbscan_eps": {
        "label": "Rayon DBSCAN",
        "minimum": 0.001,
        "step": 0.01,
    },
    "dbscan_min_samples": {
        "label": "Minimum de points DBSCAN",
        "minimum": 1,
        "step": 1,
    },
    "algorithm": {
        "label": "Algorithme de voisinage",
        "choices": [
            "kd_tree",
            "ball_tree",
            "brute",
            "auto",
        ],
    },
    "cluster_ratio": {
        "label": "Ratio minimal de cluster",
        "minimum": 0.0,
        "maximum": 1.0,
        "step": 0.01,
    },
    "min_replicates": {
        "label": "Nombre minimal de réplicats",
        "minimum": 1,
        "step": 1,
    },
    "database_file": {
        "label": "Fichier de base d’identification",
    },
    "database_key": {
        "label": "Mode d’ionisation",
        "choices": ["positive", "negative"],
    },
    "ms2_score_threshold": {
        "label": "Seuil du score MS2",
        "minimum": 0.0,
        "maximum": 1.0,
        "step": 0.01,
    },
    "mz_round_decimals": {
        "label": "Décimales m/z",
        "minimum": 0,
        "maximum": 10,
        "step": 1,
    },
    "max_peaks": {
        "label": "Nombre maximal de pics MS2",
        "minimum": 1,
        "step": 1,
    },
    "intensity_scale": {
        "label": "Échelle d’intensité MS2",
        "minimum": 1,
        "step": 1,
    },
    "parallel_max_workers": {
        "label": "Nombre maximal de processus",
        "minimum": 1,
        "step": 1,
    },
    "batch_size": {
        "label": "Taille des lots",
        "minimum": 1,
        "step": 1,
    },
    "intensity_threshold": {
        "label": "Seuil général d’intensité",
        "minimum": 0.0,
        "step": 1.0,
        "unit": "intensité",
    },
}


PATH_METADATA: Dict[str, Dict[str, Any]] = {
    "smooth_radius.mz": {
        "label": "Rayon de lissage m/z",
        "minimum": 0,
        "step": 1,
    },
    "smooth_radius.drift_time": {
        "label": "Rayon de lissage du temps de dérive",
        "minimum": 0,
        "step": 1,
    },
    "smooth_radius.retention_time": {
        "label": "Rayon de lissage du temps de rétention",
        "minimum": 0,
        "step": 1,
    },
    "peak_radius.mz": {
        "label": "Rayon de pic m/z",
        "minimum": 0,
        "step": 1,
    },
    "peak_radius.drift_time": {
        "label": "Rayon de pic du temps de dérive",
        "minimum": 0,
        "step": 1,
    },
    "peak_radius.retention_time": {
        "label": "Rayon de pic du temps de rétention",
        "minimum": 0,
        "step": 1,
    },
    "tolerances.mz_ppm": {
        "label": "Tolérance d’identification m/z",
        "minimum": 0.01,
        "maximum": 100.0,
        "step": 0.1,
        "unit": "ppm",
    },
    "tolerances.ccs_percent": {
        "label": "Tolérance CCS",
        "minimum": 0.0,
        "maximum": 100.0,
        "step": 0.1,
        "unit": "%",
    },
    "tolerances.rt_min": {
        "label": "Tolérance d’identification du temps de rétention",
        "minimum": 0.0,
        "step": 0.001,
        "unit": "min",
    },
    "weights.mz": {
        "label": "Poids m/z",
        "minimum": 0.0,
        "maximum": 1.0,
        "step": 0.01,
        "group": "Poids d’identification",
    },
    "weights.ccs": {
        "label": "Poids CCS",
        "minimum": 0.0,
        "maximum": 1.0,
        "step": 0.01,
        "group": "Poids d’identification",
    },
    "weights.rt": {
        "label": "Poids du temps de rétention",
        "minimum": 0.0,
        "maximum": 1.0,
        "step": 0.01,
        "group": "Poids d’identification",
    },
}


def get_parameter_metadata(
    path: str,
) -> Dict[str, Any]:
    """Fusionne les métadonnées générales et spécifiques."""
    leaf_name = path.split(".")[-1]

    metadata = dict(
        PARAMETER_METADATA.get(
            leaf_name,
            {},
        )
    )

    metadata.update(
        PATH_METADATA.get(
            path,
            {},
        )
    )

    return metadata
