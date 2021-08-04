import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from time import gmtime, strftime

from helpers import apology, login_required, lookup, usd

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

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():

    nomdumec = ((db.execute("SELECT username FROM users WHERE id = (?)", session["user_id"]))[0])["username"]
    data = db.execute("SELECT * FROM data WHERE data_id = (?)", session["user_id"])

    liste1 = []
    for dict in data:
        final = lookup(dict["action"])
        final["nombre"] = dict["nombre"]
        final["totalprice"] = float(dict["nombre"]) * float(final["price"])
        liste1.append(final)

    totalaction = 0
    for row in liste1:
        totalaction += row["totalprice"]
    cashleft = db.execute("SELECT cash FROM users WHERE id = (?)", session["user_id"])[0]["cash"]

    return render_template("index.html", nomdumec=nomdumec, data=liste1, totalaction=totalaction, cashleft=cashleft)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":

        # Checking error
        if not request.form.get("symbol"):
            return apology("No symbol entered :(", 403)

        if not request.form.get("shares"):
            return apology("No shares entered :(", 403)

        try:
            nmbtest = int(request.form.get("shares"))
        except ValueError:
            return apology("shares must be a posative integer", 400)

        if not (abs(nmbtest) == nmbtest):
            return apology("put a real numbee", 400)

        symb = str(request.form.get("symbol"))
        nmb = float(request.form.get("shares"))
        if lookup(symb) == None:
            return apology("symbol don't exist", 400)

        argent = (((db.execute("SELECT cash FROM users WHERE id = (?)", session["user_id"]))[0])['cash'])
        prixaction = (lookup(symb)["price"])*nmb
        if (argent-prixaction) < 0:
            return apology("not enought money bro", 667)

        actionsdumec = db.execute("SELECT * FROM data WHERE data_id = (?)", session["user_id"])

        # updating the database by updating the shares, the bank account of the person
        liste1 = []
        for dict in actionsdumec:
            liste1.append(dict["action"])
        if symb in liste1:
            db.execute("UPDATE data SET nombre = nombre + (?) WHERE data_id= (?) AND action = (?)", nmb, session["user_id"], symb)
        else:
            db.execute("INSERT INTO data (data_id, action, nombre) VALUES(?, ?, ?)", session["user_id"], symb, nmb)

        acttime = strftime("%d/%m/%Y %Hh:%Mm:%Ss", gmtime())
        db.execute("INSERT INTO history (history_id, action, nombre, prix, method, time) VALUES(?, ?, ?, ?, ?, ?)",
                   session["user_id"], symb, nmb, prixaction, "BUY", acttime)
        db.execute("UPDATE users SET cash = cash - (?) WHERE id= (?)", prixaction, session["user_id"])

        return redirect("/")
    # if POST method is not asked
    argenttotal = float(db.execute("SELECT cash FROM users WHERE id= (?)", session["user_id"])[0]["cash"])
    return render_template("buy.html", argenttotal=argenttotal)


@app.route("/history", methods=["GET", "POST"])
@login_required
def history():

    nomdumec = ((db.execute("SELECT username FROM users WHERE id = (?)", session["user_id"]))[0])["username"]
    history = db.execute("SELECT * FROM history WHERE history_id = (?) ORDER BY time DESC LIMIT 10", session["user_id"])

    # doing some math to display bought and sold in history

    totalactionsold = 0
    totalactionbought = 0
    for row in history:
        if row["method"] == "BUY":
            totalactionbought += float(row["prix"])
        elif row["method"] == "SELL":
            totalactionsold += float(row["prix"])

    # if someone want to see his entire history

    if request.method == "POST":
        history = db.execute("SELECT * FROM history WHERE history_id = (?) ORDER BY time DESC", session["user_id"])
        totalactionsold = 0
        totalactionbought = 0
        for row in history:
            if row["method"] == "BUY":
                totalactionbought += float(row["prix"])
            elif row["method"] == "SELL":
                totalactionsold += float(row["prix"])

    return render_template("history.html", nomdumec=nomdumec, data=history, totalactionsold=totalactionsold, totalactionbought=totalactionbought)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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
    if request.method == "POST":
        # error checking again
        if not request.form.get("symbol"):
            return apology("No symbol searched :( ", 400)

        result = lookup(request.form.get("symbol"))
        if result == None:
            return apology("No result boyyyy", 400)

        return render_template("quoted.html", result=result)
    """Get stock quote."""
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        users = db.execute("SELECT username FROM users")

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide password confirmation", 400)

        # Ensure that both password case are the same
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords are not the same,", 400)

        # Ensure that the username not already exists
        elif request.form.get("username") in users:
            return apology("username already exist", 403)

        pseudos = db.execute("SELECT username FROM users")
        for namess in pseudos:
            if ((request.form.get("username")).lower()) == ((namess["username"]).lower()):
                return apology("username already exist :/", 400)

        else:
            db.execute("INSERT INTO users (username, hash) VALUES(?,?)", request.form.get(
                "username"), generate_password_hash(request.form.get("password")))
            rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
            session["user_id"] = rows[0]["id"]

            # Redirect user to home page
            return redirect("/")

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":

        # error checking
        if not request.form.get("symbol"):
            return apology("No symbol entered :(", 400)

        if not request.form.get("shares"):
            return apology("No shares entered :(", 400)

        symb = str(request.form.get("symbol"))
        nmb = float(request.form.get("shares"))

        if lookup(symb) == None:
            return apology("symbol don't exist", 400)
        actionmec = db.execute("SELECT * FROM data WHERE data_id = (?) AND action = (?)", session["user_id"], symb)

        if (len(actionmec) == 0):
            return apology(f"You don't have {symb} at all", 88)

        if (actionmec[0]["nombre"] - nmb) < 0:
            return apology(f"not enought {symb} bro", 400)

        prixaction = (lookup(symb)["price"]) * nmb

        db.execute("UPDATE data SET nombre = nombre - (?) WHERE data_id= (?) AND action = (?)", nmb, session["user_id"], symb)

        acttime = strftime("%d/%m/%Y %Hh:%Mm:%Ss", gmtime())
        db.execute("INSERT INTO history (history_id, action, nombre, prix, method, time) VALUES(?, ?, ?, ?, ?, ?)",
                   session["user_id"], symb, nmb, prixaction, "SELL", acttime)
        db.execute("UPDATE users SET cash = cash + (?) WHERE id= (?)", prixaction, session["user_id"])
        return redirect("/")

    data = db.execute("SELECT * FROM data WHERE data_id = (?)", session["user_id"])

    liste1 = []
    for dict in data:
        final = lookup(dict["action"])
        final["nombre"] = dict["nombre"]
        final["totalprice"] = float(dict["nombre"]) * float(final["price"])
        liste1.append(final)

    totalaction = 0
    for row in liste1:
        totalaction += row["totalprice"]
    actiondumec = []
    for actions in data:
        actiondumec.append(actions["action"])

    return render_template("sell.html", data=liste1, totalaction=totalaction, actiondumec=actiondumec)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
