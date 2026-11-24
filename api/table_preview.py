"""Prévisualisation paginée des résultats CSV et Parquet."""

import csv
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pyarrow as pa
import pyarrow.parquet as pq

from api.result_manifest import build_result_manifest

DEFAULT_LIMIT = 50
MAX_LIMIT = 100
MAX_CELL_CHARACTERS = 500


def _serialize_cell(value: Any) -> Any:
    """Convertit une cellule en valeur JSON sûre et bornée."""
    if value is None:
        return None
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, bytes):
        text = value.hex()
    else:
        text = str(value)
    if len(text) > MAX_CELL_CHARACTERS:
        return text[:MAX_CELL_CHARACTERS] + "…"
    return text


def _validate_pagination(offset: int, limit: int) -> None:
    if offset < 0:
        raise ValueError("L’offset doit être supérieur ou égal à 0.")
    if limit < 1 or limit > MAX_LIMIT:
        raise ValueError(
            f"La limite doit être comprise entre 1 et {MAX_LIMIT}."
        )


def _select_columns(
    available: Iterable[str],
    requested: Optional[List[str]],
) -> List[str]:
    available_columns = list(available)
    if not requested:
        return available_columns
    unknown = [
        column for column in requested
        if column not in available_columns
    ]
    if unknown:
        raise ValueError(
            "Colonnes inconnues : " + ", ".join(unknown) + "."
        )
    return requested


def resolve_table_result(
    job_id: str,
    job_dir: Path,
    result_id: str,
) -> Path:
    """Résout une table déclarée dans le manifeste."""
    manifest = build_result_manifest(job_id, job_dir)
    result = next(
        (item for item in manifest["results"] if item["id"] == result_id),
        None,
    )
    if result is None:
        raise FileNotFoundError(f"Résultat inconnu : {result_id}.")
    if result["kind"] != "table":
        raise ValueError(f"Le résultat {result_id} n’est pas une table.")

    table_path = (job_dir / result["relative_path"]).resolve()
    output_dir = (job_dir / "data" / "output").resolve()
    try:
        table_path.relative_to(output_dir)
    except ValueError as error:
        raise ValueError("La table sort du dossier de résultats.") from error
    if not table_path.is_file():
        raise FileNotFoundError(f"Table introuvable : {result_id}.")
    return table_path


def preview_parquet(
    path: Path,
    offset: int,
    limit: int,
    columns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Lit uniquement les groupes de lignes couvrant la page."""
    _validate_pagination(offset, limit)
    parquet = pq.ParquetFile(path)
    metadata = parquet.metadata
    total = metadata.num_rows
    selected_columns = _select_columns(parquet.schema_arrow.names, columns)
    column_types = {
        field.name: str(field.type)
        for field in parquet.schema_arrow
        if field.name in selected_columns
    }

    if offset >= total:
        rows: List[Dict[str, Any]] = []
    else:
        requested_end = min(offset + limit, total)
        selected_groups: List[int] = []
        first_group_start = 0
        current_start = 0

        for group_index in range(metadata.num_row_groups):
            group_rows = metadata.row_group(group_index).num_rows
            group_end = current_start + group_rows
            if group_end > offset and current_start < requested_end:
                if not selected_groups:
                    first_group_start = current_start
                selected_groups.append(group_index)
            current_start = group_end
            if current_start >= requested_end:
                break

        tables = [
            parquet.read_row_group(index, columns=selected_columns)
            for index in selected_groups
        ]
        if tables:
            combined = pa.concat_tables(tables, promote_options="default")
            page = combined.slice(
                offset - first_group_start,
                requested_end - offset,
            )
            raw_rows = page.to_pylist()
        else:
            raw_rows = []
        rows = [
            {name: _serialize_cell(row.get(name)) for name in selected_columns}
            for row in raw_rows
        ]

    returned = len(rows)
    return {
        "format": "parquet",
        "columns": [
            {"name": name, "type": column_types[name]}
            for name in selected_columns
        ],
        "rows": rows,
        "offset": offset,
        "limit": limit,
        "returned": returned,
        "total": total,
        "has_more": offset + returned < total,
    }


def preview_csv(
    path: Path,
    offset: int,
    limit: int,
    columns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Parcourt le CSV en flux sans charger le fichier entier."""
    _validate_pagination(offset, limit)
    rows: List[Dict[str, Any]] = []
    total = 0
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        selected_columns = _select_columns(reader.fieldnames or [], columns)
        for row_index, row in enumerate(reader):
            if row_index >= offset and len(rows) < limit:
                rows.append({
                    name: _serialize_cell(row.get(name))
                    for name in selected_columns
                })
            total += 1
    return {
        "format": "csv",
        "columns": [
            {"name": name, "type": "string"}
            for name in selected_columns
        ],
        "rows": rows,
        "offset": offset,
        "limit": limit,
        "returned": len(rows),
        "total": total,
        "has_more": offset + len(rows) < total,
    }


def preview_table(
    job_id: str,
    job_dir: Path,
    result_id: str,
    offset: int = 0,
    limit: int = DEFAULT_LIMIT,
    columns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Prévisualise une table déclarée dans le manifeste."""
    path = resolve_table_result(job_id, job_dir, result_id)
    if path.suffix.lower() == ".parquet":
        preview = preview_parquet(path, offset, limit, columns)
    elif path.suffix.lower() == ".csv":
        preview = preview_csv(path, offset, limit, columns)
    else:
        raise ValueError("Format tabulaire non pris en charge.")
    return {"result_id": result_id, **preview}
