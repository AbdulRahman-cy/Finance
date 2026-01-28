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
        
        #Valide password
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
    

@app.route("/register", methods=["GET", "POST"])
def register():

    session.clear()

    if request.method == "POST":
        #Validate username
        username = request.form.get("username")
        if not username:
            return apology("Must provide username", 403)
        
        #Valide password
        password = request.form.get("password")
        if not password:
            return apology("Must enter password", 403)
        
        #Valide confirm_password
        confirm_password = request.form.get("confirm_password")
        if not confirm_password:
            return apology("Must confirm password", 403)
        
        if password != confirm_password:
            return apology("Wrong password confirmation", 403)

        conn = get_db()
        db = conn.cursor()

        #encrypting password
        hash_pw = generate_password_hash(password)

        #Register the user
        try:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", (username, hash_pw))
            user_id = db.lastrowid
            session["user_id"] = user_id
            conn.commit()
            conn.close()
        except sqlite3.IntegrityError:
            conn.close()
            return apology("Username already taken", 403)
        
        return redirect("/")
    
    else:
        return render_template("register.html")
    
@app.route("/")
@login_required
def index():
    conn = get_db()
    db = conn.cursor()

    db.execute("SELECT cash FROM users WHERE id = ?", (session["user_id"],))
    cash = db.fetchone()["cash"]

    #Quering number of shares
    db.execute("""
        SELECT symbol, SUM( CASE WHEN type = 'BUY' THEN shares ELSE -shares END) AS shares
        FROM transactions
        WHERE user_id = ?
        GROUP BY symbol
        HAVING shares > 0
                """, (session["user_id"],))

    rows = db.fetchall()
    conn.close()

    portfolio = []
    total_stock_value = 0

    for row in rows:
        quote = lookup(row["symbol"])
        total = row["shares"] * quote["price"]
        total_stock_value += total
        
        portfolio.append({
            "symbol": row["symbol"],
            "shares": row["shares"],
            "price": quote["price"],
            "total": total
        })

    grand_total = cash + total_stock_value

    return render_template(
        "index.html",
        portfolio=portfolio,
        cash=cash,
        grand_total=grand_total
    )

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quote = lookup(symbol)

        if not quote:
            return apology("Please enter a valid quote", 403)

        quote_name = quote["name"]
        quote_price = quote["price"]
        quote_symbol = quote["symbol"]

        return render_template("quote_data.html", quote_name=quote_name, quote_price=quote_price, quote_symbol=quote_symbol)
    
    else:
        return render_template("quote.html")
    
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    if request.method == "POST":
        quote_symbol = request.form.get("symbol")
        if not quote_symbol:
            return apology("Must select quote", 403)
        
        quote = lookup(quote_symbol)
        if not quote:
            return apology("Invalid symbol", 403)
        
        quote_price = quote["price"]

        #Casting number of quotes to int
        #try except here to avoid ValueError
        try:
            num_of_quotes = int(request.form.get("num_of_quotes"))
        except:
            return apology("Invalid number of shares", 403)

        if num_of_quotes < 1:
            return apology("Must enter valid number of quotes", 403)
        
        total_price = num_of_quotes * quote_price

        conn = get_db()
        db = conn.cursor()

        db.execute("SELECT cash FROM users WHERE id = ?", (session["user_id"],))
        row = db.fetchone()
        available_cash = row["cash"]

        if total_price > available_cash:
            conn.close()
            return apology("No available cash")
        
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", (total_price, session["user_id"]))

        db.execute("INSERT into transactions (user_id, symbol, shares, price, type)"
                   "VALUES (?, ?, ?, ?, ?)", 
                   (session["user_id"], quote_symbol, num_of_quotes, quote_price, 'BUY'))
        conn.commit()
        conn.close()
        
        return redirect("/")
    
    else:
        return render_template("buy.html")
    
@app.route("/sell", methods = ["POST", "GET"])
@login_required
def sell():

    if request.method == "POST":
        quote_symbol = request.form.get("symbol")
        if not quote_symbol:
            return apology("Must select quote", 403)
        
        quote = lookup(quote_symbol)
        if not quote:
            return apology("Invalid symbol", 403)
        
        quote_price = quote["price"]

        try:
            num_of_quotes = int(request.form.get("num_of_quotes"))
        except:
            return apology("Not enough shares", 403)

        if num_of_quotes < 1:
            return apology("Must enter valid number of quotes", 403)
        
        total_price = num_of_quotes * quote_price
        
        conn = get_db()
        db = conn.cursor()

        db.execute("""
            SELECT SUM(
                CASE
                    WHEN type = 'BUY' THEN shares
                    ELSE -shares
                END
            ) AS shares
            FROM transactions
            WHERE user_id = ? AND symbol = ?
        """, (session["user_id"], quote_symbol))

        row = db.fetchone()
        owned_shares = row["shares"]

        if not owned_shares or owned_shares < num_of_quotes:
            conn.close()
            return apology("Not enough shares", 403)

        #update cash
        #update transactions

        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", (total_price, session["user_id"]))

        db.execute("""
                   INSERT into transactions 
                   (user_id, symbol, shares, price, type) 
                   VALUES (?, ?, ?, ?, ?)
                   """, (session["user_id"], quote_symbol, num_of_quotes, quote_price, 'SELL'))
        conn.commit()
        conn.close()

        return redirect("/")
    
    else:
        conn = get_db()
        db = conn.cursor()

        db.execute("""
            SELECT symbol
            FROM transactions
            WHERE user_id = ?
            GROUP BY symbol
            HAVING SUM(CASE WHEN type = 'BUY' THEN shares ELSE -shares END) > 0
        """, (session["user_id"],))

        symbols = []

        rows = db.fetchall()
        for row in rows:
            symbols.append(row["symbol"])
        
        conn.close()

        return render_template("sell.html", symbols=symbols)

@app.route("/history")
@login_required
def history():
    
    conn = get_db()
    db = conn.cursor()

    db.execute("SELECT * from transactions WHERE user_id = ?", (session["user_id"],))
    transactions = db.fetchall()
    conn.close()

    history = []

    for t in transactions:
        history.append({
            "symbol": t["symbol"],
            "shares": t["shares"],
            "price": t["price"],
            "type": t["type"],
            "timestamp": t["timestamp"],
            "total": t["shares"] * t["price"]
        })

    return render_template("history.html", history=history)

    



        




        




        


    

    
        



