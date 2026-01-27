import os
import sqlite3
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd

app = Flask(__name__)

app.jinja_env.filters["usd"] = usd

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

def get_db():

    conn = sqlite3.connect("finance.db")
    conn.row_factory = sqlite3.Row  # So rows behave like dicts
    return conn


@app.route("/login", methods=["GET", "POST"])
def login():

    #Forget any user that have logged in before
    session.clear()

    if request.method == "POST":
        #Validate username
        username = request.form.get("username")
        if not username:
            return apology("Must provide username", 403)
        
        #valide password
        password = request.form.get("password")
        if not password:
            return apology("Must enter password", 403)
        
        #Open connection to the database
        conn = get_db()
        db = conn.cursor()

        #Query for the user data
        db.execute("SELECT * from users WHERE username = ?", (username,))
        row = db.fetchone()

        #Validate presence of user's data 
        #Validate matching of username and pass
        if row is None or not check_password_hash(row["hash"], password):
            return apology("Invalid username and/or password", 403)

        #Remember user
        session["user_id"] = row["id"]

        #Close connection
        conn.close()

        #Return to homepage
        return redirect("/")
    
    else:
        return render_template("login.html")
    


