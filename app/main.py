from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import sqlite3
from datetime import datetime

app = FastAPI()

DB_PATH = "airport_v2.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso():
    return datetime.utcnow().isoformat()


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS gates (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        project_name TEXT NOT NULL,
        group_name TEXT NOT NULL,
        status TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS group_incidents (
        group_name TEXT PRIMARY KEY,
        incident_start TEXT,
        current_priority TEXT NOT NULL DEFAULT 'OK'
    )
    """)

    cur.execute("DELETE FROM gates")
    cur.execute("DELETE FROM group_incidents")

    cur.executemany("""
    INSERT INTO gates (id, name, project_name, group_name, status)
    VALUES (?, ?, ?, ?, ?)
    """, [
        (1, "SCP 11", "ANASEAMLESS", "Security", "Operational"),
        (2, "SCP 12", "ANASEAMLESS", "Security", "Operational"),
        (3, "SCP 14", "ANASEAMLESS", "Security", "Operational"),
        (4, "SCP 15", "ANASEAMLESS", "Security", "Operational"),
        (5, "SCP 16", "ANASEAMLESS", "Security", "Operational"),
        (6, "SCP 17", "ANASEAMLESS", "Security", "Operational"),
        (7, "SCP 21", "ANASEAMLESS", "Security", "Operational"),
        (8, "SCP 22", "ANASEAMLESS", "Security", "Operational"),
        (9, "SCP 23", "ANASEAMLESS", "Security", "Operational"),
        (10, "SCP 24", "ANASEAMLESS", "Security", "Operational"),
        (11, "SCP 25", "ANASEAMLESS", "Security", "Operational"),
        (12, "SCP 28", "ANASEAMLESS", "Security", "Operational"),
        (13, "SCP 29", "ANASEAMLESS", "Security", "Operational"),
        (14, "SCP 30", "ANASEAMLESS", "Security", "Operational"),
        (15, "SCP 31", "ANASEAMLESS", "Security", "Operational"),
        (16, "KIOSK 01", "ANASEAMLESS", "Enrollment", "Operational"),
        (17, "KIOSK 03", "ANASEAMLESS", "Enrollment", "Operational"),
        (18, "KIOSK 04", "ANASEAMLESS", "Enrollment", "Operational"),
        (19, "KIOSK 05", "ANASEAMLESS", "Enrollment", "Operational"),
        (20, "KIOSK 06", "ANASEAMLESS", "Enrollment", "Operational"),
        (21, "SBG25-01", "ANASEAMLESS", "Boarding SBG25", "Operational"),
        (22, "SBG25-02", "ANASEAMLESS", "Boarding SBG25", "Operational"),
        (23, "SBG46-01", "ANASEAMLESS", "Boarding SBG46", "Operational"),
        (24, "SBG46-02", "ANASEAMLESS", "Boarding SBG46", "Operational"),
        (25, "SBG47-01", "ANASEAMLESS", "Boarding SBG47", "Operational"),
        (26, "SBG47-02", "ANASEAMLESS", "Boarding SBG47", "Operational"),
    ])

    for group_name in ["Security", "Enrollment", "Boarding SBG25", "Boarding SBG46", "Boarding SBG47"]:
        cur.execute("""
        INSERT INTO group_incidents (group_name, incident_start, current_priority)
        VALUES (?, NULL, 'OK')
        """, (group_name,))

    conn.commit()
    conn.close()


def calculate_priority(group_name, down_count):
    if group_name.startswith("Boarding"):
        if down_count >= 2:
            return "P1"
        elif down_count == 1:
            return "P2"
        return "OK"

    if group_name == "Security":
        if down_count >= 12:
            return "P1"
        elif down_count >= 8:
            return "P2"
        elif down_count >= 4:
            return "P3"
        elif down_count >= 1:
            return "P4"
        return "OK"

    if group_name == "Enrollment":
        if down_count >= 1:
            return "P4"
        return "OK"

    return "OK"


def get_sla_hours(priority):
    if priority == "P1":
        return 4
    if priority == "P2":
        return 8
    if priority == "P3":
        return 24
    if priority == "P4":
        return 36
    return None


def recalculate_group(cur, group_name):
    cur.execute("""
    SELECT COUNT(*) as total
    FROM gates
    WHERE group_name = ? AND status = 'Down'
    """, (group_name,))
    down_count = cur.fetchone()["total"]

    priority = calculate_priority(group_name, down_count)

    cur.execute("""
    SELECT incident_start, current_priority
    FROM group_incidents
    WHERE group_name = ?
    """, (group_name,))
    incident = cur.fetchone()

    incident_start = incident["incident_start"] if incident else None

    if priority == "OK":
        incident_start = None
    else:
        if not incident_start:
            incident_start = now_iso()

    cur.execute("""
    UPDATE group_incidents
    SET incident_start = ?, current_priority = ?
    WHERE group_name = ?
    """, (incident_start, priority, group_name))

    return {
        "group": group_name,
        "down_count": down_count,
        "priority": priority,
        "incident_start": incident_start,
        "sla_hours": get_sla_hours(priority)
    }


init_db()


class StatusUpdate(BaseModel):
    status: str


@app.get("/api/gates")
def get_gates():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        id,
        name,
        project_name as project,
        group_name as "group",
        status
    FROM gates
    ORDER BY id
    """)

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


@app.get("/api/groups")
def get_groups():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT group_name
    FROM group_incidents
    ORDER BY group_name
    """)

    groups = []
    for row in cur.fetchall():
        summary = recalculate_group(cur, row["group_name"])
        groups.append(summary)

    conn.commit()
    conn.close()
    return groups


@app.post("/api/gates/{gate_id}/status")
def update_gate_status(gate_id: int, payload: StatusUpdate):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, group_name FROM gates WHERE id = ?", (gate_id,))
    existing = cur.fetchone()

    if not existing:
        conn.close()
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "Gate not found"}
        )

    cur.execute(
        "UPDATE gates SET status = ? WHERE id = ?",
        (payload.status, gate_id)
    )

    group_summary = recalculate_group(cur, existing["group_name"])

    cur.execute("""
    SELECT
        id,
        name,
        project_name as project,
        group_name as "group",
        status
    FROM gates
    WHERE id = ?
    """, (gate_id,))
    gate = dict(cur.fetchone())

    conn.commit()
    conn.close()

    return {
        "success": True,
        "gate": gate,
        "group_summary": group_summary
    }


app.mount("/", StaticFiles(directory="static", html=True), name="static")
