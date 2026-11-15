from flask import Blueprint, render_template, request, jsonify, redirect, url_for

views = Blueprint(__name__, "views") # can be whatever

@views.route("/")
def home():
    return render_template("index.html", name="noname")
    # within render_template, variables (like names) can be defined that can be used within the file (first param)

@views.route("/room")
def room_view():
    return "hi"