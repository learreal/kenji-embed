import os
import sqlite3
from datetime import datetime, timezone
from flask import Flask, jsonify, request

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gym_attendance.db")
app = Flask(__name__)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                member_code TEXT NOT NULL UNIQUE,
                rfid_uid TEXT UNIQUE,
                phone TEXT,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL,
                scanned_uid TEXT NOT NULL,
                scan_time TEXT NOT NULL,
                result TEXT NOT NULL DEFAULT 'GRANTED',
                FOREIGN KEY (member_id) REFERENCES members (id)
            );
            """
        )


def normalize_uid(uid):
    if not uid:
        return None
    cleaned = " ".join(str(uid).strip().upper().split())
    return cleaned if cleaned else None


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/stats")
def stats():
    local_today = datetime.now().astimezone().date()
    with get_db() as conn:
        active = conn.execute("SELECT COUNT(*) FROM members WHERE status = 'ACTIVE'").fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
        rows = conn.execute("SELECT scan_time FROM attendance").fetchall()
        today_count = sum(
            1 for r in rows if datetime.fromisoformat(r["scan_time"]).astimezone().date() == local_today
        )
        recent = conn.execute(
            """
            SELECT a.scanned_uid, a.scan_time, a.result, m.full_name, m.member_code
            FROM attendance a JOIN members m ON a.member_id = m.id
            ORDER BY a.id DESC LIMIT 10
            """
        ).fetchall()
    return jsonify({
        "active_members": active,
        "total_members": total,
        "today_attendance": today_count,
        "recent": [dict(r) for r in recent],
    })


@app.get("/api/members")
def list_members():
    q = request.args.get("search", "").strip()
    sql = "SELECT * FROM members"
    params = []
    if q:
        sql += " WHERE full_name LIKE ? OR member_code LIKE ? OR rfid_uid LIKE ?"
        params = [f"%{q}%", f"%{q}%", f"%{q}%"]
    sql += " ORDER BY id DESC"
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return jsonify({"members": [dict(r) for r in rows]})


@app.post("/api/members")
def add_member():
    data = request.get_json(silent=True) or {}
    name = (data.get("full_name") or "").strip()
    code = (data.get("member_code") or "").strip().upper()
    uid = normalize_uid(data.get("rfid_uid"))
    phone = (data.get("phone") or "").strip() or None
    status = (data.get("status") or "ACTIVE").strip().upper()

    if not name or not code:
        return jsonify({"error": "Full name and member code are required."}), 400

    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO members (full_name, member_code, rfid_uid, phone, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (name, code, uid, phone, status, datetime.now(timezone.utc).isoformat()),
            )
        return jsonify({"status": "created"}), 201
    except sqlite3.IntegrityError as e:
        msg = "Duplicate member code or RFID UID."
        if "member_code" in str(e).lower():
            msg = f"Member code '{code}' already exists."
        elif "rfid_uid" in str(e).lower():
            msg = f"RFID UID '{uid}' is already assigned."
        return jsonify({"error": msg}), 400


@app.put("/api/members/<int:member_id>")
def update_member(member_id):
    data = request.get_json(silent=True) or {}
    name = (data.get("full_name") or "").strip()
    code = (data.get("member_code") or "").strip().upper()
    uid = normalize_uid(data.get("rfid_uid"))
    phone = (data.get("phone") or "").strip() or None
    status = (data.get("status") or "ACTIVE").strip().upper()

    if not name or not code:
        return jsonify({"error": "Full name and member code are required."}), 400

    try:
        with get_db() as conn:
            cur = conn.execute(
                "UPDATE members SET full_name=?, member_code=?, rfid_uid=?, phone=?, status=? WHERE id=?",
                (name, code, uid, phone, status, member_id),
            )
            if cur.rowcount == 0:
                return jsonify({"error": "Member not found."}), 404
        return jsonify({"status": "updated"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Duplicate member code or RFID UID."}), 400


@app.patch("/api/members/<int:member_id>/deactivate")
def deactivate_member(member_id):
    with get_db() as conn:
        cur = conn.execute("UPDATE members SET status='INACTIVE' WHERE id=?", (member_id,))
        if cur.rowcount == 0:
            return jsonify({"error": "Member not found."}), 404
    return jsonify({"status": "deactivated"})


@app.post("/api/attendance")
@app.post("/attendance")
def record_attendance():
    data = request.get_json(silent=True) or {}
    uid = normalize_uid(data.get("uid"))
    if not uid:
        return jsonify({"status": "denied", "message": "UID is required."}), 400

    with get_db() as conn:
        member = conn.execute("SELECT * FROM members WHERE rfid_uid = ?", (uid,)).fetchone()
        if not member:
            return jsonify({"status": "denied", "message": "Unauthorized card (Unknown UID)", "uid": uid}), 200
        if member["status"] != "ACTIVE":
            return jsonify({"status": "denied", "message": f"Access denied: {member['full_name']} is INACTIVE", "uid": uid}), 200

        now = datetime.now(timezone.utc)
        last = conn.execute(
            "SELECT scan_time FROM attendance WHERE member_id = ? ORDER BY id DESC LIMIT 1",
            (member["id"],),
        ).fetchone()
        if last and (now - datetime.fromisoformat(last["scan_time"])).total_seconds() < 60:
            return jsonify({
                "status": "granted",
                "message": f"Already checked in recently ({member['full_name']})",
                "uid": uid,
            }), 200

        ts = now.isoformat()
        conn.execute(
            "INSERT INTO attendance (member_id, scanned_uid, scan_time, result) VALUES (?, ?, ?, 'GRANTED')",
            (member["id"], uid, ts),
        )
        return jsonify({
            "status": "granted",
            "message": f"Welcome, {member['full_name']}",
            "uid": uid,
            "member": {"id": member["id"], "full_name": member["full_name"], "member_code": member["member_code"]},
            "timestamp": ts,
        }), 200


@app.get("/api/attendance")
@app.get("/records")
def get_attendance():
    q = request.args.get("search", "").strip()
    sql = """
        SELECT a.id, a.scanned_uid, a.scan_time, a.result, m.full_name, m.member_code
        FROM attendance a JOIN members m ON a.member_id = m.id
    """
    params = []
    if q:
        sql += " WHERE m.full_name LIKE ? OR m.member_code LIKE ? OR a.scanned_uid LIKE ?"
        params = [f"%{q}%", f"%{q}%", f"%{q}%"]
    sql += " ORDER BY a.id DESC LIMIT 200"
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return jsonify({"records": [dict(r) for r in rows]})


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=8000, debug=False)