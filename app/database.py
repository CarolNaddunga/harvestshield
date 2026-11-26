"""SQLite schema, repeatable synthetic seed and aggregate overview."""
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
import sqlite3
from .auth import hash_password
from .models import CROPS, calculate_amount

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
 display_name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('farmer','clerk','admin')),
 password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS farmers (
 id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE NOT NULL REFERENCES users(id),
 member_code TEXT UNIQUE NOT NULL, district TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deliveries (
 id INTEGER PRIMARY KEY, farmer_id INTEGER NOT NULL REFERENCES farmers(id),
 crop TEXT NOT NULL CHECK(crop IN ('maize','beans','coffee')),
 quantity_grams INTEGER NOT NULL CHECK(quantity_grams > 0),
 unit_price_ugx INTEGER NOT NULL CHECK(unit_price_ugx > 0),
 amount_ugx INTEGER NOT NULL CHECK(amount_ugx > 0),
 delivered_at TEXT NOT NULL, recorded_by INTEGER NOT NULL REFERENCES users(id),
 status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected')),
 CHECK(amount_ugx * 1000 = quantity_grams * unit_price_ugx)
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id),
 csrf TEXT NOT NULL, expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts (
 identity TEXT PRIMARY KEY, attempts INTEGER NOT NULL, started_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_events (
 id INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL, actor_id INTEGER REFERENCES users(id),
 action TEXT NOT NULL, record_id INTEGER, details TEXT NOT NULL
);
"""


@contextmanager
def connect(path):
    if str(path).startswith(('postgres://','postgresql://')):
        from .postgres import Database
        db = Database(str(path))
    else:
        db = sqlite3.connect(path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize(path):
    postgres = str(path).startswith(('postgres://','postgresql://'))
    if not postgres:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        schema = SCHEMA.replace('id INTEGER PRIMARY KEY','id SERIAL PRIMARY KEY') if postgres else SCHEMA
        # Gram × price constraint can exceed 32-bit integer ranges.
        if postgres:
            for name in ('quantity_grams','unit_price_ugx','amount_ugx'):
                schema = schema.replace(name+' INTEGER',name+' BIGINT')
        db.executescript(schema)


def seed(path, demo_password):
    """Seed only an empty database; never overwrite existing records."""
    initialize(path)
    with connect(path) as db:
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return False
        districts = ["Mukono", "Kayunga", "Buikwe", "Luwero", "Mpigi"]
        for i in range(1, 11):
            db.execute("INSERT INTO users VALUES (?, ?, ?, 'farmer', ?)",
                       (i, f"farmer{i:02}", f"Farmer {i:02}", hash_password(demo_password)))
            db.execute("INSERT INTO farmers VALUES (?, ?, ?, ?)",
                       (i, i, f"GF-{i:03}", districts[(i-1) % 5]))
        for i, username, name, role in [(11,"clerk01","Clerk 01","clerk"),
                                      (12,"clerk02","Clerk 02","clerk"),
                                      (13,"admin","Administrator","admin")]:
            db.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                       (i, username, name, role, hash_password(demo_password)))
        for i in range(1, 19):
            crop = list(CROPS)[(i-1) % 3]
            grams, price, amount = calculate_amount(50 + i * 10, CROPS[crop])
            db.execute("INSERT INTO deliveries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (i, (i-1) % 10 + 1, crop, grams, price, amount,
                        f"2026-11-{(i-1)%9+1:02}T09:00:00+03:00", 11 + i % 2,
                        ["pending","approved","approved"][(i-1) % 3]))
        db.execute("INSERT INTO audit_events (occurred_at, actor_id, action, details) "
                   "VALUES (?, NULL, 'demo.seed', ?)",
                   (datetime.now(timezone.utc).isoformat(), 'Created synthetic fixture: 13 users, 10 farmers, 18 deliveries.'))
        if str(path).startswith(('postgres://','postgresql://')):
            # Fixed internal identifiers, never user input.
            for table in ('users','farmers','deliveries'):
                db.execute(f"SELECT setval(pg_get_serial_sequence('{table}','id'), MAX(id)) FROM {table}")
    return True


def overview(path):
    with connect(path) as db:
        totals = dict(db.execute("""SELECT COUNT(*) AS deliveries,
            COALESCE(SUM(quantity_grams),0) AS quantity_grams,
            COALESCE(SUM(CASE WHEN status='approved' THEN amount_ugx ELSE 0 END),0) AS approved_ugx,
            COALESCE(SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END),0) AS pending
            FROM deliveries""").fetchone())
        totals['farmers'] = db.execute("SELECT COUNT(*) FROM farmers").fetchone()[0]
        crops = [dict(r) for r in db.execute("SELECT crop, SUM(quantity_grams) AS grams, COUNT(*) AS count FROM deliveries GROUP BY crop ORDER BY grams DESC")]
        return totals, crops
