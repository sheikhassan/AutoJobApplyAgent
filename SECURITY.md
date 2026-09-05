# Job Hunter Agent — Production Security Model

## Safety goals
- Human-in-the-loop is mandatory. The agent never submits applications automatically.
- All provider credentials stay server-side in environment variables/secrets.
- Third-party job pages/search results are treated as untrusted input and are isolated from model instructions.
- External content fetching rejects localhost, private, reserved, link-local, multicast, and unspecified network targets.
- Session authentication uses a signed HTTP-only cookie; state-changing requests require a CSRF token.
- Login and API requests are rate-limited; Redis is the production limiter backend.
- Security headers and a restrictive CSP are added by the API and HTTPS is terminated by Caddy.
- Security events are recorded in PostgreSQL.

## Threats covered
1. **Credential theft:** no API keys are returned by API endpoints or sent to the browser.
2. **Prompt injection:** job descriptions/snippets are explicitly untrusted in model prompts.
3. **SSRF:** job/content URLs are syntactically and DNS validated before content fetches.
4. **CSRF/session abuse:** SameSite cookies, CSRF token binding, signed sessions, secure-cookie mode.
5. **Brute force:** Redis-backed login rate limiting.
6. **Clickjacking/content sniffing:** X-Frame-Options and X-Content-Type-Options.
7. **Application automation risk:** no auto-apply capability exists; UI exposes only the external application page.
8. **Auditability:** login, logout, rate-limit, and application-status events are logged.

## Production requirements
- Set `REQUIRE_HTTPS=true` and `COOKIE_SECURE=true`.
- Set a strong `DASHBOARD_PASSWORD` and a random `DASHBOARD_SESSION_SECRET` (32+ characters).
- Set `REDIS_URL` and keep PostgreSQL/Redis private to the Docker network.
- Put the stack behind the included Caddy reverse proxy and use a real DNS name in `DOMAIN`.
- Rotate any credentials that were previously exposed outside the server secret store.
- Back up PostgreSQL and monitor `/health` and `/ready`.

## Residual risk
DNS validation cannot mathematically eliminate every DNS-rebinding race when a third-party
HTTP client resolves a hostname again later. For highest assurance, route outbound content
fetching through a dedicated egress proxy/firewall with private-address blocking and an
explicit allow/deny policy.
