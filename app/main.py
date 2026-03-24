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
    # Lisboa T1 Chegadas (14)
    (1, "T1-CHEG-01", "PSP", "LIS T1 Chegadas", "Operational"),
    (2, "T1-CHEG-02", "PSP", "LIS T1 Chegadas", "Operational"),
    (3, "T1-CHEG-03", "PSP", "LIS T1 Chegadas", "Operational"),
    (4, "T1-CHEG-04", "PSP", "LIS T1 Chegadas", "Operational"),
    (5, "T1-CHEG-05", "PSP", "LIS T1 Chegadas", "Operational"),
    (6, "T1-CHEG-06", "PSP", "LIS T1 Chegadas", "Operational"),
    (7, "T1-CHEG-07", "PSP", "LIS T1 Chegadas", "Operational"),
    (8, "T1-CHEG-08", "PSP", "LIS T1 Chegadas", "Operational"),
    (9, "T1-CHEG-09", "PSP", "LIS T1 Chegadas", "Operational"),
    (10, "T1-CHEG-10", "PSP", "LIS T1 Chegadas", "Operational"),
    (11, "T1-CHEG-11", "PSP", "LIS T1 Chegadas", "Operational"),
    (12, "T1-CHEG-12", "PSP", "LIS T1 Chegadas", "Operational"),
    (13, "T1-CHEG-13", "PSP", "LIS T1 Chegadas", "Operational"),
    (14, "T1-CHEG-14", "PSP", "LIS T1 Chegadas", "Operational"),

    # Lisboa T1 Partidas (14)
    (15, "T1-PART-01", "PSP", "LIS T1 Partidas", "Operational"),
    (16, "T1-PART-02", "PSP", "LIS T1 Partidas", "Operational"),
    (17, "T1-PART-03", "PSP", "LIS T1 Partidas", "Operational"),
    (18, "T1-PART-04", "PSP", "LIS T1 Partidas", "Operational"),
    (19, "T1-PART-05", "PSP", "LIS T1 Partidas", "Operational"),
    (20, "T1-PART-06", "PSP", "LIS T1 Partidas", "Operational"),
    (21, "T1-PART-07", "PSP", "LIS T1 Partidas", "Operational"),
    (22, "T1-PART-08", "PSP", "LIS T1 Partidas", "Operational"),
    (23, "T1-PART-09", "PSP", "LIS T1 Partidas", "Operational"),
    (24, "T1-PART-10", "PSP", "LIS T1 Partidas", "Operational"),
    (25, "T1-PART-11", "PSP", "LIS T1 Partidas", "Operational"),
    (26, "T1-PART-12", "PSP", "LIS T1 Partidas", "Operational"),
    (27, "T1-PART-13", "PSP", "LIS T1 Partidas", "Operational"),
    (28, "T1-PART-14", "PSP", "LIS T1 Partidas", "Operational"),

    # Zona T (4)
    (29, "ZT-01", "PSP", "Zona T", "Operational"),
    (30, "ZT-02", "PSP", "Zona T", "Operational"),
    (31, "ZT-03", "PSP", "Zona T", "Operational"),
    (32, "ZT-04", "PSP", "Zona T", "Operational"),

    # T2 Partidas (5)
    (33, "T2-PART-01", "PSP", "LIS T2 Partidas", "Operational"),
    (34, "T2-PART-02", "PSP", "LIS T2 Partidas", "Operational"),
    (35, "T2-PART-03", "PSP", "LIS T2 Partidas", "Operational"),
    (36, "T2-PART-04", "PSP", "LIS T2 Partidas", "Operational"),
    (37, "T2-PART-05", "PSP", "LIS T2 Partidas", "Operational"),
])

    for group_name in ["Security", "Enrollment", "Boarding SBG25", "Boarding SBG46", "Boarding SBG47"]:
        cur.execute("""
        INSERT INTO group_incidents (group_name, incident_start, current_priority)
        VALUES (?, NULL, 'OK')
        """, (group_name,))

    conn.commit()
    conn.close()


def calculate_priority(group_name, down_count):
    # LIS T1 Chegadas / Partidas
    if group_name in ["LIS T1 Chegadas", "LIS T1 Partidas"]:
        if down_count >= 7:
            return "P1"
        elif down_count >= 4:
            return "P2"
        elif down_count >= 3:
            return "P3"
        return "OK"

    # Zona T
    if group_name == "Zona T":
        if down_count >= 2:
            return "P1"
        elif down_count == 1:
            return "P2"
        return "OK"

    # LIS T2
    if group_name == "LIS T2 Partidas":
        if down_count >= 3:
            return "P1"
        elif down_count == 2:
            return "P2"
        elif down_count >= 1:
            return "P3"
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
