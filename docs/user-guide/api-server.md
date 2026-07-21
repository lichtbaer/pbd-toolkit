# REST API Server

`pbd-toolkit serve` starts a local REST API for triggering scans and querying
analytics, backed by the same scan pipeline as the CLI.

```bash
pbd-toolkit serve --api-key "$(openssl rand -hex 32)" --port 8000
```

## Authentication is required by default

The API scans directories for PII and stores findings metadata, so an
unauthenticated deployment is a serious foot-gun. Starting `serve` (or calling
`api.app.create_app` directly) **without an API key fails fast** with a clear
error instead of silently serving unauthenticated requests:

```
Error: Refusing to start the API without authentication: no API key was
configured (--api-key / PBD_API_KEY). ...
```

Configure a key with `--api-key` or the `PBD_API_KEY` environment variable.
Requests must then send `Authorization: Bearer <key>`. The `/api/v1/health`,
`/docs`, `/openapi.json`, and `/redoc` endpoints remain reachable without a
key so load balancers can probe the service.

If you deliberately want to run without authentication — for example behind
a reverse proxy on a locked-down internal network — opt out explicitly with
`--allow-unauthenticated` or `PBD_ALLOW_UNAUTHENTICATED=1`. Without one of
these, the server will not start.

## Rate limiting

`RateLimitMiddleware` enforces a sliding-window limit per client IP: a
general limit (60/min) and a stricter limit for scan creation (5/min). These
are not yet exposed as `serve` flags; embed `api.app.create_app(rate_limit=...,
scan_rate_limit=...)` directly if you need different values. Idle client
buckets are evicted automatically so memory stays bounded under IP churn.

**Rate limits are per-process.** Running `uvicorn --workers N` or multiple
replicas behind a load balancer multiplies the effective limit by the number
of processes, since each worker keeps its own in-memory buckets. For
deployments that need a hard global limit:

- Prefer a **single worker** and enforce additional limits at a reverse
  proxy (nginx, Envoy, Traefik) in front of it, or
- Accept that the configured limits are *per worker* and size them
  accordingly (e.g. divide the desired total by the worker count).

A shared external rate-limit backend (e.g. Redis) is intentionally not a
default dependency; consider it if you need an exact global limit across
many processes.

## Scan concurrency

Background scans run in a `ThreadPoolExecutor` owned by `ScannerService`.
The worker count defaults to 2 and is configurable with `--scan-workers` or
the `PBD_SCAN_WORKERS` environment variable — raise it if you expect many
concurrent scan requests, keeping in mind each scan is itself CPU/IO bound.

## Options reference

| Flag | Env var | Default | Purpose |
|------|---------|---------|---------|
| `--api-key` | `PBD_API_KEY` | unset | Bearer token required on protected endpoints |
| `--allow-unauthenticated` | `PBD_ALLOW_UNAUTHENTICATED` | `false` | Opt out of the no-key startup refusal |
| `--allowed-scan-roots` | — | current directory | Directories the scan API may access |
| `--cors-origins` | — | `localhost:3000`, `localhost:8080` | Allowed CORS origins |
| `--scan-workers` | `PBD_SCAN_WORKERS` | `2` | Worker threads for background scans |

Rate limits (60/min general, 5/min scan creation) are configurable only via
`create_app()` keyword arguments today, not through `serve` flags.
