import os
import datetime

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
from dotenv import load_dotenv
load_dotenv()

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is
FLASK_APP = os.getenv('FLASK_APP')
API_KEY = os.getenv('API_KEY')
if not API_KEY:
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # variables
    userStates = []
    userId = session["user_id"]
    c = db.execute("SELECT cash FROM users WHERE id = :id", id=userId)
    cash = round(c[0]['cash'], 2)
    rows = db.execute(
        "SELECT DISTINCT (symbol), user_id, stock FROM purchases WHERE user_id = :id", id=userId)
    allStocksValue = 0

    if len(rows) != 0:
        for row in rows:
            # find total value of one stock type
            count = db.execute(
                "SELECT count FROM ownerships WHERE user_id = :id AND symbol = :symbol", id=userId, symbol=row["symbol"])

            # if user no longer owns stock do not show it in index page
            if count[0]['count'] == 0:
                continue

            # find current price
            data = lookup(row["symbol"])
            currentPrice = data["price"]

            # find total value of one stock type
            total = round(count[0]['count'] * currentPrice, 2)

            # create object containing all information about one stock type
            state = {"symbol": row["symbol"], "name": row["stock"],
                     "shares": count[0]['count'], "price": currentPrice, "total": total}

            # put all information in userStates array
            userStates.append(state)

            # find total value of all stocks
            allStocksValue = round(allStocksValue + total, 2)

        return render_template("index.html", rows=userStates, cash=cash, allStocksValue=allStocksValue)

    else:
        return render_template("index.html", cash=cash, allStocksValue=0)

# create new table
# db.execute("CREATE TABLE purchases (user_id INTEGER, symbol TEXT, stock TEXT, shares NUMERIC, price NUMERIC, date DATE)")
# db.execute("CREATE TABLE ownerships (user_id INTEGER, symbol TEXT, count NUMERIC)")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        # variables
        symbol = request.form.get('symbol')
        shares = int(request.form.get('shares'))
        data = lookup(symbol)
        userId = session["user_id"]

        # error checking
        # check if symbol is valid
        if not symbol or data == None:
            return apology("invalid symbol", 403)
        # shares count is greater than zero
        if int(request.form.get("shares")) <= 0:
            return apology("invalid shares count", 403)
        # variables
        fullPrice = round(data["price"] * int(request.form.get("shares")), 2)
        cashObj = db.execute("SELECT cash FROM users WHERE id=:id", id=userId)
        cash = cashObj[0]["cash"]
        # user do not have enough cash
        if fullPrice > cash:
            return apology("You dont have enough cash", 403)

        # put data in tables
        # purchases table
        db.execute("INSERT INTO purchases (user_id, symbol, stock, shares, price, date) VALUES (?, ?, ?, ?, ?, ?)",
                   userId, data["symbol"], data["name"], shares, fullPrice, datetime.datetime.now())

        # ownerships table
        exist = db.execute(
            "SELECT count FROM ownerships WHERE symbol = :symbol AND user_id = :id", symbol=data["symbol"], id=userId)
        if len(exist) == 0:
            db.execute("INSERT INTO ownerships (user_id, symbol, count) VALUES (?, ?, ?)",
                       userId, data["symbol"], request.form.get('shares'))
        else:
            count = shares + int(exist[0]['count'])
            db.execute("UPDATE ownerships SET count = :count WHERE user_id = :id AND symbol = :symbol",
                       count=count, id=userId, symbol=data["symbol"])
        # users table
        db.execute("UPDATE users SET cash = :cash WHERE id = :id",
                   cash=cash - fullPrice, id=userId)

        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    data = db.execute(
        "SELECT symbol, shares, price, date FROM purchases WHERE user_id = :id", id=session["user_id"])
    return render_template("history.html", data=data)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # symbol's input is blank
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)

        # search stock
        data = lookup(request.form.get("symbol"))

        # requested stock does not exist
        if data == None:
            return apology("invalid symbol", 403)

        return render_template("quoted.html", name=data["name"], symbol=data["symbol"], price=data["price"])
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    session.clear()

    if request.method == "POST":

        rows = db.execute("SELECT * FROM users WHERE username= :username",
                          username=request.form.get("username"))

        # username already exists
        if len(rows) == 1:
            return apology("username already exists", 403)

        # username's input is blank
        elif not request.form.get("username"):
            return apology("enter your username", 403)

        # either password input is blank
        if not request.form.get("password") or not request.form.get("confirmation"):
            return apology("enter your password", 403)

        # passwords do not not match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("make sure to repeat your password correctly", 403)

        else:
            # generate hash password
            password = generate_password_hash(request.form.get("password"))
            # add new user
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)",
                       request.form.get("username"), password)
        # redirect user to home page
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":
        # variables
        userId = session["user_id"]
        selectedSymbol = request.form.get('symbol')
        exist = db.execute(
            "SELECT count FROM ownerships WHERE symbol = :symbol AND user_id = :id", symbol=selectedSymbol, id=userId)
        shares = int(request.form.get('shares'))
        data = lookup(request.form.get("symbol"))

        # errors
        # no symbol
        if selectedSymbol == "None":
            return apology("No selected symbol", 403)
        # user do not have shares of selected symbol
        if len(exist) == 0:
            return apology('You can not sell stock you do not have', 403)
        elif exist[0]['count'] == 0:
            return apology('You can not sell stock you do not have', 403)
        # shares count is greater than zero
        if shares <= 0:
            return apology("invalid shares count", 403)
        # trying to sell more than user owns
        if shares > exist[0]['count']:
            return apology('you do not have that many shares', 403)

        # variables
        fullPrice = data["price"] * shares
        cashObj = db.execute("SELECT cash FROM users WHERE id=:id", id=userId)
        cash = cashObj[0]["cash"]

        # fill tables
        # purchases table
        db.execute("INSERT INTO purchases (user_id, symbol, stock, shares, price, date) VALUES (?, ?, ?, ?, ?, ?)",
                   userId, data["symbol"], data["name"], -shares, fullPrice, datetime.datetime.now())
        # user table
        db.execute("UPDATE users SET cash = :cash WHERE id =:id",
                   cash=cash + fullPrice, id=userId)
        # ownerships table
        # n = db.execute("SELECT count FROM ownerships WHERE user_id = :id AND symbol = :symbol", id = userId, symbol = request.form.get("symbol"))
        count = int(exist[0]['count']) - shares
        db.execute("UPDATE ownerships SET count = :count WHERE user_id = :id AND symbol = :symbol",
                   count=count, id=userId, symbol=selectedSymbol)

        return redirect("/")

    else:
        symbols = db.execute("SELECT DISTINCT symbol FROM purchases")
        return render_template("sell.html", symbols=symbols)


@app.route("/changepassword", methods=["GET", "POST"])
def changepassword():
    """Change password"""
    if request.method == "POST":
        userId = session["user_id"]
        rows = db.execute("SELECT * FROM users WHERE id = :id", id=userId)

        # errors
        # ensure all fields are filled
        if not request.form.get("old-password") or not request.form.get("new-password") or not request.form.get("confirmation"):
            return apology("all fields must be filled", 403)
        # old password is incorrect
        elif not check_password_hash(rows[0]['hash'], request.form.get("old-password")):
            return apology("invalid password", 403)
        # passwords do not not match
        elif request.form.get("new-password") != request.form.get("confirmation"):
            return apology("make sure to repeat your new password correctly", 403)

        # change password
        else:
            # generate hash password
            password = generate_password_hash(request.form.get("new-password"))
            # edit users table
            db.execute("UPDATE users SET hash = :hash WHERE id = :id",
                       hash=password, id=userId)
        # redirect user to home page
        return redirect("/")
    else:
        return render_template('changepassword.html')


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
