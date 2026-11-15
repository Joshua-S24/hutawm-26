from functools import wraps
from flask import session, request, redirect, url_for, flash, render_template, Blueprint
from argon2.exceptions import VerifyMismatchError
from argon2 import PasswordHasher
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError

from db import users

ph = PasswordHasher()

bp = Blueprint("auth", __name__, url_prefix="/auth")

# Protects any route you decorate with it
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        confirm = request.form["confirm_password"]

        if password != confirm:
            flash("Passwords do not match.")
            return render_template("auth/register.html", username=username, email=email)

        try:
            result = users.insert_one({
                "username": username,
                "email": email,
                "passwordHash": ph.hash(password),
                "createdAt": datetime.now(timezone.utc),
                "accessibleRoomIds": [],
                "adminRoomIds": []
            })
        except DuplicateKeyError:
            flash("That username or email is already taken.")
            return render_template("auth/register.html", username=username, email=email)

        # Log them in immediately and go to the dashboard
        session.clear()
        session["user_id"] = str(result.inserted_id)
        return redirect(url_for("rooms.dashboard"))

    return render_template("auth/register.html")

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = users.find_one({"username": request.form["username"]})
        try:
            if user:
                ph.verify(user["passwordHash"], request.form["password"])
                session.clear()
                session["user_id"] = str(user["_id"])
                return redirect(url_for("rooms.dashboard"))
        except VerifyMismatchError:
            pass
        flash("Invalid username or password.")  # same message either way
    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    session.clear()
    # TODO: Change this to the default views
    return redirect(url_for("auth.login"))


@bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("rooms/dashboard.html")