import os
from urllib.parse import quote_plus # makes uri cleaner
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()  # redundant but harmless i suppose

USER = quote_plus(os.environ["DB_USERNAME"])
PASSWORD = quote_plus(os.environ["DB_PASSWORD"])

mongo_uri = f"mongodb+srv://{USER}:{PASSWORD}@cluster0.tk16v6r.mongodb.net/"
client = MongoClient(mongo_uri, tz_aware=True)
db = client["WasheteriaTracking"]


rooms = db["rooms"]
machine_types = db["machine_types"]
reports = db["reports"]
users = db["users"]
users.create_index("username", unique=True)
users.create_index("email", unique=True)
rooms.create_index("roomId", unique=True)
reports.create_index([("roomId", 1), ("machineId", 1), ("createdAt", -1)])