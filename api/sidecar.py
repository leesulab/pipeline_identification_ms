"""Lanceur local sécurisé de l'API pour l'application Tauri."""

import argparse
import json
import os
import secrets
import socket
from pathlib import Path
from typing import Dict, Union

import uvicorn


LOCAL_HOST = "127.0.0.1"


def find_free_local_port() -> int:
    """Réserve brièvement un port TCP libre sur l'interface locale."""
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as local_socket:
        local_socket.bind((LOCAL_HOST, 0))
        return int(local_socket.getsockname()[1])


def create_connection_info(
    *,
    port: int,
    token: str,
) -> Dict[str, Union[str, int]]:
    """Construit les informations transmises à Tauri."""
    return {
        "host": LOCAL_HOST,
        "port": port,
        "base_url": f"http://{LOCAL_HOST}:{port}",
        "token": token,
        "health_url": (
            f"http://{LOCAL_HOST}:{port}/health"
        ),
    }


def write_connection_file(
    connection_file: Path,
    connection_info: Dict[str, Union[str, int]],
) -> None:
    """Écrit atomiquement les informations de connexion."""
    connection_file = connection_file.expanduser().resolve()
    connection_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = connection_file.with_suffix(
        connection_file.suffix + ".tmp"
    )

    temporary_file.write_text(
        json.dumps(
            connection_info,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary_file.chmod(0o600)
    temporary_file.replace(connection_file)
    connection_file.chmod(0o600)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Lance l'API locale sécurisée de la pipeline HRMS."
        )
    )

    parser.add_argument(
        "--connection-file",
        type=Path,
        required=True,
        help=(
            "Fichier JSON dans lequel écrire le port "
            "et le jeton."
        ),
    )

    parser.add_argument(
        "--jobs-dir",
        type=Path,
        default=None,
        help="Dossier persistant des jobs.",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help=(
            "Port local. La valeur 0 choisit "
            "automatiquement un port libre."
        ),
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    port = (
        arguments.port
        if arguments.port > 0
        else find_free_local_port()
    )

    token = secrets.token_urlsafe(32)

    os.environ["PIPELINE_API_TOKEN"] = token

    if arguments.jobs_dir is not None:
        jobs_dir = arguments.jobs_dir.expanduser().resolve()
        jobs_dir.mkdir(parents=True, exist_ok=True)
        os.environ["PIPELINE_JOBS_DIR"] = str(jobs_dir)

    connection_info = create_connection_info(
        port=port,
        token=token,
    )

    write_connection_file(
        arguments.connection_file,
        connection_info,
    )

    # Tauri pourra aussi lire cette ligne sur stdout.
    print(
        json.dumps(
            connection_info,
            ensure_ascii=False,
        ),
        flush=True,
    )

    uvicorn.run(
        "api.app:app",
        host=LOCAL_HOST,
        port=port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
