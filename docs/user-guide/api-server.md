# REST API Server

`pbd-toolkit serve` starts a local REST API for triggering scans and querying
analytics, backed by the same scan pipeline as the CLI.

```bash
PBD_API_KEY="$(openssl rand -hex 32)" pbd-toolkit serve --port 8000
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

Configure a key with the `PBD_API_KEY` environment variable. (`--api-key` still
works but is deprecated: command-line arguments are visible to every local
user in the process list.) Requests must then send
`Authorization: Bearer <key>`. Only `/api/v1/health` is reachable without a
key so load balancers can probe the service; the OpenAPI schema and the
interactive docs (`/docs`, `/openapi.json`, `/redoc`) require the key too.

Error responses never include server-side detail: a path outside the allowed
roots is reported as such without listing the roots, and unexpected failures
return a generic `500` while the traceback goes to the server log.

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

**Behind a reverse proxy** every request arrives from the proxy's address, so
all clients share one bucket. If (and only if) a proxy you control sets
`X-Forwarded-For`, start with `--trust-proxy-headers` (or
`PBD_TRUST_PROXY_HEADERS=1`) to key the limiter on the left-most forwarded
address. Never enable this on a directly exposed server: clients could forge
the header to escape the limit.

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
| `--api-key` (deprecated) | `PBD_API_KEY` | unset | Bearer token required on protected endpoints; prefer the env var |
| `--trust-proxy-headers` | `PBD_TRUST_PROXY_HEADERS` | `false` | Rate-limit by `X-Forwarded-For` (only behind a trusted proxy) |
| `--allow-unauthenticated` | `PBD_ALLOW_UNAUTHENTICATED` | `false` | Opt out of the no-key startup refusal |
| `--allowed-scan-roots` | — | current directory | Directories the scan API may access |
| `--cors-origins` | — | `localhost:3000`, `localhost:8080` | Allowed CORS origins |
| `--scan-workers` | `PBD_SCAN_WORKERS` | `2` | Worker threads for background scans |

Rate limits (60/min general, 5/min scan creation) are configurable only via
`create_app()` keyword arguments today, not through `serve` flags.
