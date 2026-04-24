import sqlite3
import json
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
from typing import Any

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

                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,           -- same user_id string
                    app_id TEXT NOT NULL REFERENCES ordo_apps(id),
                    username TEXT NOT NULL,
                    contact_email TEXT,
                    contact_phone TEXT,
                    sms_phone TEXT,
                    ordo_number TEXT,
                    timezone TEXT DEFAULT 'America/New_York',
                    created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(app_id, id)
                );

                CREATE TABLE IF NOT EXISTS calendar_integrations (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    app_id TEXT NOT NULL REFERENCES ordo_apps(id),
                    user_id TEXT NOT NULL,
                    provider TEXT NOT NULL DEFAULT 'google',
                    email TEXT NOT NULL,
                    label TEXT,
                    color TEXT DEFAULT '#22d3ee',
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
                    UNIQUE(app_id, user_id, provider, email)
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

                CREATE TABLE IF NOT EXISTS calendar_watch_channels (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    app_id TEXT NOT NULL REFERENCES ordo_apps(id),
                    user_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    email TEXT NOT NULL,
                    channel_id TEXT,
                    resource_id TEXT,
                    expiration TEXT,
                    sync_token TEXT,
                    UNIQUE(app_id, user_id, provider, email)
                );

                CREATE TABLE IF NOT EXISTS collision_notifications (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    app_id TEXT NOT NULL REFERENCES ordo_apps(id),
                    user_id TEXT NOT NULL,
                    email TEXT,
                    new_event_id TEXT,
                    new_event_summary TEXT,
                    new_event_start TEXT,
                    new_event_end TEXT,
                    colliding_events TEXT,
                    status TEXT DEFAULT 'pending',
                    resolution TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS working_hours (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL REFERENCES users(id),
                    day_of_week INTEGER NOT NULL, -- 0=Mon, 6=Sun
                    start_time TEXT NOT NULL,     -- 'HH:MM'
                    end_time TEXT NOT NULL,       -- 'HH:MM'
                    enabled BOOLEAN DEFAULT TRUE,
                    UNIQUE(user_id, day_of_week)
                );

                CREATE TABLE IF NOT EXISTS event_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL REFERENCES users(id),
                    slug TEXT NOT NULL,
                    name TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    buffer_before INTEGER DEFAULT 0,
                    buffer_after INTEGER DEFAULT 15,
                    description TEXT,
                    location TEXT,
                    booking_window_days INTEGER DEFAULT 30,
                    active BOOLEAN DEFAULT TRUE,
                    created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(user_id, slug)
                );

                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type_id INTEGER REFERENCES event_types(id),
                    user_id TEXT NOT NULL REFERENCES users(id),
                    calendar_event_id TEXT,
                    attendee_name TEXT NOT NULL,
                    attendee_email TEXT NOT NULL,
                    attendee_phone TEXT,
                    sms_consent BOOLEAN DEFAULT FALSE,
                    start_time TEXT NOT NULL,      -- UTC ISO8601
                    end_time TEXT NOT NULL,        -- UTC ISO8601
                    timezone TEXT NOT NULL,        -- attendee's timezone
                    status TEXT DEFAULT 'confirmed',
                    notes TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS scheduled_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    booking_id INTEGER NOT NULL REFERENCES bookings(id),
                    user_id TEXT NOT NULL REFERENCES users(id),
                    recipient TEXT NOT NULL,       -- 'user' | 'attendee'
                    phone TEXT NOT NULL,
                    email TEXT DEFAULT NULL,
                    message_type TEXT NOT NULL,    -- 'confirmation' | 'reminder_24h' | 'reminder_1h' | 'no_show'
                    body TEXT NOT NULL,
                    send_at TEXT NOT NULL,         -- UTC ISO8601
                    sent_at TEXT,
                    status TEXT DEFAULT 'pending', -- pending | sent | failed | cancelled
                    twilio_sid TEXT,
                    retry_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_watch_channels_app_user
                    ON calendar_watch_channels(app_id, user_id, provider);

                CREATE INDEX IF NOT EXISTS idx_collision_notifications_user
                    ON collision_notifications(app_id, user_id, status);

                CREATE INDEX IF NOT EXISTS idx_integrations_app_user
                    ON calendar_integrations(app_id, user_id, provider);

                CREATE INDEX IF NOT EXISTS idx_integrations_app_user_email
                    ON calendar_integrations(app_id, user_id, provider, email);

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

    def upsert_integration(self, app_id: str, user_id: str, provider: str,
                           email: str, **kwargs) -> dict:
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
                f"""INSERT INTO calendar_integrations (app_id, user_id, provider, email, {fields})
                    VALUES (?, ?, ?, ?, {placeholders})
                    ON CONFLICT(app_id, user_id, provider, email) DO UPDATE SET {updates}""",
                (app_id, user_id, provider, email, *kwargs.values())
            )
            row = conn.execute(
                """SELECT * FROM calendar_integrations
                   WHERE app_id = ? AND user_id = ? AND provider = ? AND email = ?""",
                (app_id, user_id, provider, email)
            ).fetchone()
            return self._deserialize_integration(dict(row))

    def get_integration(self, app_id: str, user_id: str, provider: str = "google",
                        email: str = None) -> dict | None:
        """Get a single integration. If email is provided, fetch that specific account."""
        with self._conn() as conn:
            if email:
                row = conn.execute(
                    """SELECT * FROM calendar_integrations
                       WHERE app_id = ? AND user_id = ? AND provider = ? AND email = ?""",
                    (app_id, user_id, provider, email)
                ).fetchone()
            else:
                # Return first match if no email specified
                row = conn.execute(
                    """SELECT * FROM calendar_integrations
                       WHERE app_id = ? AND user_id = ? AND provider = ?
                       ORDER BY created_at ASC LIMIT 1""",
                    (app_id, user_id, provider)
                ).fetchone()
            return self._deserialize_integration(dict(row)) if row else None

    def get_integrations_by_provider(self, app_id: str, user_id: str,
                                     provider: str) -> list[dict]:
        """Get all accounts for a specific provider."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM calendar_integrations
                   WHERE app_id = ? AND user_id = ? AND provider = ?
                   ORDER BY created_at ASC""",
                (app_id, user_id, provider)
            ).fetchall()
            return [self._deserialize_integration(dict(r)) for r in rows]

    def get_integrations(self, app_id: str, user_id: str) -> list[dict]:
        """Get all integrations across all providers for a user."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM calendar_integrations
                   WHERE app_id = ? AND user_id = ?
                   ORDER BY provider, created_at ASC""",
                (app_id, user_id)
            ).fetchall()
            return [self._deserialize_integration(dict(r)) for r in rows]

    def delete_integration(self, app_id: str, user_id: str, provider: str,
                           email: str) -> bool:
        """Delete a specific calendar account by email."""
        with self._conn() as conn:
            cur = conn.execute(
                """DELETE FROM calendar_integrations
                   WHERE app_id = ? AND user_id = ? AND provider = ? AND email = ?""",
                (app_id, user_id, provider, email)
            )
            return cur.rowcount > 0

    def update_integration_config(self, app_id: str, user_id: str,
                                  provider: str, email: str, **kwargs) -> dict | None:
        if "available_days" in kwargs and isinstance(kwargs["available_days"], list):
            kwargs["available_days"] = json.dumps(kwargs["available_days"])
        kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        with self._conn() as conn:
            conn.execute(
                f"""UPDATE calendar_integrations SET {sets}
                    WHERE app_id = ? AND user_id = ? AND provider = ? AND email = ?""",
                (*kwargs.values(), app_id, user_id, provider, email)
            )
            row = conn.execute(
                """SELECT * FROM calendar_integrations
                   WHERE app_id = ? AND user_id = ? AND provider = ? AND email = ?""",
                (app_id, user_id, provider, email)
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
            row = conn.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
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
                "SELECT * FROM event_provider_sync WHERE event_id = ?",
                (event_id,),
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
    # Watch Channels
    # -------------------------

    def upsert_watch_channel(self, app_id: str, user_id: str, provider: str, email: str, **kwargs) -> dict:
        kwargs_copy = {**kwargs}
        fields = ", ".join(kwargs_copy.keys())
        placeholders = ", ".join("?" * len(kwargs_copy))
        updates = ", ".join(f"{k} = excluded.{k}" for k in kwargs_copy)
        with self._conn() as conn:
            conn.execute(
                f"""INSERT INTO calendar_watch_channels (app_id, user_id, provider, email, {fields})
                    VALUES (?, ?, ?, ?, {placeholders})
                    ON CONFLICT(app_id, user_id, provider, email) DO UPDATE SET {updates}""",
                (app_id, user_id, provider, email, *kwargs_copy.values())
            )
            row = conn.execute(
                """SELECT * FROM calendar_watch_channels
                   WHERE app_id = ? AND user_id = ? AND provider = ? AND email = ?""",
                (app_id, user_id, provider, email)
            ).fetchone()
            return dict(row)

    def get_watch_channel(self, app_id: str, user_id: str, provider: str, email: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                """SELECT * FROM calendar_watch_channels
                   WHERE app_id = ? AND user_id = ? AND provider = ? AND email = ?""",
                (app_id, user_id, provider, email)
            ).fetchone()
            return dict(row) if row else None

    def get_watch_channel_by_channel_id(self, channel_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM calendar_watch_channels WHERE channel_id = ?",
                (channel_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_expiring_watch_channels(self, before: str) -> list[dict]:
        """Get all channels expiring before a given ISO timestamp."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM calendar_watch_channels WHERE expiration < ?",
                (before,)
            ).fetchall()
            return [dict(r) for r in rows]

    def update_watch_channel_sync_token(self, app_id: str, user_id: str,
                                        provider: str, email: str, sync_token: str):
        with self._conn() as conn:
            conn.execute(
                """UPDATE calendar_watch_channels SET sync_token = ?
                   WHERE app_id = ? AND user_id = ? AND provider = ? AND email = ?""",
                (sync_token, app_id, user_id, provider, email)
            )

    # -------------------------
    # Collision Notifications
    # -------------------------

    def create_collision_notification(self, app_id: str, user_id: str,
                                      email: str,
                                      new_event_id: str, new_event_summary: str,
                                      new_event_start: str, new_event_end: str,
                                      colliding_events: list) -> dict:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO collision_notifications
                   (app_id, user_id, email, new_event_id, new_event_summary,
                    new_event_start, new_event_end, colliding_events)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (app_id, user_id, email, new_event_id, new_event_summary,
                 new_event_start, new_event_end, json.dumps(colliding_events))
            )
            row = conn.execute(
                """SELECT * FROM collision_notifications
                   WHERE app_id = ? AND user_id = ? AND new_event_id = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (app_id, user_id, new_event_id)
            ).fetchone()
            return self._deserialize_collision(dict(row))

    def get_pending_collisions(self, app_id: str, user_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM collision_notifications
                   WHERE app_id = ? AND user_id = ? AND status = 'pending'
                   ORDER BY created_at DESC""",
                (app_id, user_id)
            ).fetchall()
            return [self._deserialize_collision(dict(r)) for r in rows]

    def resolve_collision(self, notification_id: str, resolution: str) -> dict | None:
        """resolution: 'keep_new' | 'keep_old' | 'manual'"""
        with self._conn() as conn:
            conn.execute(
                """UPDATE collision_notifications
                   SET status = 'resolved', resolution = ?
                   WHERE id = ?""",
                (resolution, notification_id)
            )
            row = conn.execute(
                "SELECT * FROM collision_notifications WHERE id = ?",
                (notification_id,)
            ).fetchone()
            return self._deserialize_collision(dict(row)) if row else None

    def resolve_expired_collisions(self, user_id: str = None) -> int:
        """Mark pending collisions as resolved if the new event's start time has passed."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            if user_id:
                cur = conn.execute(
                    """UPDATE collision_notifications
                       SET status = 'resolved', resolution = 'expired'
                       WHERE status = 'pending' AND user_id = ? AND new_event_start < ?""",
                    (user_id, now)
                )
            else:
                cur = conn.execute(
                    """UPDATE collision_notifications
                       SET status = 'resolved', resolution = 'expired'
                       WHERE status = 'pending' AND new_event_start < ?""",
                    (now,)
                )
            return cur.rowcount

    def _deserialize_collision(self, row: dict) -> dict:
        if row.get("colliding_events") and isinstance(row["colliding_events"], str):
            try:
                row["colliding_events"] = json.loads(row["colliding_events"])
            except (json.JSONDecodeError, TypeError):
                pass
        return row

    def get_user_by_username(self, username: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict[Any, Any](row) if row else None

    def get_user(self, user_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_event_type(self, user_id: str, slug: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM event_types WHERE user_id = ? AND slug = ?",
                (user_id, slug)
            ).fetchone()
            return dict(row) if row else None

    def get_working_hours(self, user_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM working_hours WHERE user_id = ? AND enabled = 1 ORDER BY day_of_week",
                (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def create_booking(self, **kwargs) -> dict:
        fields = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" * len(kwargs))
        with self._conn() as conn:
            conn.execute(
                f"INSERT INTO bookings ({fields}) VALUES ({placeholders})",
                tuple(kwargs.values())
            )
            row = conn.execute(
                "SELECT * FROM bookings WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)

    def create_scheduled_message(self, **kwargs) -> dict:
        fields = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" * len(kwargs))
        with self._conn() as conn:
            conn.execute(
                f"INSERT INTO scheduled_messages ({fields}) VALUES ({placeholders})",
                tuple(kwargs.values())
            )
            row = conn.execute(
                "SELECT * FROM scheduled_messages WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)

    def get_pending_messages(self, before: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT sm.*, u.sms_phone, u.ordo_number
                   FROM scheduled_messages sm
                   JOIN users u ON u.id = sm.user_id
                   WHERE sm.status = 'pending'
                   AND sm.send_at <= ?
                   ORDER BY sm.send_at ASC""",
                (before,)
            ).fetchall()
            return [dict(r) for r in rows]

    def update_message_status(self, message_id: int, status: str,
                              sent_at: str = None, twilio_sid: str = None,
                              retry_count: int = None) -> None:
        updates = {"status": status}
        if sent_at:
            updates["sent_at"] = sent_at
        if twilio_sid:
            updates["twilio_sid"] = twilio_sid
        if retry_count is not None:
            updates["retry_count"] = retry_count
        sets = ", ".join(f"{k} = ?" for k in updates)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE scheduled_messages SET {sets} WHERE id = ?",
                (*updates.values(), message_id)
            )

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
                DROP TABLE IF EXISTS calendar_watch_channels;
                DROP TABLE IF EXISTS collision_notifications;
                DROP TABLE IF EXISTS ordo_apps;
            """)
        self._init_db()

    def seed(self):
        """Insert test fixtures. Dev only."""
        app = self.create_app(
            name="Ordo Dev",
            api_key="ordo_sk_7f3a91c2e84b56d0f2a7139e4c8b05d1",
            redirect_uri="http://localhost:3000/callback",
            allowed_providers=["google", "microsoft"],
        )
        return app
