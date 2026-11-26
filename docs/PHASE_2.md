# Phase 2: working cooperative portal

Implemented 25 November 2026. The Phase 1 notes are historical; this document describes the current portal.

## Working routes

- `/`: public synthetic aggregate overview and photo credits.
- `/login`, POST `/logout`: role sign-in and sign-out.
- `/portal`: database-backed role workspace.
- `/deliveries`: searchable delivery list, filtered by farmer ownership where applicable.
- `/deliveries/new`: clerks/admins submit a delivery using server-controlled prices and pending status.
- `/deliveries/{id}`: details; farmers are restricted to their own deliveries.
- POST `/deliveries/{id}/status`: admin approval/rejection, with stale-record detection.
- `/farmers`, `/farmers/{id}`: member profiles, scoped to the current farmer or visible to clerks/admins.
- `/audit`: admin-only latest 200 application audit events, including actor, record, time and before/after status.
- `/users`: admin-only read-only account directory; hashes are never displayed.

## Security decisions to explain

One-hour server-side sessions use random opaque tokens; only SHA-256 token digests are stored in SQLite. Tokens rotate after login and are invalidated on logout. Session cookies are HttpOnly and SameSite=Strict; Secure is enabled when the request uses HTTPS. Local HTTP is for localhost development only, not public deployment. No proxy trust is configured.

Forms include a per-session CSRF token. All state-changing routes require POST. Role and ownership decisions are server-side. SQL uses bound parameters. Dynamic HTML is escaped. A 64 KiB request limit is enforced. Login verification uses salted scrypt, executed in a worker thread; unknown usernames also undergo a dummy hash verification. Account/source attempt counters limit login attempts to 10 per five-minute window.

Clerks cannot choose approved status or override unit prices by adding form fields. Quantities use integer grams and money integer UGX. Create and approval audit events commit atomically with the corresponding record change. The audit table is application evidence, not a cryptographically tamper-proof log. Delivery dates use Kampala's UTC+03 offset.

## What remains outside this phase

Staff provisioning, password changes, user-role editing, corrections to existing delivery quantities/prices, pagination, and full incident-response tooling are not implemented. Admins can approve/reject deliveries and view accounts, not manage the full user lifecycle. There is no intentional vulnerable version, exploitation result, or supplied-artifact analysis. Windows ARM64 Docker execution remains unverified here.

## Validation

Automated integration tests use temporary synthetic SQLite databases, real HTTP requests, cookies and CSRF tokens. The end-to-end test creates a delivery as a clerk, reads it as its farmer, blocks another farmer, approves as admin, verifies the before/after audit event, rejects a stale decision and confirms the farmer sees approval. Other tests cover invalid inputs, price/status tampering, missing/invalid CSRF, role restrictions, session expiry/rotation/logout, login rate limits, escaped output and scoped search.

Browser automation was attempted twice but timed out in this session. The newly added portal screens have HTTP validation but require visual browser review. The previous photo overview had desktop/mobile visual verification. Do not describe these local development tests as Windows exam-lab evidence.

Final verification: 16 tests passed (26.180 seconds). Compose configuration validated. An additional HTTP check of the running localhost server signed in as the existing synthetic demo admin, received 200 responses from workspace/deliveries/farmers/audit/accounts and successfully signed out. No real credentials or data were used.

## Registration update

The sign-in page now links to `/register`. The form creates a farmer user and linked profile atomically and rotates the anonymous session into an authenticated one. Role fields sent by a client cannot elevate access. Invalid input, CSRF failures, mismatched/short passwords, duplicate usernames and rate limits are checked. The account guidance and LOCAL DEMO labels were removed from the visible interface. New farmer self-registration is now implemented; staff provisioning and role editing remain separate work. Browser navigation reached the registration page, but native page capture did not render the content reliably; HTTP and integration tests verify its behaviour.

26 November 2026: corrected the test PostgreSQL URI encoding and an ambiguous PostgreSQL upsert column reference. A confirmed real PostgreSQL 16 run passed all 23 tests in 43.290 seconds. Earlier apparent PostgreSQL test passes were misrouted SQLite runs and must not be cited as PostgreSQL verification.
