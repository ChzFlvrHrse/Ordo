from __future__ import annotations
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

                CREATE INDEX IF NOT EXISTS idx_integrations_app_user
                    ON calendar_integrations(app_id, user_id, provider);
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
        """All providers for a given user within an app."""
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
    # Dev helpers
    # -------------------------

    def reset(self):
        """Drop and recreate all tables. Dev only."""
        with self._conn() as conn:
            conn.executescript("""
                DROP TABLE IF EXISTS calendar_integrations;
                DROP TABLE IF EXISTS ordo_apps;
            """)
        self._init_db()

    def seed(
        self,
        name: str = "Ordo Dev",
        api_key: str = "ordo_sk_7f3a91c2e84b56d0f2a7139e4c8b05d1",
        redirect_uri: str = "http://localhost:5000/callback",
    ):
        """Insert test fixtures. Dev only."""
        app = self.create_app(
            name=name,
            api_key=api_key,
            redirect_uri=redirect_uri,
            allowed_providers=["google"],
        )
        return app
