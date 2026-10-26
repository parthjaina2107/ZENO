"""Bounded, persistent event inbox. Notifications are data, never executable tasks."""
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class EventStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, source TEXT, title TEXT, body TEXT, priority INTEGER, created REAL, announced INTEGER)')
            db.execute('CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def contains(self, event_id):
        with self.connect() as db:
            return db.execute('SELECT 1 FROM events WHERE id=?', (event_id,)).fetchone() is not None

    def get(self, key, default=None):
        with self.connect() as db:
            row = db.execute('SELECT value FROM state WHERE key=?', (key,)).fetchone()
        return json.loads(row['value']) if row else default

    def set(self, key, value):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO state VALUES (?,?)', (key, json.dumps(value)))

    def add(self, event, announced=False):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?)', (
                event['id'], event['source'][:120], event['title'][:300], event.get('body', '')[:1500],
                event.get('priority', 0), event.get('created', time.time()), int(announced)))

    def events(self, pending=False, limit=100):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                'SELECT * FROM events WHERE created>? ' + ('AND announced=0 ' if pending else '')
                + 'ORDER BY priority DESC, created DESC LIMIT ?', (time.time() - 86400, limit))]

    def acknowledge(self, ids):
        with self.connect() as db:
            db.executemany('UPDATE events SET announced=1 WHERE id=?', [(value,) for value in ids])

    def prune(self):
        with self.connect() as db:
            db.execute('DELETE FROM events WHERE created<?', (time.time() - 7 * 86400,))
            db.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY created DESC LIMIT 1000)')
