from flask import Flask, jsonify
import os
from dotenv import load_dotenv

from db import client 
from views import views
from auth.routes import bp as auth_bp
from rooms.routes import bp as rooms_bp
# from machines.routes import bp as machines_bp

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]  # required for session/login
app.register_blueprint(views, url_prefix="/")
app.register_blueprint(auth_bp)
app.register_blueprint(rooms_bp)

@app.route("/ping-db")
def ping_db():
    try:
        client.admin.command("ping")
        return jsonify({"ok": True, "message": "MongoDB is reachable"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/")
def home():
    return redirect(url_for("rooms.dashboard"))

if __name__ == "__main__":
    app.run(debug=False, port=5001) # TODO: Should be false when shipping