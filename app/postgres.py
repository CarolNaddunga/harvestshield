"""PostgreSQL connection adapter for the app's fixed, parameterised SQL.

Local lab storage remains SQLite. This small adapter preserves the existing
row and insert-id contract while letting hosted records survive app restarts.
"""
import re
import sqlite3
import psycopg

class Row(dict):
    def __getitem__(self,key):
        if isinstance(key,int):
            return tuple(self.values())[key]
        return super().__getitem__(key)

def row_factory(cursor):
    names=[c.name for c in cursor.description] if cursor.description else []
    return lambda values: Row(zip(names,values))

class Cursor:
    def __init__(self,cursor,insert_id=False):
        self.cursor=cursor
        self.lastrowid=cursor.fetchone()['id'] if insert_id else None
    def fetchone(self): return self.cursor.fetchone()
    def fetchall(self): return self.cursor.fetchall()
    def __iter__(self): return iter(self.cursor)

class Database:
    def __init__(self,url):
        self.raw=psycopg.connect(url,row_factory=row_factory,connect_timeout=10)
    def execute(self,sql,parameters=()):
        # Only application-owned SQL reaches this adapter; values stay bound.
        # Application statements contain no literal question marks or percents.
        sql=sql.replace('%','%%').replace('?','%s') if parameters else sql
        inserted=bool(re.match(r'INSERT INTO (users|farmers|deliveries)\b',sql,re.I))
        if inserted: sql=sql.rstrip().rstrip(';')+' RETURNING id'
        try:
            cursor=self.raw.execute(sql,parameters or None)
            return Cursor(cursor,inserted)
        except psycopg.IntegrityError as exc:
            raise sqlite3.IntegrityError('Database constraint rejected this change.') from exc
    def executescript(self,sql):
        self.raw.execute(sql)
    def commit(self): self.raw.commit()
    def rollback(self): self.raw.rollback()
    def close(self): self.raw.close()
