import sqlite3
from pathlib import Path
from contextlib import contextmanager


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS nonces(nonce TEXT PRIMARY KEY,wallet TEXT,agent TEXT,deadline INTEGER,used INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,wallet TEXT,agent TEXT,deadline INTEGER);
            CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,agent TEXT,wallet TEXT,seed TEXT,class INTEGER,
              fingerprint TEXT UNIQUE,started INTEGER,state TEXT,result TEXT,auth TEXT);
            CREATE TABLE IF NOT EXISTS limits(bucket TEXT,at INTEGER);
            CREATE INDEX IF NOT EXISTS limits_bucket ON limits(bucket,at);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except Exception:
                db.rollback()
                raise
            else:
                db.commit()
