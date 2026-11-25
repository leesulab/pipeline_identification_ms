"""Prévisualisation paginée des résultats CSV et Parquet."""

import csv
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import duckdb
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


def _quote_identifier(name: str) -> str:
    """Protège un nom de colonne validé pour DuckDB."""
    return '"' + name.replace('"', '""') + '"'


def _validate_sort(
    available_columns: Iterable[str],
    sort_by: Optional[str],
    sort_direction: Optional[str],
) -> Optional[str]:
    """Valide et construit la clause ORDER BY."""
    if sort_by is None:
        if sort_direction is not None:
            raise ValueError(
                "sort_direction nécessite sort_by."
            )

        return None

    available = list(available_columns)

    if sort_by not in available:
        raise ValueError(
            f"Colonne de tri inconnue : {sort_by}."
        )

    direction = (
        sort_direction or "asc"
    ).lower()

    if direction not in {"asc", "desc"}:
        raise ValueError(
            "La direction de tri doit être "
            "'asc' ou 'desc'."
        )

    return (
        f"{_quote_identifier(sort_by)} "
        f"{direction.upper()} NULLS LAST"
    )


FILTER_OPERATORS = {
    "eq",
    "ne",
    "lt",
    "lte",
    "gt",
    "gte",
    "contains",
    "starts_with",
    "is_null",
    "not_null",
    "is_empty",
    "not_empty",
}


def _build_filter_clause(
    available_columns: Iterable[str],
    filters: Optional[List[Dict[str, Any]]],
) -> tuple[str, List[Any]]:
    """Construit une clause WHERE DuckDB paramétrée."""
    if not filters:
        return "", []

    available = set(available_columns)
    conditions: List[str] = []
    parameters: List[Any] = []

    comparison_operators = {
        "eq": "=",
        "ne": "<>",
        "lt": "<",
        "lte": "<=",
        "gt": ">",
        "gte": ">=",
    }

    for index, filter_item in enumerate(filters):
        filter_number = index + 1

        if not isinstance(filter_item, dict):
            raise ValueError(
                f"Filtre {filter_number} invalide."
            )

        column = filter_item.get("column")
        operator = filter_item.get("operator")
        value = filter_item.get("value")

        if not isinstance(column, str):
            raise ValueError(
                f"Filtre {filter_number} : colonne invalide."
            )

        if column not in available:
            raise ValueError(
                f"Colonne de filtre inconnue : {column}."
            )

        if operator not in FILTER_OPERATORS:
            raise ValueError(
                f"Opérateur de filtre inconnu : {operator}."
            )

        quoted_column = _quote_identifier(column)

        if operator in comparison_operators:
            if value is None:
                raise ValueError(
                    f"Le filtre {column} nécessite une valeur."
                )

            conditions.append(
                f"{quoted_column} "
                f"{comparison_operators[operator]} ?"
            )
            parameters.append(value)
            continue

        if operator in {
            "contains",
            "starts_with",
        }:
            if not isinstance(value, str):
                raise ValueError(
                    f"Le filtre texte {column} "
                    "nécessite une chaîne."
                )

            pattern = (
                f"%{value}%"
                if operator == "contains"
                else f"{value}%"
            )

            conditions.append(
                f"CAST({quoted_column} AS VARCHAR) "
                "ILIKE ?"
            )
            parameters.append(pattern)
            continue

        if operator == "is_null":
            conditions.append(
                f"{quoted_column} IS NULL"
            )
            continue

        if operator == "not_null":
            conditions.append(
                f"{quoted_column} IS NOT NULL"
            )
            continue

        if operator == "is_empty":
            conditions.append(
                "("
                f"{quoted_column} IS NULL "
                "OR "
                f"TRIM(CAST({quoted_column} AS VARCHAR)) = ''"
                ")"
            )
            continue

        if operator == "not_empty":
            conditions.append(
                "("
                f"{quoted_column} IS NOT NULL "
                "AND "
                f"TRIM(CAST({quoted_column} AS VARCHAR)) <> ''"
                ")"
            )

    return (
        " WHERE " + " AND ".join(conditions),
        parameters,
    )


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
    sort_by: Optional[str] = None,
    sort_direction: Optional[str] = None,
    filters: Optional[
        List[Dict[str, Any]]
    ] = None,
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

    order_clause = _validate_sort(
        parquet.schema_arrow.names,
        sort_by,
        sort_direction,
    )

    where_clause, filter_parameters = (
        _build_filter_clause(
            parquet.schema_arrow.names,
            filters,
        )
    )

    if order_clause is not None or filters:
        selected_sql = ", ".join(
            _quote_identifier(name)
            for name in selected_columns
        )

        order_sql = (
            f" ORDER BY {order_clause}"
            if order_clause is not None
            else ""
        )

        page_query = f"""
            SELECT {selected_sql}
            FROM read_parquet(?)
            {where_clause}
            {order_sql}
            LIMIT ?
            OFFSET ?
        """

        count_query = f"""
            SELECT COUNT(*)
            FROM read_parquet(?)
            {where_clause}
        """

        connection = duckdb.connect()

        try:
            total = connection.execute(
                count_query,
                [
                    str(path),
                    *filter_parameters,
                ],
            ).fetchone()[0]

            raw_rows = connection.execute(
                page_query,
                [
                    str(path),
                    *filter_parameters,
                    limit,
                    offset,
                ],
            ).fetchall()
        finally:
            connection.close()

        rows = [
            {
                name: _serialize_cell(value)
                for name, value in zip(
                    selected_columns,
                    row,
                )
            }
            for row in raw_rows
        ]

        returned = len(rows)

        return {
            "format": "parquet",
            "columns": [
                {
                    "name": name,
                    "type": column_types[name],
                }
                for name in selected_columns
            ],
            "rows": rows,
            "offset": offset,
            "limit": limit,
            "returned": returned,
            "total": total,
            "has_more": offset + returned < total,
            "sort_by": sort_by,
            "sort_direction": (
                (sort_direction or "asc").lower()
                if sort_by is not None
                else None
            ),
            "filters": filters or [],
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
    sort_by: Optional[str] = None,
    sort_direction: Optional[str] = None,
    filters: Optional[
        List[Dict[str, Any]]
    ] = None,
) -> Dict[str, Any]:
    """Prévisualise une table déclarée dans le manifeste."""
    path = resolve_table_result(job_id, job_dir, result_id)
    if path.suffix.lower() == ".parquet":
        preview = preview_parquet(
            path,
            offset,
            limit,
            columns,
            sort_by,
            sort_direction,
            filters,
        )
    elif path.suffix.lower() == ".csv":
        preview = preview_csv(path, offset, limit, columns)
    else:
        raise ValueError("Format tabulaire non pris en charge.")
    return {"result_id": result_id, **preview}
