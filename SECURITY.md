# Security Policy

The pbD Toolkit scans directories for personal data. Its outputs, caches and
indexes therefore contain exactly the data it is meant to find, and its input
is by definition untrusted (arbitrary files, possibly crafted). Reports about
either side are welcome.

## Supported versions

There are no tagged releases yet. Security fixes land on the `main` branch;
use the latest commit on `main`.

## Reporting a vulnerability

Please do **not** open a public issue for a vulnerability.

1. Preferred: use GitHub's private vulnerability reporting for this repository
   (Security tab → "Report a vulnerability", or
   <https://github.com/lichtbaer/pbd-toolkit/security/advisories/new>).
2. If that is not available to you, open an issue titled "Security contact
   request" **without any details**; a maintainer will reply with a private
   channel.

Include what you can: affected command or endpoint, a minimal reproducer
(a crafted file, a request), the impact you see, and the commit you tested.

You can expect an acknowledgement within 7 days. Confirmed issues are fixed on
`main` and credited in the commit message unless you ask otherwise.

## What counts

In scope, for example:

- Reading, writing or executing outside the directories a user pointed the
  tool at (path traversal via archive members, symlinks, generated hook
  scripts, API scan roots).
- Personal data leaking into places the documentation says it does not go
  (privacy statistics mode, analytics database, logs, cache and index files,
  pseudonymised output).
- Authentication or authorisation bypass in the REST API, or server-side
  detail disclosed to API clients.
- Resource exhaustion through crafted inputs (archive bombs, oversized
  mailboxes, deeply nested documents) beyond the documented limits.
- Weaknesses in the pseudonymisation scheme (guessable or reversible
  pseudonyms).

Out of scope:

- Sending data to an LLM or vision endpoint you configured yourself; that is
  documented behaviour (see the security analysis linked below).
- Vulnerabilities in third-party models or model hosting services.
- Findings that require an already compromised host or the API key.

## Hardening guidance

The threat model, privacy properties and operational safeguards are described
in [docs/about/security-analysis.md](docs/about/security-analysis.md). The
REST API's authentication, rate limiting and proxy considerations are covered
in [docs/user-guide/api-server.md](docs/user-guide/api-server.md).

## Automated checks

Every push runs Bandit (static analysis) and pip-audit against the exact
dependency set pinned in `uv.lock`, in addition to the test suite.
