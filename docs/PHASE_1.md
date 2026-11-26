# Foundation design and review

## Boundary

Local browser → localhost port 8080 → aiohttp application → local SQLite database. Static files live in a separate, fixed directory; the database and Python source are never static content. Nothing calls a cloud service. The public development page shows synthetic totals only. Private data endpoints and mutating HTTP actions do not exist in this phase.

SQLite uses foreign keys and role/crop/status/positive-amount constraints. Delivery amounts must match the stored quantity and price. Seed records use fixed November 2026 dates and fake names. The seed audit event has the actual UTC insertion timestamp and is not presented as delivery-change evidence.

The project deliberately has no unused permissions/audit abstractions. Those modules will be introduced alongside the workflows they protect in Phase 2. Passwords are salted and hashed, but authentication and sessions are not yet implemented.

## Review checkpoint

1. Run the README setup on the Windows ARM64 laptop.
2. Confirm the fixture totals and `/health` result.
3. Run the test suite; save actual output and environment information separately.
4. Check the Docker image architecture and container restrictions on that machine.
5. Review the source and explain the request-to-database path.

## Next phase

Build login/logout, expiring server-side sessions, CSRF protection for state-changing requests, explicit server-side role/ownership checks, farmer/delivery pages, clerk entry validation, admin approvals and timestamped audit events. Verify authorised and denied user journeys before advancing. No intentional weakness is enabled by this foundation.

## Exam limitations

This phase does not establish full lab isolation, demonstrate the CVE, supply three vulnerability discoveries, implement an incident response or analyse the missing instructor artifact. Container configuration is not a malware containment approval. The Windows environment information in the supplied guide is reported context, not measurements taken in this workspace.

## Development verification (21 November 2026)

Executed on the current macOS Apple silicon host with Python 3.13 and aiohttp 3.14.5, not on the exam Windows laptop. The nine-test unittest suite passed. Docker Compose configuration validation passed. A real local HTTP request to `/health` returned status `ok`. Docker engine access was denied in this session, so image build, Python 3.11 container execution and Windows ARM64 behaviour remain unverified. Browser visual verification was unavailable due to preview-tool/download failures. This is development validation, not exam vulnerability evidence.

## Photography update verification

The later photo UI update supersedes the earlier visual-verification limitation: the running app was visually checked at desktop width 1440 and mobile width 390. All five images loaded, neither viewport had horizontal overflow, and the expandable attribution section opened correctly. Nine existing foundation tests passed again. SQLite aggregates and backend workflows were unchanged. Docker/Windows ARM execution still requires validation on the exam machine.
