"""Uvicorn server entry point for the PBD Toolkit REST API.

Can be started standalone::

    python -m api.server --port 8000

Or via the CLI::

    pii-toolkit serve --port 8000
"""

from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and start the uvicorn server."""
    parser = argparse.ArgumentParser(description="PBD Toolkit API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--analytics-db", default=".pbd_analytics.db", help="Analytics DB path")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev only)")
    parser.add_argument("--api-key", default=None, help="API key for Bearer authentication (or set PBD_API_KEY)")
    parser.add_argument(
        "--allowed-scan-roots",
        default=None,
        help="Comma-separated list of directories the scan API may access (default: cwd)",
    )
    parser.add_argument(
        "--cors-origins",
        default=None,
        help="Comma-separated list of allowed CORS origins",
    )
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

    # Pass configuration via environment so the factory can pick it up,
    # or build the app directly when using non-string config.
    os.environ.setdefault("PBD_ANALYTICS_DB", args.analytics_db)
    if args.api_key:
        os.environ["PBD_API_KEY"] = args.api_key
    if args.allowed_scan_roots:
        os.environ["PBD_ALLOWED_SCAN_ROOTS"] = args.allowed_scan_roots
    if args.cors_origins:
        os.environ["PBD_CORS_ORIGINS"] = args.cors_origins

    from api.app import create_app

    cors_origins = args.cors_origins.split(",") if args.cors_origins else None
    allowed_roots = args.allowed_scan_roots.split(",") if args.allowed_scan_roots else None

    app = create_app(
        analytics_db_path=args.analytics_db,
        cors_origins=cors_origins,
        api_key=args.api_key,
        allowed_scan_roots=allowed_roots,
    )

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
