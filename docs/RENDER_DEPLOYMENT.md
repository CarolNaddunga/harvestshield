# Render deployment without GitHub

Prepared for Docker Hub namespace `carolnaddunga`. Local exam lab storage remains SQLite; hosted storage uses PostgreSQL. The cloud copy is the normal application only, not the intentionally vulnerable exam target.

## Build and upload

In the project folder, with Docker Desktop running and signed into Docker Hub:

```powershell
docker buildx build --platform linux/amd64 --load -t carolnaddunga/harvestshield:2026-11-25 .
docker push carolnaddunga/harvestshield:2026-11-25
```

Render requires linux/amd64 images. On Windows ARM or Apple silicon this build uses Docker's cross-platform support. Native local lab builds can continue using their host architecture. The image copies app/scripts/requirements only. Runtime databases, .env files, evidence and tests are excluded; no preview password is embedded.

## Current route: Render Free web service + Neon Free database

Render's existing free database `book-borrower-db` belongs to another active project and must remain untouched. The root `render.yaml` now defines only HARVESTSHIELD's free web service. It no longer attempts to create `harvestshield-db`.

1. Create/sign in to a Neon account at https://console.neon.tech/ . Choose the Free plan. Name the project `harvestshield`. If offered, use PostgreSQL 16 (the tested version) and an AWS US West/Oregon region near the Render service. Do not add a payment method or select a paid plan.
2. In the Neon project, select Connect. Copy the PostgreSQL connection URI, including `sslmode=require` and any other supplied connection-security parameters. Copy the URI alone, not a surrounding psql command.
3. In Render's HARVESTSHIELD Blueprint or service environment, set `DATABASE_URL` to that URI. Enter it directly in Render; never put it in GitHub, a Docker image, a screenshot or chat.
4. Set `HARVESTSHIELD_SECURE_COOKIES=1`. Choose two different passwords of at least 16 characters for `HARVESTSHIELD_ADMIN_PASSWORD` and `HARVESTSHIELD_CLERK_PASSWORD`.
5. Select the updated GitHub commit in the existing HARVESTSHIELD Blueprint and retry its sync. The configuration should show only one free web service and no database-creation action. If Render does not prompt for the new DATABASE_URL during retry, add it through the service's environment settings or start the updated Blueprint form from the repository's Deploy link. Never delete Book Borrower resources to make room.
6. Wait for Live, open the exact HTTPS URL Render returns, and verify `/health`, login and registration. Sign in as `admin` with the administrator password; `clerk01`/`clerk02` use the clerk password. New farmers register their own accounts. Use only synthetic information.
7. Create a record and verify persistence after a controlled service restart. Back up important exam evidence separately.

The app’s `python -m scripts.serve --host 0.0.0.0` entry point reads Render's PORT, initialises a fresh hosted database and keeps existing credentials unchanged on restarts. Seeded farmer credentials are random and inaccessible; there is no known development password online. No existing Mac or Windows database is automatically uploaded.

The prebuilt Docker image route remains available using the same environment values, but the linked GitHub Blueprint is the current deployment route. Rebuild images after source changes before deploying them.

## Free-plan constraints

Render's free service can sleep and needs time to wake. Neon Free has usage and storage limits; it currently requires no credit card and has no fixed time limit. The two services' free-plan conditions can change, so verify the plan selections before deployment. The former Render PostgreSQL 30-day expiry does not apply to this external Neon setup.

References checked 26 November 2026:
- https://neon.com/pricing
- https://neon.com/docs/connect/connect-from-any-app
- https://render.com/docs/free
- https://render.com/docs/blueprint-spec

## Development verification

The complete HTTP suite can run against SQLite or a real isolated PostgreSQL database. To test PostgreSQL locally, set `HARVESTSHIELD_TEST_POSTGRES` to a test database URL before running unittest. Each test uses a unique temporary schema that is removed at cleanup. Never point the test suite at your hosted application database.

Build/push/Render deployment status is reported separately; this file is setup documentation, not proof of an online deployment.
