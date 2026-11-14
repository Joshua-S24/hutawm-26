from flask import Flask, jsonify
from pymongo import MongoClient
import os, json
from dotenv import load_dotenv

# Blueprints
from views import views

# Setup
load_dotenv()

USER = os.getenv("DB_USERNAME")
PASSWORD = os.getenv("DB_PASSWORD")

app = Flask(__name__)
app.register_blueprint(views, url_prefix="/")
mongo_uri = "mongodb+srv://" + USER + ":" + PASSWORD + "@cluster0.tk16v6r.mongodb.net/"
client = MongoClient(mongo_uri)

# App
@app.route("/ping-db")
def ping_db():
    try:
        client.admin.command("ping")
        return jsonify({"ok": True, "message": "MongoDB is reachable"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/")
def index():
    return "Flask + MongoDB is running. Try GET /ping-db"

if __name__ == "__main__":
    app.run()