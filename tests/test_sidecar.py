"""Tests du lanceur sidecar destiné à Tauri."""

import json
import stat
from pathlib import Path

from api.sidecar import (
    LOCAL_HOST,
    create_connection_info,
    find_free_local_port,
    write_connection_file,
)


def test_create_secure_connection_file(
    tmp_path: Path,
) -> None:
    port = find_free_local_port()

    assert isinstance(port, int)
    assert 1 <= port <= 65535

    connection_info = create_connection_info(
        port=port,
        token="test-secret-token",
    )

    connection_file = (
        tmp_path
        / "runtime"
        / "pipeline-api.json"
    )

    write_connection_file(
        connection_file,
        connection_info,
    )

    stored_info = json.loads(
        connection_file.read_text(encoding="utf-8")
    )

    assert stored_info == {
        "host": LOCAL_HOST,
        "port": port,
        "base_url": f"http://{LOCAL_HOST}:{port}",
        "token": "test-secret-token",
        "health_url": (
            f"http://{LOCAL_HOST}:{port}/health"
        ),
    }

    permissions = stat.S_IMODE(
        connection_file.stat().st_mode
    )

    assert permissions == 0o600
