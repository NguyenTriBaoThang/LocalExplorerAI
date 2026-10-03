# Production operations and release checks

## What is operationalized

- Email is an optional outbound notification channel. Configure SMTP, apply migration `0008_operations_notifications`, then run the `worker` service. Booking requests/decisions and provider slot cancellations enter the database outbox in the same transaction as the business change. Idempotency keys prevent duplicate rows; temporary SMTP failures retry with exponential backoff, and exhausted messages move to `failed`.
- Admin-only `GET /api/ops/status`, `/api/ops/jobs`, `/api/ops/events`, and `/api/ops/notifications` expose delivery/job/event health. The monitoring API omits recipient addresses and message bodies. Protect it with an admin session or `X-Admin-Key`; do not publish the key to a browser or monitoring dashboard accessible to guests.
- `GET /health` is process liveness. `GET /ready` tests PostgreSQL and, when rate limiting is enabled, Redis. Production Compose enables the shared Redis fixed-window limiter (auth, chat/AI, general quotas); Redis failure returns 503 instead of silently disabling the protection. The app ignores forwarded-IP headers by default. If behind a proxy, set `TRUSTED_PROXY_IPS` to the proxy's exact IP/CIDR ranges and configure the ingress to overwrite/append `X-Forwarded-For`; never trust arbitrary client-supplied forwarded headers.
- HTTP access logs are structured JSON with request ID, method, path, status and duration. Query strings, request bodies, authorization headers and client addresses are not logged. Return/capture `X-Request-ID` when investigating an incident. Container stdout/stderr must be collected by the host's restricted, rotated log service.

## Environment

Copy `.env.example` to an untracked `.env`, replace all demo/default secrets, and configure at least `DATABASE_URL`, `REDIS_URL`, `AUTH_SECRET`, `APP_SIGNING_SECRET`, `ADMIN_API_KEY`, exact `CORS_ORIGINS`, and SMTP settings if email is required. For SMTP use port 587 with `SMTP_STARTTLS=true`, or port 465 with `SMTP_USE_SSL=true` (not both). Never commit credentials. If SMTP is blank the app reports email disabled and does not enqueue email messages; the existing in-app event feed continues to work.

```powershell
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
./scripts/production-smoke.ps1 -BaseUrl https://api.example.com
```

Apply migrations before serving traffic. The development Compose command does this automatically; for controlled production deploys use a one-off API container/job, verify its exit code, then update API and worker. Do not run two independent migration jobs concurrently. Operations endpoints require admin authentication.

For example, after PostgreSQL/Redis are reachable and the production environment file is loaded, run `docker compose -f docker-compose.prod.yml run --rm --no-deps api alembic upgrade head` and verify its exit code before `up -d`.

## Backup and restore

Install PostgreSQL client tools (`pg_dump`, `pg_restore`) matching or newer than the server major version. Set `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and provide `PGPASSWORD` through a secret manager or `.pgpass` (never place a password in shell history). Examples:

```powershell
./scripts/backup-postgres.ps1 -OutputDirectory G:\Backups\LocalExplorer
./scripts/restore-postgres.ps1 -BackupFile G:\Backups\LocalExplorer\local-explorer-local_explorer-20261004-120000Z.dump -TargetDatabase local_explorer_restore_test
```

Linux/container operators can use `bash scripts/backup-postgres.sh <existing-output-directory>` and `bash scripts/restore-postgres.sh <backup.dump> <target-database>`. The restore script validates the archive then uses `pg_restore --clean --if-exists`: it overwrites restored objects in the target database. Type the exact target name when prompted, and restore to an isolated database first. Backups are not encrypted by these scripts; store them in encrypted, access-controlled, off-host storage, define retention, and regularly rehearse restoration. These scripts create PostgreSQL logical dumps only; they do not back up Redis, uploaded media, model artifacts, or external secrets.

## Release acceptance

1. Run `docker compose -f docker-compose.prod.yml config`; check no default credentials, wildcard CORS or missing secrets are present.
2. Run `pytest -q` from `apps/api`. A printed `[100%]` is not sufficient: the process must terminate on its own with exit code **0**. If it hangs, capture the active process/thread and fix or report it; do not report the suite as passing or stop it manually and infer success.
3. Run migration upgrade against a disposable PostgreSQL/PostGIS database and verify `alembic current` is at `0008_operations_notifications`.
4. Check `/health`, `/ready`, protected ops endpoints (401/403 without admin, 200 with admin), rate-limit responses, and SMTP outbox delivery/retry in a staging environment.
5. Rehearse backup plus restore into an isolated database; verify row counts, migrations and application readiness before approving a production release.

An earlier review run printed 19 dots and `[100%]` but did not terminate and had no successful exit code; that run was not evidence of a pass. The current review re-ran the complete API suite: 44 tests passed, pytest terminated normally with exit code 0 (10.81 seconds). The earlier hang was not reproduced; continue to require a normal exit code of zero on each release run.

GitHub Actions now runs the backend suite with `pytest -q` and a 10-minute job timeout, so a hung test job fails instead of staying indefinitely green/pending.
