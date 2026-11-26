# Render deployment without GitHub

Prepared for Docker Hub namespace `carolnaddunga`. Local exam lab storage remains SQLite; hosted storage uses PostgreSQL. The cloud copy is the normal application only, not the intentionally vulnerable exam target.

## Build and upload

In the project folder, with Docker Desktop running and signed into Docker Hub:

```powershell
docker buildx build --platform linux/amd64 --load -t carolnaddunga/harvestshield:2026-11-25 .
docker push carolnaddunga/harvestshield:2026-11-25
```

Render requires linux/amd64 images. On Windows ARM or Apple silicon this build uses Docker's cross-platform support. Native local lab builds can continue using their host architecture. The image copies app/scripts/requirements only. Runtime databases, .env files, evidence and tests are excluded; no preview password is embedded.

## Render resources (Free only)

1. Create a new **PostgreSQL** instance named `harvestshield-db`, on the **Free** plan. Use the same region as the app. Do not change or delete another project's existing database.
2. Render allows one free PostgreSQL instance per workspace. If that allowance is already in use, stop and resolve it without upgrading or deleting existing data.
3. Create a **Web Service → Existing Image** using `docker.io/carolnaddunga/harvestshield:2026-11-25` after its push is verified. Choose **Free**.
4. Set health check path `/health` and port `10000` (the app reads Render's PORT environment variable).
5. Enter environment values in Render, never source control or chat:

| Key | Value |
| --- | --- |
| `DATABASE_URL` | The new Render PostgreSQL instance's internal connection URL, entered directly in Render |
| `HARVESTSHIELD_SECURE_COOKIES` | `1` |
| `HARVESTSHIELD_ADMIN_PASSWORD` | A unique administrator password of at least 16 characters, chosen privately |
| `HARVESTSHIELD_CLERK_PASSWORD` | A different clerk password of at least 16 characters, chosen privately |

The existing entry point is `python -m scripts.serve --host 0.0.0.0`; no manual seed command or Docker CMD override is needed. First startup creates synthetic fixtures and configures admin/clerk credentials from the environment. Existing accounts/passwords are not overwritten on a restart. Seeded farmer credentials are random and inaccessible; new farmers use registration. Never reuse the known local preview password online. Database credentials and startup passwords must never be baked into the image.

6. Deploy, wait for **Live**, open the exact HTTPS URL Render returns and check `/health`, sign-in and registration.
7. Sign in as `admin` with your chosen admin password; `clerk01` and `clerk02` use your chosen clerk password. New farmers create their own accounts. Use only synthetic information in the exam project.
8. Create a record and verify it remains after a controlled service restart before relying on the hosted copy.

## Free-plan constraints

Render's free web service sleeps after inactivity and takes time to wake. Its filesystem is ephemeral, which is why the app must use DATABASE_URL rather than hosted SQLite. The free PostgreSQL database expires after 30 days; it does not include managed backups. Export data before expiry or move it elsewhere. Do not enable a paid plan or supply payment approval as part of this deployment.

This app does not move your existing Mac or Windows database online. New hosted data stays in the separately configured PostgreSQL database. Keep the lab and hosted application's data/configuration distinct.

References checked 25 November 2026:
- https://render.com/docs/deploying-an-image
- https://render.com/docs/web-services
- https://render.com/docs/free
- https://www.psycopg.org/psycopg3/docs/

## Development verification

The complete HTTP suite can run against SQLite or a real isolated PostgreSQL database. To test PostgreSQL locally, set `HARVESTSHIELD_TEST_POSTGRES` to a test database URL before running unittest. Each test uses a unique temporary schema that is removed at cleanup. Never point the test suite at your hosted application database.

Build/push/Render deployment status is reported separately; this file is setup documentation, not proof of an online deployment.
