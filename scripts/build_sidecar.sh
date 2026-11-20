#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
  pwd
)"

PYTHON="${PROJECT_DIR}/.venv/bin/python"
TARGET_TRIPLE="${TARGET_TRIPLE:-x86_64-unknown-linux-gnu}"
SIDECAR_NAME="pipeline-api-sidecar"
OUTPUT_DIR="${1:-${PROJECT_DIR}/dist/tauri-sidecar}"
OUTPUT_NAME="${SIDECAR_NAME}-${TARGET_TRIPLE}"

if [ ! -x "${PYTHON}" ]; then
  echo "ERREUR: environnement Python introuvable: ${PYTHON}" >&2
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"

rm -rf \
  "${PROJECT_DIR}/build/pyinstaller-onefile" \
  "${PROJECT_DIR}/${SIDECAR_NAME}.spec" \
  "${OUTPUT_DIR:?}/${OUTPUT_NAME}"

echo "=== Construction du sidecar ==="
echo "Cible: ${TARGET_TRIPLE}"
echo "Sortie: ${OUTPUT_DIR}/${OUTPUT_NAME}"

cd "${PROJECT_DIR}"

"${PYTHON}" -m PyInstaller \
  --noconfirm \
  --clean \
  --onefile \
  --name "${OUTPUT_NAME}" \
  --workpath "${PROJECT_DIR}/build/pyinstaller-onefile" \
  --distpath "${OUTPUT_DIR}" \
  --specpath "${PROJECT_DIR}" \
  --paths "${PROJECT_DIR}" \
  --hidden-import api.app \
  --hidden-import api.jobs \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan.on \
  "${PROJECT_DIR}/api/sidecar_entry.py"

chmod 755 "${OUTPUT_DIR}/${OUTPUT_NAME}"

echo
echo "=== Sidecar produit ==="
file "${OUTPUT_DIR}/${OUTPUT_NAME}"
du -h "${OUTPUT_DIR}/${OUTPUT_NAME}"
sha256sum "${OUTPUT_DIR}/${OUTPUT_NAME}"
