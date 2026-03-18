"""Uvicorn server entry point for the PBD Toolkit REST API.

Can be started standalone::

    python -m api.server --port 8000

Or via the CLI::

    pii-toolkit serve --port 8000
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and start the uvicorn server."""
    parser = argparse.ArgumentParser(description="PBD Toolkit API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--analytics-db", default=".pbd_analytics.db", help="Analytics DB path")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev only)")
    args = parser.parse_args(argv)

    try:
        import uvicorn
    except ImportError:
        print(
            "uvicorn is required to run the API server.\n"
            "Install it with:  pip install 'pii-toolkit[api]'",
            file=sys.stderr,
        )
        sys.exit(1)

    # Store DB path in environment so the app factory can pick it up
    import os
    os.environ.setdefault("PBD_ANALYTICS_DB", args.analytics_db)

    uvicorn.run(
        "api.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
