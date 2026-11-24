"""Command-line entrypoint used by source runs and packaged binaries."""
import argparse
import os
import sys
from pathlib import Path

import uvicorn

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from oshy_service.api import app
    from oshy_service.version import APP_NAME, VERSION
else:
    from .api import app
    from .version import APP_NAME, VERSION


def main() -> None:
    parser = argparse.ArgumentParser(prog="oshyvpn", description=f"{APP_NAME} service")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"), help="Listen address (default: loopback)")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
