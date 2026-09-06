"""Uvicorn server entry point for the PBD Toolkit REST API.

Can be started standalone::

    python -m api.server --port 8000

Or via the CLI::

    pbd-toolkit serve --port 8000
"""

from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and start the uvicorn server."""
    parser = argparse.ArgumentParser(description="PBD Toolkit API Server")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)"
    )
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument(
        "--analytics-db", default=".pbd_analytics.db", help="Analytics DB path"
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload (dev only)"
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help=(
            "DEPRECATED: API key for Bearer authentication. Command-line "
            "arguments are visible to every local user via the process list; "
            "set PBD_API_KEY instead."
        ),
    )
    parser.add_argument(
        "--trust-proxy-headers",
        action="store_true",
        help=(
            "Rate-limit by the left-most X-Forwarded-For address instead of the "
            "socket peer (or set PBD_TRUST_PROXY_HEADERS=1). Only behind a "
            "reverse proxy you control."
        ),
    )
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
    parser.add_argument(
        "--allow-unauthenticated",
        action="store_true",
        help=(
            "Explicitly opt out of authentication when no API key is set "
            "(or set PBD_ALLOW_UNAUTHENTICATED=1). Without this, the server "
            "refuses to start unauthenticated."
        ),
    )
    parser.add_argument(
        "--scan-workers",
        type=int,
        default=None,
        help="Worker-thread count for background scans (default: 2, or PBD_SCAN_WORKERS)",
    )
    args = parser.parse_args(argv)

    try:
        import uvicorn
    except ImportError:
        print(
            "uvicorn is required to run the API server.\n"
            "Install it with:  pip install 'pbd-toolkit[api]'",
            file=sys.stderr,
        )
        sys.exit(1)

    # Pass configuration via environment so the factory can pick it up,
    # or build the app directly when using non-string config.
    os.environ.setdefault("PBD_ANALYTICS_DB", args.analytics_db)
    if args.api_key:
        print(
            "Warning: --api-key is deprecated because the key is visible in the "
            "process list; set the PBD_API_KEY environment variable instead.",
            file=sys.stderr,
        )
        os.environ["PBD_API_KEY"] = args.api_key
    if args.trust_proxy_headers:
        os.environ["PBD_TRUST_PROXY_HEADERS"] = "1"
    if args.allowed_scan_roots:
        os.environ["PBD_ALLOWED_SCAN_ROOTS"] = args.allowed_scan_roots
    if args.cors_origins:
        os.environ["PBD_CORS_ORIGINS"] = args.cors_origins

    try:
        from api.app import UnauthenticatedAPIError, create_app
    except ImportError:
        # uvicorn can be present as a transitive dependency (e.g. pulled in by
        # pydantic-ai) even when fastapi itself is not installed, so this import
        # needs its own guard rather than relying on the uvicorn check above.
        print(
            "fastapi is required to run the API server.\n"
            "Install it with:  pip install 'pbd-toolkit[api]'",
            file=sys.stderr,
        )
        sys.exit(1)

    cors_origins = args.cors_origins.split(",") if args.cors_origins else None
    allowed_roots = (
        args.allowed_scan_roots.split(",") if args.allowed_scan_roots else None
    )

    try:
        app = create_app(
            analytics_db_path=args.analytics_db,
            cors_origins=cors_origins,
            api_key=args.api_key,
            allowed_scan_roots=allowed_roots,
            allow_unauthenticated=args.allow_unauthenticated,
            scan_workers=args.scan_workers,
            trust_proxy_headers=args.trust_proxy_headers or None,
        )
    except UnauthenticatedAPIError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
