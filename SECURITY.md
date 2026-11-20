# Security Policy — ReLink

ReLink is a prototype trust platform (messaging, Security Teacher, Verify, Link Planner, Lunar Relay game). This document describes the protections implemented in the code and the known limitations.

## Implemented protections

### Authentication and sessions
- Passwords are hashed with **scrypt** (random 16-byte salt, `n=2^14, r=8, p=1`) and compared in constant time.
- Passwords must be 10-128 characters, with a basic weak-password check. Usernames must match `^[a-z0-9_]{3,24}$`.
- Login for an unknown username still performs a dummy hash, so timing does not reveal which usernames exist.
- Sessions use **HMAC-SHA256 signed tokens** that expire after 12 hours. Logging out increments a per-user token version, which invalidates existing tokens.
- The signing key comes from `RELINK_SECRET`. If unset, a random key is generated in `data/.secret` with `0600` permissions.

### Abuse protection
- Per-IP limit: 240 requests per minute across the API.
- Auth endpoints: 12 attempts per minute per IP.
- Login: 8 attempts per minute per username.
- Verify endpoint: 12 requests per minute per IP.
- Request bodies are limited to 64 KB and must be a valid JSON object. Invalid or negative `Content-Length` values are rejected, and connections time out after 15 seconds.
- `X-Forwarded-For` is trusted only when the direct connection comes from a non-public (proxy) address or one listed in `TRUSTED_PROXY_CIDRS`, so clients cannot spoof their IP.

### Data access control
- All SQL uses **parameterized queries**.
- Every conversation endpoint verifies that the caller is a member of that conversation.
- Direct messages and groups require accepted, unblocked contacts. Blocks apply in both directions.
- Users can only report messages they can see.
- Input lengths are capped for messages, titles, display names, search and report reasons.

### Browser protections
- Response headers: `Content-Security-Policy` (`default-src 'self'`, `frame-ancestors 'none'`, no inline scripts), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`.
- API responses use `Cache-Control: no-store`.
- All dynamic content is rendered with `textContent`, never `innerHTML`, which prevents XSS from user-supplied text.
- Static file serving resolves paths and blocks directory traversal.

### Privacy and user control
- Users can export their data and delete their account (password required). Deletion removes messages, memberships, contacts, blocks and verification history.
- Optional message retention limit via `RETENTION_DAYS`.
- Read receipts can be switched off per user.
- Security Teacher and Verify only analyse text the user chooses to submit. Nothing is read automatically.

### Deployment
- The Docker image runs as a **non-root** user.
- API keys (Tavily, Gemini, Bifrost) are read from environment variables only. `.env` is git-ignored and `.env.example` contains no secrets.
- CI runs the test suite on every push.

## Known limitations

- **Messages are not end-to-end encrypted.** The server can read them. Do not send secrets.
- **No encryption at rest** for the SQLite database.
- **HTTPS depends on the hosting platform.** The app itself serves plain HTTP and does not send an HSTS header.
- The session token is stored in `sessionStorage`, so a future XSS bug could expose it. The CSP and `textContent` rendering reduce this risk.
- The CSP allows `style-src 'unsafe-inline'`.
- No email verification, password reset or multi-factor authentication.
- Reports are stored but there is no moderation interface.
- Security Teacher is rule-based screening, not a malware scanner.
- Verify and Link Planner results are informational and have documented limits (see `docs/METHODS.md`).

## Recommended production configuration

1. Set a long random `RELINK_SECRET`.
2. Serve only over HTTPS and add an HSTS header at the proxy.
3. Mount persistent storage at `/app/data` and set `RELINK_DB=/app/data/relink.db`.
4. Store API keys as platform secrets, never in the repository.
5. Pin dependency versions and enable dependency update alerts.

## Reporting a vulnerability

Please open a private security advisory on the GitHub repository or contact the maintainer directly. Do not post exploit details in public issues. We aim to acknowledge reports within 3 days.
