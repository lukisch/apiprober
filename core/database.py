"""
ApiProber.core.database -- SQLite CRUD
========================================
5 Tabellen: services, endpoints, responses, parameters, probe_runs
Pattern: BACH hub/apibook.py (_ensure_table + CRUD)
"""
import json
import sqlite3
from pathlib import Path
from datetime import datetime


class Database:
    """SQLite-Datenbank fuer API-Probing-Ergebnisse."""

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_tables(self):
        conn = self._connect()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    base_url TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_probed TEXT,
                    server_header TEXT DEFAULT '',
                    robots_txt TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS endpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_id INTEGER NOT NULL REFERENCES services(id),
                    path TEXT NOT NULL,
                    methods_json TEXT DEFAULT '[]',
                    status_codes_json TEXT DEFAULT '[]',
                    auth_required INTEGER DEFAULT 0,
                    auth_type_hint TEXT DEFAULT '',
                    content_types_json TEXT DEFAULT '[]',
                    discovered_by TEXT DEFAULT '',
                    UNIQUE(service_id, path)
                );

                CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint_id INTEGER NOT NULL REFERENCES endpoints(id),
                    method TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    headers_json TEXT DEFAULT '{}',
                    body_schema_json TEXT DEFAULT '{}',
                    body_sample TEXT DEFAULT '',
                    content_type TEXT DEFAULT '',
                    elapsed_ms INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS parameters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint_id INTEGER NOT NULL REFERENCES endpoints(id),
                    name TEXT NOT NULL,
                    param_type TEXT DEFAULT 'string',
                    location TEXT DEFAULT 'query',
                    required INTEGER DEFAULT 0,
                    example_value TEXT DEFAULT '',
                    UNIQUE(endpoint_id, name, location)
                );

                CREATE TABLE IF NOT EXISTS probe_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_id INTEGER NOT NULL REFERENCES services(id),
                    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    finished_at TEXT,
                    status TEXT DEFAULT 'running',
                    config_json TEXT DEFAULT '{}',
                    total_requests INTEGER DEFAULT 0,
                    endpoints_found INTEGER DEFAULT 0,
                    progress_json TEXT DEFAULT '{}'
                );
            """)
            conn.commit()
        finally:
            conn.close()

    # ── Services ──────────────────────────────────────────────────────────

    def upsert_service(self, name, base_url, description="", server_header="",
                       robots_txt="", metadata=None):
        """Service anlegen oder aktualisieren. Gibt service_id zurueck."""
        now = datetime.utcnow().isoformat()
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        conn = self._connect()
        try:
            conn.execute("""
                INSERT INTO services (name, base_url, description, discovered_at,
                                      server_header, robots_txt, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    base_url = excluded.base_url,
                    description = CASE WHEN excluded.description != ''
                                  THEN excluded.description ELSE services.description END,
                    server_header = CASE WHEN excluded.server_header != ''
                                   THEN excluded.server_header ELSE services.server_header END,
                    robots_txt = CASE WHEN excluded.robots_txt != ''
                                 THEN excluded.robots_txt ELSE services.robots_txt END,
                    metadata_json = CASE WHEN excluded.metadata_json != '{}'
                                    THEN excluded.metadata_json ELSE services.metadata_json END
            """, (name, base_url, description, now, server_header, robots_txt, meta_json))
            conn.commit()
            row = conn.execute("SELECT id FROM services WHERE name = ?", (name,)).fetchone()
            return row["id"]
        finally:
            conn.close()

    def get_service(self, name):
        """Service nach Name suchen. Gibt dict oder None zurueck."""
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM services WHERE name = ?", (name,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_service_by_id(self, service_id):
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_services(self):
        """Alle Services als Liste von dicts."""
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM services ORDER BY name").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_service_last_probed(self, service_id):
        now = datetime.utcnow().isoformat()
        conn = self._connect()
        try:
            conn.execute("UPDATE services SET last_probed = ? WHERE id = ?", (now, service_id))
            conn.commit()
        finally:
            conn.close()

    # ── Endpoints ─────────────────────────────────────────────────────────

    def upsert_endpoint(self, service_id, path, methods=None, status_codes=None,
                        auth_required=False, auth_type_hint="", content_types=None,
                        discovered_by=""):
        """Endpoint anlegen oder aktualisieren. Gibt endpoint_id zurueck."""
        conn = self._connect()
        try:
            existing = conn.execute(
                "SELECT id, methods_json, status_codes_json, content_types_json "
                "FROM endpoints WHERE service_id = ? AND path = ?",
                (service_id, path)
            ).fetchone()

            if existing:
                # Merge: bestehende Listen erweitern
                old_methods = set(json.loads(existing["methods_json"]))
                old_codes = set(json.loads(existing["status_codes_json"]))
                old_types = set(json.loads(existing["content_types_json"]))
                if methods:
                    old_methods.update(methods)
                if status_codes:
                    old_codes.update(status_codes)
                if content_types:
                    old_types.update(content_types)

                conn.execute("""
                    UPDATE endpoints SET
                        methods_json = ?,
                        status_codes_json = ?,
                        content_types_json = ?,
                        auth_required = CASE WHEN ? THEN 1 ELSE auth_required END,
                        auth_type_hint = CASE WHEN ? != '' THEN ? ELSE auth_type_hint END
                    WHERE id = ?
                """, (
                    json.dumps(sorted(old_methods)),
                    json.dumps(sorted(old_codes)),
                    json.dumps(sorted(old_types)),
                    auth_required, auth_type_hint, auth_type_hint,
                    existing["id"]
                ))
                conn.commit()
                return existing["id"]
            else:
                cur = conn.execute("""
                    INSERT INTO endpoints (service_id, path, methods_json, status_codes_json,
                                           auth_required, auth_type_hint, content_types_json,
                                           discovered_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    service_id, path,
                    json.dumps(sorted(methods or [])),
                    json.dumps(sorted(status_codes or [])),
                    1 if auth_required else 0,
                    auth_type_hint,
                    json.dumps(sorted(content_types or [])),
                    discovered_by
                ))
                conn.commit()
                return cur.lastrowid
        finally:
            conn.close()

    def get_endpoints(self, service_id):
        """Alle Endpoints eines Services."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM endpoints WHERE service_id = ? ORDER BY path",
                (service_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_endpoint_paths(self, service_id):
        """Nur die Pfade eines Services (fuer schnellen Check)."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT path FROM endpoints WHERE service_id = ?",
                (service_id,)
            ).fetchall()
            return {r["path"] for r in rows}
        finally:
            conn.close()

    # ── Responses ─────────────────────────────────────────────────────────

    def add_response(self, endpoint_id, method, status_code, headers=None,
                     body_schema=None, body_sample="", content_type="", elapsed_ms=0):
        """Response-Datensatz speichern."""
        # body_sample auf 2KB beschraenken
        if len(body_sample) > 2048:
            body_sample = body_sample[:2048]
        conn = self._connect()
        try:
            conn.execute("""
                INSERT INTO responses (endpoint_id, method, status_code, headers_json,
                                       body_schema_json, body_sample, content_type, elapsed_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                endpoint_id, method, status_code,
                json.dumps(headers or {}, ensure_ascii=False),
                json.dumps(body_schema or {}, ensure_ascii=False),
                body_sample, content_type, elapsed_ms
            ))
            conn.commit()
        finally:
            conn.close()

    def get_responses(self, endpoint_id):
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM responses WHERE endpoint_id = ? ORDER BY method",
                (endpoint_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Parameters ────────────────────────────────────────────────────────

    def upsert_parameter(self, endpoint_id, name, param_type="string",
                         location="query", required=False, example_value=""):
        conn = self._connect()
        try:
            conn.execute("""
                INSERT INTO parameters (endpoint_id, name, param_type, location,
                                        required, example_value)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(endpoint_id, name, location) DO UPDATE SET
                    param_type = excluded.param_type,
                    required = CASE WHEN excluded.required THEN 1 ELSE parameters.required END,
                    example_value = CASE WHEN excluded.example_value != ''
                                    THEN excluded.example_value ELSE parameters.example_value END
            """, (endpoint_id, name, param_type, location, 1 if required else 0, example_value))
            conn.commit()
        finally:
            conn.close()

    def get_parameters(self, endpoint_id):
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM parameters WHERE endpoint_id = ? ORDER BY location, name",
                (endpoint_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Probe Runs ────────────────────────────────────────────────────────

    def create_probe_run(self, service_id, config=None):
        """Neuen Probe-Run starten. Gibt run_id zurueck."""
        conn = self._connect()
        try:
            cur = conn.execute("""
                INSERT INTO probe_runs (service_id, config_json)
                VALUES (?, ?)
            """, (service_id, json.dumps(config or {}, ensure_ascii=False)))
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def update_probe_run(self, run_id, status=None, total_requests=None,
                         endpoints_found=None, progress=None):
        """Probe-Run aktualisieren."""
        conn = self._connect()
        try:
            updates = []
            params = []
            if status is not None:
                updates.append("status = ?")
                params.append(status)
                if status in ("completed", "stopped", "error"):
                    updates.append("finished_at = ?")
                    params.append(datetime.utcnow().isoformat())
            if total_requests is not None:
                updates.append("total_requests = ?")
                params.append(total_requests)
            if endpoints_found is not None:
                updates.append("endpoints_found = ?")
                params.append(endpoints_found)
            if progress is not None:
                updates.append("progress_json = ?")
                params.append(json.dumps(progress, ensure_ascii=False))
            if updates:
                params.append(run_id)
                conn.execute(
                    f"UPDATE probe_runs SET {', '.join(updates)} WHERE id = ?",
                    params
                )
                conn.commit()
        finally:
            conn.close()

    def get_last_probe_run(self, service_id):
        """Letzten Run eines Services holen."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM probe_runs WHERE service_id = ? ORDER BY id DESC LIMIT 1",
                (service_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_probe_runs(self, service_id):
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM probe_runs WHERE service_id = ? ORDER BY id DESC",
                (service_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Statistiken ───────────────────────────────────────────────────────

    def get_service_stats(self, service_id):
        """Statistiken fuer einen Service."""
        conn = self._connect()
        try:
            ep_count = conn.execute(
                "SELECT COUNT(*) as c FROM endpoints WHERE service_id = ?",
                (service_id,)
            ).fetchone()["c"]
            resp_count = conn.execute(
                "SELECT COUNT(*) as c FROM responses r "
                "JOIN endpoints e ON r.endpoint_id = e.id "
                "WHERE e.service_id = ?",
                (service_id,)
            ).fetchone()["c"]
            param_count = conn.execute(
                "SELECT COUNT(*) as c FROM parameters p "
                "JOIN endpoints e ON p.endpoint_id = e.id "
                "WHERE e.service_id = ?",
                (service_id,)
            ).fetchone()["c"]
            return {
                "endpoints": ep_count,
                "responses": resp_count,
                "parameters": param_count
            }
        finally:
            conn.close()
