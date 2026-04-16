import sqlite3, json, logging, hashlib
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "ordo_dev.db"


class OrdoDB:
    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS ordo_apps (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    name TEXT NOT NULL,
                    api_key_hash TEXT NOT NULL UNIQUE,
                    redirect_uri TEXT,
                    allowed_providers TEXT DEFAULT '["google"]',
                    webhook_url TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS calendar_integrations (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    app_id TEXT NOT NULL REFERENCES ordo_apps(id),
                    user_id TEXT NOT NULL,
                    provider TEXT NOT NULL DEFAULT 'google',
                    email TEXT,
                    access_token TEXT,
                    refresh_token TEXT,
                    token_expiry TEXT,
                    scopes TEXT,
                    calendar_id TEXT,
                    redirect_uri TEXT,
                    lookahead_weeks INTEGER DEFAULT 2,
                    timezone TEXT DEFAULT 'America/New_York',
                    available_days TEXT,
                    available_start TEXT,
                    available_end TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(app_id, user_id, provider)
                );

                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    app_id TEXT NOT NULL REFERENCES ordo_apps(id),
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    timezone TEXT DEFAULT 'America/New_York',
                    location TEXT,
                    attendees TEXT,
                    meet_link TEXT,
                    status TEXT DEFAULT 'confirmed',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS event_provider_sync (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    provider_event_id TEXT NOT NULL,
                    synced_at TEXT,
                    sync_status TEXT DEFAULT 'pending',
                    UNIQUE(event_id, provider)
                );

                CREATE INDEX IF NOT EXISTS idx_integrations_app_user
                    ON calendar_integrations(app_id, user_id, provider);

                CREATE INDEX IF NOT EXISTS idx_events_app_user
                    ON events(app_id, user_id);

                CREATE INDEX IF NOT EXISTS idx_events_start_time
                    ON events(start_time);

                CREATE INDEX IF NOT EXISTS idx_event_sync_event_id
                    ON event_provider_sync(event_id);

                CREATE INDEX IF NOT EXISTS idx_event_sync_provider_event_id
                    ON event_provider_sync(provider, provider_event_id);
            """)

    # -------------------------
    # Apps
    # -------------------------

    def create_app(self, name: str, api_key: str, redirect_uri: str = None,
                   allowed_providers: list = None, webhook_url: str = None) -> dict:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        allowed_providers = json.dumps(allowed_providers or ["google"])
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO ordo_apps (name, api_key_hash, redirect_uri, allowed_providers, webhook_url)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, key_hash, redirect_uri, allowed_providers, webhook_url)
            )
            row = conn.execute(
                "SELECT * FROM ordo_apps WHERE api_key_hash = ?", (key_hash,)
            ).fetchone()
            return self._deserialize_app(dict(row))

    def get_app_by_key(self, api_key: str) -> dict | None:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM ordo_apps WHERE api_key_hash = ?", (key_hash,)
            ).fetchone()
            return self._deserialize_app(dict(row)) if row else None

    def get_app_by_id(self, app_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM ordo_apps WHERE id = ?", (app_id,)
            ).fetchone()
            return self._deserialize_app(dict(row)) if row else None

    def _deserialize_app(self, row: dict) -> dict:
        if row.get("allowed_providers") and isinstance(row["allowed_providers"], str):
            try:
                row["allowed_providers"] = json.loads(row["allowed_providers"])
            except (json.JSONDecodeError, TypeError):
                pass
        return row

    # -------------------------
    # Calendar Integrations
    # -------------------------

    def upsert_integration(self, app_id: str, user_id: str, provider: str, **kwargs) -> dict:
        kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
        if "scopes" in kwargs and isinstance(kwargs["scopes"], list):
            kwargs["scopes"] = json.dumps(kwargs["scopes"])
        if "available_days" in kwargs and isinstance(kwargs["available_days"], list):
            kwargs["available_days"] = json.dumps(kwargs["available_days"])

        fields = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" * len(kwargs))
        updates = ", ".join(f"{k} = excluded.{k}" for k in kwargs)

        with self._conn() as conn:
            conn.execute(
                f"""INSERT INTO calendar_integrations (app_id, user_id, provider, {fields})
                    VALUES (?, ?, ?, {placeholders})
                    ON CONFLICT(app_id, user_id, provider) DO UPDATE SET {updates}""",
                (app_id, user_id, provider, *kwargs.values())
            )
            row = conn.execute(
                """SELECT * FROM calendar_integrations
                   WHERE app_id = ? AND user_id = ? AND provider = ?""",
                (app_id, user_id, provider)
            ).fetchone()
            return self._deserialize_integration(dict(row))

    def get_integration(self, app_id: str, user_id: str, provider: str = "google") -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                """SELECT * FROM calendar_integrations
                   WHERE app_id = ? AND user_id = ? AND provider = ?""",
                (app_id, user_id, provider)
            ).fetchone()
            return self._deserialize_integration(dict(row)) if row else None

    def get_integrations(self, app_id: str, user_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM calendar_integrations WHERE app_id = ? AND user_id = ?",
                (app_id, user_id)
            ).fetchall()
            return [self._deserialize_integration(dict(r)) for r in rows]

    def delete_integration(self, app_id: str, user_id: str, provider: str = "google") -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                """DELETE FROM calendar_integrations
                   WHERE app_id = ? AND user_id = ? AND provider = ?""",
                (app_id, user_id, provider)
            )
            return cur.rowcount > 0

    def update_integration_config(self, app_id: str, user_id: str,
                                   provider: str = "google", **kwargs) -> dict | None:
        if "available_days" in kwargs and isinstance(kwargs["available_days"], list):
            kwargs["available_days"] = json.dumps(kwargs["available_days"])
        kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        with self._conn() as conn:
            conn.execute(
                f"""UPDATE calendar_integrations SET {sets}
                    WHERE app_id = ? AND user_id = ? AND provider = ?""",
                (*kwargs.values(), app_id, user_id, provider)
            )
            row = conn.execute(
                """SELECT * FROM calendar_integrations
                   WHERE app_id = ? AND user_id = ? AND provider = ?""",
                (app_id, user_id, provider)
            ).fetchone()
            return self._deserialize_integration(dict(row)) if row else None

    def _deserialize_integration(self, row: dict) -> dict:
        for field in ("scopes", "available_days"):
            if row.get(field) and isinstance(row[field], str):
                try:
                    row[field] = json.loads(row[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return row

    # -------------------------
    # Events
    # -------------------------

    def create_event(self, app_id: str, user_id: str, title: str,
                     start_time: str, end_time: str, **kwargs) -> dict:
        if "attendees" in kwargs and isinstance(kwargs["attendees"], list):
            kwargs["attendees"] = json.dumps(kwargs["attendees"])
        kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
        fields = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" * len(kwargs))
        with self._conn() as conn:
            conn.execute(
                f"""INSERT INTO events (app_id, user_id, title, start_time, end_time, {fields})
                    VALUES (?, ?, ?, ?, ?, {placeholders})""",
                (app_id, user_id, title, start_time, end_time, *kwargs.values())
            )
            row = conn.execute(
                "SELECT * FROM events WHERE app_id = ? AND user_id = ? AND title = ? AND start_time = ?",
                (app_id, user_id, title, start_time)
            ).fetchone()
            return self._deserialize_event(dict(row))

    def get_event(self, event_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            ).fetchone()
            return self._deserialize_event(dict(row)) if row else None

    def get_events(self, app_id: str, user_id: str,
                   start: str = None, end: str = None) -> list[dict]:
        query = "SELECT * FROM events WHERE app_id = ? AND user_id = ? AND status != 'cancelled'"
        params = [app_id, user_id]
        if start:
            query += " AND start_time >= ?"
            params.append(start)
        if end:
            query += " AND start_time <= ?"
            params.append(end)
        query += " ORDER BY start_time ASC"
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._deserialize_event(dict(r)) for r in rows]

    def update_event(self, event_id: str, **kwargs) -> dict | None:
        if "attendees" in kwargs and isinstance(kwargs["attendees"], list):
            kwargs["attendees"] = json.dumps(kwargs["attendees"])
        kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE events SET {sets} WHERE id = ?",
                (*kwargs.values(), event_id)
            )
            row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
            return self._deserialize_event(dict(row)) if row else None

    def delete_event(self, event_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
            return cur.rowcount > 0

    def _deserialize_event(self, row: dict) -> dict:
        if row.get("attendees") and isinstance(row["attendees"], str):
            try:
                row["attendees"] = json.loads(row["attendees"])
            except (json.JSONDecodeError, TypeError):
                pass
        return row

    # -------------------------
    # Event Provider Sync
    # -------------------------

    def upsert_event_sync(self, event_id: str, provider: str,
                          provider_event_id: str, sync_status: str = "synced") -> dict:
        synced_at = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO event_provider_sync (event_id, provider, provider_event_id, synced_at, sync_status)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(event_id, provider) DO UPDATE SET
                       provider_event_id = excluded.provider_event_id,
                       synced_at = excluded.synced_at,
                       sync_status = excluded.sync_status""",
                (event_id, provider, provider_event_id, synced_at, sync_status)
            )
            row = conn.execute(
                "SELECT * FROM event_provider_sync WHERE event_id = ? AND provider = ?",
                (event_id, provider)
            ).fetchone()
            return dict(row)

    def get_event_syncs(self, event_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM event_provider_sync WHERE event_id = ?", (event_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_event_by_provider_id(self, provider: str, provider_event_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                """SELECT e.* FROM events e
                   JOIN event_provider_sync s ON s.event_id = e.id
                   WHERE s.provider = ? AND s.provider_event_id = ?""",
                (provider, provider_event_id)
            ).fetchone()
            return self._deserialize_event(dict(row)) if row else None

    def delete_event_sync(self, event_id: str, provider: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM event_provider_sync WHERE event_id = ? AND provider = ?",
                (event_id, provider)
            )
            return cur.rowcount > 0

    # -------------------------
    # Dev helpers
    # -------------------------

    def reset(self):
        """Drop and recreate all tables. Dev only."""
        with self._conn() as conn:
            conn.executescript("""
                DROP TABLE IF EXISTS event_provider_sync;
                DROP TABLE IF EXISTS events;
                DROP TABLE IF EXISTS calendar_integrations;
                DROP TABLE IF EXISTS ordo_apps;
            """)
        self._init_db()

    def seed(self):
        """Insert test fixtures. Dev only."""
        app = self.create_app(
            name="Ordo Dev",
            api_key="ordo_sk_7f3a91c2e84b56d0f2a7139e4c8b05d1",
            redirect_uri="http://localhost:3000/callback",
            allowed_providers=["google"],
            # webhook_url="http://localhost:8000/webhooks/ordo",
        )
