import os
import re
import hmac
import sqlite3
from contextlib import closing
from pathlib import Path

from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

BASE_DIR = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("PORTFOLIO_DATABASE", BASE_DIR / "portfolio.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "local-dev-key-change-before-deploying")
app.config["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD")
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

DEFAULT_PROFILE = {
    "name": "Alex Morgan",
    "title": "Product designer & creative thinker",
    "bio": "I turn complex ideas into simple, thoughtful digital experiences. I enjoy working at the intersection of design, technology, and human behavior.",
    "email": "hello@example.com",
    "location": "Brooklyn, NY",
    "website": "",
    "skills": "Product design, Prototyping, Design systems, User research",
    "slug": "alex-morgan",
    "theme": "mint",
}


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with closing(get_db()) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT NOT NULL,
                title TEXT NOT NULL,
                bio TEXT NOT NULL,
                email TEXT NOT NULL,
                location TEXT NOT NULL,
                website TEXT NOT NULL DEFAULT '',
                skills TEXT NOT NULL DEFAULT '',
                slug TEXT NOT NULL UNIQUE,
                theme TEXT NOT NULL DEFAULT 'mint'
            );
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                year TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        if db.execute("SELECT 1 FROM profile WHERE id = 1").fetchone() is None:
            db.execute(
                """INSERT INTO profile
                   (id, name, title, bio, email, location, website, skills, slug, theme)
                   VALUES (1, :name, :title, :bio, :email, :location, :website, :skills, :slug, :theme)""",
                DEFAULT_PROFILE,
            )
            db.executemany(
                "INSERT INTO projects (title, description, year, category) VALUES (?, ?, ?, ?)",
                [
                    ("Forma — A calmer way to plan", "A focused planning app that helps small teams turn big goals into clear next steps.", "2025", "Product design"),
                    ("Common Ground", "A neighborhood platform connecting local volunteers with the causes that need them.", "2024", "Brand & digital"),
                ],
            )
        db.commit()


def profile_data():
    with closing(get_db()) as db:
        profile = db.execute("SELECT * FROM profile WHERE id = 1").fetchone()
        projects = db.execute("SELECT * FROM projects ORDER BY created_at DESC, id DESC").fetchall()
    return profile, projects


def clean_text(field, *, required=False, limit=500):
    value = request.form.get(field, "").strip()
    if required and not value:
        raise ValueError(f"{field.replace('_', ' ').capitalize()} is required.")
    if len(value) > limit:
        raise ValueError(f"{field.replace('_', ' ').capitalize()} must be {limit} characters or fewer.")
    return value


def valid_external_url(value):
    return not value or value.startswith(("https://", "http://"))


@app.before_request
def protect_editor_routes():
    is_editor_route = request.path == "/edit" or request.path == "/projects" or request.path.startswith("/projects/")
    if not is_editor_route:
        return None

    password = app.config.get("ADMIN_PASSWORD")
    if not password:
        if os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
            return "Portfolio editor access is not configured.", 503
        return None

    credentials = request.authorization
    supplied_password = credentials.password if credentials else ""
    if supplied_password and hmac.compare_digest(supplied_password, password):
        return None
    return Response(
        "Editor access requires the configured password.",
        401,
        {"WWW-Authenticate": 'Basic realm="Portfolio editor"'},
    )


@app.get("/")
def home():
    profile, projects = profile_data()
    return render_template("index.html", profile=profile, projects=projects)


@app.route("/edit", methods=["GET", "POST"])
def edit_profile():
    profile, projects = profile_data()
    if request.method == "POST":
        try:
            values = {
                "name": clean_text("name", required=True, limit=80),
                "title": clean_text("title", required=True, limit=120),
                "bio": clean_text("bio", required=True, limit=1200),
                "email": clean_text("email", required=True, limit=254),
                "location": clean_text("location", limit=80),
                "website": clean_text("website", limit=300),
                "skills": clean_text("skills", limit=500),
                "slug": clean_text("slug", required=True, limit=50).lower(),
                "theme": request.form.get("theme", "mint"),
            }
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", values["slug"]):
                raise ValueError("Public URL can use lowercase letters, numbers, and hyphens.")
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", values["email"]):
                raise ValueError("Enter a valid email address.")
            if not valid_external_url(values["website"]):
                raise ValueError("Website must start with http:// or https://.")
            if values["theme"] not in {"mint", "lavender", "sunset"}:
                values["theme"] = "mint"
            with closing(get_db()) as db:
                db.execute(
                    """UPDATE profile SET name=:name, title=:title, bio=:bio, email=:email,
                       location=:location, website=:website, skills=:skills, slug=:slug, theme=:theme
                       WHERE id=1""",
                    values,
                )
                db.commit()
            flash("Your profile is up to date.", "success")
            return redirect(url_for("home"))
        except ValueError as error:
            flash(str(error), "error")
        except sqlite3.IntegrityError:
            flash("That public URL is already in use. Choose another one.", "error")
        profile = {**profile, **request.form}
    _, projects = profile_data()
    return render_template("edit.html", profile=profile, projects=projects)


@app.post("/projects")
def add_project():
    try:
        title = clean_text("title", required=True, limit=100)
        description = clean_text("description", required=True, limit=600)
        year = clean_text("year", limit=4)
        category = clean_text("category", limit=60)
        url = clean_text("url", limit=300)
        if year and not re.fullmatch(r"\d{4}", year):
            raise ValueError("Year must be four digits.")
        if not valid_external_url(url):
            raise ValueError("Project link must start with http:// or https://.")
        with closing(get_db()) as db:
            db.execute(
                "INSERT INTO projects (title, description, year, category, url) VALUES (?, ?, ?, ?, ?)",
                (title, description, year, category, url),
            )
            db.commit()
        flash("Project added to your portfolio.", "success")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("home") + "#projects")


@app.post("/projects/<int:project_id>/delete")
def delete_project(project_id):
    with closing(get_db()) as db:
        db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        db.commit()
    flash("Project removed.", "success")
    return redirect(url_for("home") + "#projects")


@app.get("/p/<slug>")
def public_portfolio(slug):
    profile, projects = profile_data()
    if profile["slug"] != slug:
        abort(404)
    return render_template("portfolio.html", profile=profile, projects=projects)


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
