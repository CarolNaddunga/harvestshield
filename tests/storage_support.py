"""Optional real PostgreSQL backend for the same integration suite."""
import os
import uuid
from pathlib import Path

def test_database(test):
    url=os.environ.get('HARVESTSHIELD_TEST_POSTGRES')
    if not url:
        return Path(test.temp.name)/'test.sqlite3'
    import psycopg
    from psycopg import sql
    from urllib.parse import urlencode, quote
    schema='hs_test_'+uuid.uuid4().hex
    with psycopg.connect(url,autocommit=True) as db:
        db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    def cleanup():
        with psycopg.connect(url,autocommit=True) as db:
            db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
    test.addCleanup(cleanup)
    return url+('&' if '?' in url else '?')+urlencode({'options':'-c search_path='+schema},quote_via=quote)
