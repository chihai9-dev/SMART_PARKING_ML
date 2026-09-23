"""Lưu vé gửi xe và lịch sử quét bằng SQLite."""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "database" / "parking.db"
SCAN_DIR = PROJECT_ROOT / "data" / "processed" / "scans"
TICKET_IMAGE_DIR = PROJECT_ROOT / "data" / "processed" / "ticket_images"
SCAN_CSV = PROJECT_ROOT / "data" / "processed" / "plate_scans.csv"


class TicketStore:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=DELETE")
        except sqlite3.Error:
            pass
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_code TEXT UNIQUE,
                    student_id TEXT,
                    plate TEXT NOT NULL,
                    vehicle_type TEXT,
                    entry_time TEXT NOT NULL,
                    predicted_behavior TEXT,
                    duration_minutes INTEGER,
                    recommended_zone TEXT,
                    estimated_exit TEXT,
                    entry_image_path TEXT,
                    plate_image_path TEXT,
                    exit_image_path TEXT,
                    exit_plate_image_path TEXT,
                    extra_json TEXT,
                    exit_time TEXT,
                    exit_plate TEXT,
                    exit_vehicle_type TEXT,
                    plate_match INTEGER,
                    vehicle_match INTEGER,
                    overtime_minutes INTEGER,
                    penalty_vnd INTEGER,
                    status TEXT NOT NULL DEFAULT 'open',
                    alert_message TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS plate_scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate TEXT,
                    valid INTEGER,
                    confidence REAL,
                    engine TEXT,
                    source_filename TEXT,
                    image_path TEXT,
                    crop_path TEXT,
                    vehicle_type TEXT,
                    created_at TEXT NOT NULL,
                    extra_json TEXT
                )
                """
            )

            # Migration cho database cũ.
            columns = {row[1] for row in conn.execute("PRAGMA table_info(tickets)").fetchall()}
            migrations = {
                "ticket_code": "TEXT",
                "entry_image_path": "TEXT",
                "plate_image_path": "TEXT",
                "exit_image_path": "TEXT",
                "exit_plate_image_path": "TEXT",
            }
            for name, definition in migrations.items():
                if name not in columns:
                    conn.execute(f"ALTER TABLE tickets ADD COLUMN {name} {definition}")

            # Bổ sung mã vé cho các vé cũ chưa có mã.
            rows = conn.execute(
                "SELECT id, created_at, ticket_code FROM tickets WHERE ticket_code IS NULL OR ticket_code = ''"
            ).fetchall()
            for row in rows:
                try:
                    dt = datetime.fromisoformat(str(row[1]).replace("Z", ""))
                except Exception:
                    dt = datetime.now()
                code = f"SP-{dt:%Y%m%d}-{int(row[0]):06d}"
                conn.execute("UPDATE tickets SET ticket_code = ? WHERE id = ?", (code, row[0]))
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tickets_ticket_code ON tickets(ticket_code)")
            conn.commit()

    @staticmethod
    def _new_ticket_code(ticket_id: int, entry_time: str) -> str:
        try:
            dt = datetime.fromisoformat(str(entry_time).replace("Z", ""))
        except Exception:
            dt = datetime.now()
        return f"SP-{dt:%Y%m%d}-{int(ticket_id):06d}"

    def _prepare_extra(self, payload: dict[str, Any]) -> str:
        return json.dumps(payload.get("extra") or {}, ensure_ascii=False)

    def open_ticket(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        extra_json = self._prepare_extra(payload)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO tickets (
                    ticket_code, student_id, plate, vehicle_type, entry_time,
                    predicted_behavior, duration_minutes, recommended_zone,
                    estimated_exit, entry_image_path, plate_image_path,
                    extra_json, status, created_at
                ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
                """,
                (
                    payload.get("student_id"),
                    payload["plate"],
                    payload.get("vehicle_type"),
                    payload["entry_time"],
                    payload.get("predicted_behavior"),
                    payload.get("duration_minutes"),
                    payload.get("recommended_zone"),
                    payload.get("estimated_exit"),
                    payload.get("entry_image_path"),
                    payload.get("plate_image_path"),
                    extra_json,
                    now,
                ),
            )
            ticket_id = int(cur.lastrowid)
            code = self._new_ticket_code(ticket_id, payload.get("entry_time") or now)
            conn.execute("UPDATE tickets SET ticket_code = ? WHERE id = ?", (code, ticket_id))
            conn.commit()
        return self.get(ticket_id)

    def find_open_by_plate(self, plate: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM tickets
                WHERE plate = ? AND status = 'open'
                ORDER BY id DESC LIMIT 1
                """,
                (plate,),
            ).fetchone()
        return dict(row) if row else None

    def get(self, ticket_id: int) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return dict(row) if row else None

    def close_ticket(self, ticket_id: int, updates: dict[str, Any]) -> dict[str, Any]:
        fields = []
        values = []
        for key in (
            "exit_time",
            "exit_plate",
            "exit_vehicle_type",
            "exit_image_path",
            "exit_plate_image_path",
            "plate_match",
            "vehicle_match",
            "overtime_minutes",
            "penalty_vnd",
            "status",
            "alert_message",
        ):
            if key in updates:
                fields.append(f"{key} = ?")
                val = updates[key]
                if isinstance(val, bool):
                    val = int(val)
                values.append(val)
        values.append(ticket_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE tickets SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()
        return self.get(ticket_id)

    def list_tickets(self, status: Optional[str] = None, limit: int = 50) -> list[dict[str, Any]]:
        sql = "SELECT * FROM tickets"
        params: list[Any] = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def save_plate_scan(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        extra = payload.get("extra") or {}
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO plate_scans (
                    plate, valid, confidence, engine, source_filename,
                    image_path, crop_path, vehicle_type, created_at, extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("plate"),
                    int(bool(payload.get("valid"))),
                    payload.get("confidence"),
                    payload.get("engine"),
                    payload.get("source_filename"),
                    payload.get("image_path"),
                    payload.get("crop_path"),
                    payload.get("vehicle_type"),
                    now,
                    json.dumps(extra, ensure_ascii=False),
                ),
            )
            scan_id = cur.lastrowid
        SCAN_CSV.parent.mkdir(parents=True, exist_ok=True)
        write_header = not SCAN_CSV.exists()
        with SCAN_CSV.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            if write_header:
                writer.writerow(["id", "created_at", "plate", "valid", "confidence", "engine", "source_filename", "image_path"])
            writer.writerow([
                scan_id, now, payload.get("plate"), int(bool(payload.get("valid"))),
                payload.get("confidence"), payload.get("engine"),
                payload.get("source_filename"), payload.get("image_path"),
            ])
        return self.get_scan(scan_id)

    def get_scan(self, scan_id: int) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM plate_scans WHERE id = ?", (scan_id,)).fetchone()
        return dict(row) if row else None

    def list_scans(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM plate_scans ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
