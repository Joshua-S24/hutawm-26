from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, redirect, session, url_for, flash, jsonify, abort
from bson import ObjectId
from db import rooms, machine_types, users, reports
import math

bp = Blueprint("rooms", __name__, url_prefix="/rooms")
VALID_STATUSES = {"IDLE", "RUNNING", "BROKEN"}
VERIFY_RADIUS_M = 300 # how close counts as "at the room", in meters (adjusted from 150)
VERIFY_TTL = timedelta(minutes=15)


def utcnow():
    return datetime.now(timezone.utc)

def clean_code(code):
    return code.strip().upper() 

def get_room(code):
    room = rooms.find_one({"roomId": clean_code(code)})
    if not room:
        abort(404)
    return room

def is_room_admin(room):
    uid = session.get("user_id")
    if not uid:
        return False
    return users.count_documents(
        {"_id": ObjectId(uid), "adminRoomIds": room["_id"]}, limit=1
    ) > 0

def distance_m(lat1, lon1, lat2, lon2):
    """Haversine distance in meters."""
    # Haversine distance accounts for the spherical nature of Earth
    # Might be overkill though; as far as we're concerned the Earth is flat (between a low distance)
    # Also, results should not be stored. (Privacy reasons. Stalking, even.)
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def room_point(room):
    """Return (lat, lon) from address.location, or None if missing/private."""
    addr = room.get("address")
    if not addr:
        return None
    loc = addr.get("location")
    if not loc or loc.get("type") != "Point":
        return None
    try:
        lon, lat = loc["coordinates"] # GeoJSON order is [longitude, latitude]
        return float(lat), float(lon)
    except (KeyError, TypeError, ValueError):
        return None


def is_location_verified(room_code):
    """True if this session recently passed a location check for this room."""
    ts = session.get("verified", {}).get(room_code)
    if not ts:
        return False
    return utcnow() - datetime.fromtimestamp(ts, timezone.utc) < VERIFY_TTL

def decorate(room):
    """Add computed status and cycle options to each machine."""
    now = utcnow()
    ids = [m["referenceId"] for m in room["machines"]]
    types = {t["_id"]: t for t in machine_types.find({"_id": {"$in": ids}})}

    out = []
    for m in room["machines"]:
        ends = m.get("endsAt")
        left = max(0, int((ends - now).total_seconds())) if ends else 0
        t = types.get(m["referenceId"], {})
        out.append({
            "machineId": m["machineId"],
            "name": m.get("machineName"),
            "model": t.get("model"),
            "type": t.get("type"),
            "cycles": t.get("cycles", []),
            "cycleName": m.get("cycleName"),
            "visibleTimer": t.get("visibleTimer", False),
            "running": left > 0,
            "secondsLeft": left,
            "grid_x": m.get("grid_x"),
            "grid_y": m.get("grid_y"),
        })
    return out


@bp.route("/", methods=["GET", "POST"])
def dashboard():
    if request.method == "POST":
        code = clean_code(request.form["room_id"])
        if rooms.find_one({"roomId": code}, {"_id": 1}):
            return redirect(url_for("rooms.room_view", code=code))
        flash("No room with that ID.")
        return render_template("rooms/dashboard.html", room_id=code)
    return render_template("rooms/dashboard.html")


@bp.route("/<code>")
def room_view(code):
    room = get_room(code)
    return render_template("rooms/view.html", room=room, machines=decorate(room), is_admin=is_room_admin(room))


@bp.route("/<code>/api/status")
def room_status(code):
    return jsonify(decorate(get_room(code)))


@bp.route("/<code>/machines/<int:machine_id>/start", methods=["POST"])
def start(code, machine_id):
    room = get_room(code)
    machine = next((m for m in room["machines"] if m["machineId"] == machine_id), None)
    if not machine:
        abort(404)
    back = redirect(url_for("rooms.room_view", code=room["roomId"]))

    mtype = machine_types.find_one({"_id": machine["referenceId"]})
    cycle = next((c for c in (mtype or {}).get("cycles", [])
                if c["name"] == request.form.get("cycle")), None)
    if not cycle:
        flash("Unknown cycle.")
        return back

    now = utcnow()
    result = rooms.update_one(
        {
            "roomId": room["roomId"],
            "machines": {"$elemMatch": {
                "machineId": machine_id,
                "$or": [{"endsAt": None}, {"endsAt": {"$lte": now}}],
            }},
        },
        {"$set": {
            "machines.$.cycleName": cycle["name"],
            "machines.$.startedAt": now,
            "machines.$.endsAt": now + timedelta(minutes=cycle["minutes"]),
            "machines.$.status": "RUNNING"
        }},
    )
    if result.matched_count == 0:
        flash("That machine is already running.")
    return back


@bp.route("/<code>/machines/<int:machine_id>/stop", methods=["POST"])
def stop(code, machine_id):
    room = get_room(code)
    if not is_room_admin(room): abort(403)
    rooms.update_one(
        {"roomId": room["roomId"], "machines.machineId": machine_id},
        {"$set": {
            "machines.$.cycleName": None,
            "machines.$.startedAt": None,
            "machines.$.endsAt": None,
            "machines.$.status": "IDLE"
        }},
    )
    return redirect(url_for("rooms.room_view", code=room["roomId"]))

@bp.route("/<code>/machines/<int:machine_id>/report", methods=["POST"])
def report(code, machine_id):
    room = get_room(code)
    back = redirect(url_for("rooms.room_view", code=room["roomId"]))
    machine = next((m for m in room["machines"] if m["machineId"] == machine_id), None)
    if not machine:
        abort(404)
    

    status = request.form.get("reportedStatus", "")
    if status not in VALID_STATUSES:
        flash("Invalid report status.")
        return back
    
    # Check if current status matches reported status, can it if they match
    current = machine.get("status")

    if status == "RUNNING" and current == "RUNNING":
        flash("This machine is already running.")
        return back
    elif status == "IDLE" and current == "IDLE":
        flash("This machine is already idle.")
        return back

    mtype = machine_types.find_one({"_id": machine["referenceId"]}) or {}
    minutes = None
    if status == "RUNNING" and mtype.get("visibleTimer"):
        try:
            minutes = min(240, max(0, int(request.form.get("reportedMinutesLeft", ""))))
        except ValueError:
            flash("Please enter the minutes left.")
            return back

    uid = session.get("user_id")

    reports.insert_one({
        "roomId": room["roomId"],
        "machineId": machine_id,
        "userSource": ObjectId(uid) if uid else None,
        "locationVerified": is_location_verified(room["roomId"]),
        "reportedStatus": status,
        "reportedMinutesLeft": minutes,
        "createdAt": utcnow(),
    })

    flash("Thanks, your report was submitted.")
    return back

@bp.route("/<code>/machines/<int:machine_id>/reports")
def machine_reports(code, machine_id):
    room = get_room(code)
    docs = (reports.find({"roomId": room["roomId"], "machineId": machine_id})
                .sort("createdAt", -1)
                .limit(10))
    return jsonify([
        {
            "status": d.get("reportedStatus"),
            "minutesLeft": d.get("reportedMinutesLeft"),
            "createdAt": d["createdAt"].isoformat(),
            "verified": d.get("locationVerified", False),
        }
        for d in docs
    ])

@bp.route("/<code>/verify-location", methods=["POST"])
def verify_location(code):
    room = get_room(code)
    data = request.get_json(silent=True) or {}

    try:
        lat = float(data["latitude"])
        lon = float(data["longitude"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"verified": False, "reason": "bad_input"}), 400
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({"verified": False, "reason": "bad_input"}), 400

    point = room_point(room)
    if point is None:
        # Address is null (private): there is nothing to compare against
        return jsonify({"verified": False, "reason": "unavailable"})

    verified = distance_m(lat, lon, *point) <= VERIFY_RADIUS_M
    if verified:
        # Reassign the dict to force session change
        v = dict(session.get("verified", {}))
        v[room["roomId"]] = utcnow().timestamp()
        session["verified"] = v

    return jsonify({"verified": verified})