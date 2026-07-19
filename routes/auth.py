from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from db.connection import query
from models import User

auth_bp = Blueprint("auth", __name__)

DEMO_LOGIN_USERNAME = "staff1"


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        rows = query("SELECT * FROM users WHERE username = %s", (username,))
        if rows and check_password_hash(rows[0]["password_hash"], password):
            login_user(User(rows[0]))
            next_url = request.args.get("next") or url_for("cases.queue")
            return redirect(next_url)
        flash("Invalid username or password.")
    return render_template("login.html", allow_demo_login=current_app.config["ALLOW_DEMO_LOGIN"])


@auth_bp.route("/login/demo", methods=["POST"])
def demo_login():
    """Skips password entry entirely — logs straight in as a fixed demo
    account. Gated behind ALLOW_DEMO_LOGIN, off by default; see app.py."""
    if not current_app.config["ALLOW_DEMO_LOGIN"]:
        flash("Demo login is disabled.")
        return redirect(url_for("auth.login"))
    rows = query("SELECT * FROM users WHERE username = %s", (DEMO_LOGIN_USERNAME,))
    if not rows:
        flash("Demo account not found — run db/seed.py.")
        return redirect(url_for("auth.login"))
    login_user(User(rows[0]))
    return redirect(url_for("cases.queue"))


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Logged out.")
    return redirect(url_for("auth.login"))
