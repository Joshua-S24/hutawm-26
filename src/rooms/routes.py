from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from db import rooms, machine_types

bp = Blueprint("rooms", __name__, url_prefix="/rooms")


def utcnow():
    return datetime.now(timezone.utc)


def clean_code(code):
    return code.strip().upper() 


def get_room(code):
    room = rooms.find_one({"roomId": clean_code(code)})
    if not room:
        abort(404)
    return room


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
            "type": t.get("type"),
            "cycles": t.get("cycles", []),
            "cycleName": m.get("cycleName"),
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
    return render_template("rooms/view.html", room=room, machines=decorate(room))


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
        }},
    )
    if result.matched_count == 0:
        flash("That machine is already running.")
    return back


@bp.route("/<code>/machines/<int:machine_id>/stop", methods=["POST"])
def stop(code, machine_id):
    room = get_room(code)
    rooms.update_one(
        {"roomId": room["roomId"], "machines.machineId": machine_id},
        {"$set": {
            "machines.$.cycleName": None,
            "machines.$.startedAt": None,
            "machines.$.endsAt": None,
        }},
    )
    return redirect(url_for("rooms.room_view", code=room["roomId"]))