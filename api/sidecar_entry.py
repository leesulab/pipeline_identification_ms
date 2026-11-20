"""Point d'entrée du sidecar autonome construit avec PyInstaller."""

from api import app as api_app  # noqa: F401
from api.sidecar import main


if __name__ == "__main__":
    main()
