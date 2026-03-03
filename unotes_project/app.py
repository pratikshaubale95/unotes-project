from flask import Flask, render_template, request, redirect, session, send_from_directory
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "unotes_secret_key"

DATABASE = "database.db"
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ---------------- DATABASE CONNECTION ----------------
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- CREATE TABLES IF NOT EXISTS ----------------
def create_tables():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        password TEXT,
        role TEXT DEFAULT 'user'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        subject TEXT,
        branch TEXT,
        year TEXT,
        description TEXT,
        file_path TEXT,
        uploaded_by INTEGER,
        download_count INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()

create_tables()

# ---------------- HOME ----------------
@app.route("/")
def home():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notes ORDER BY download_count DESC LIMIT 5")
    notes = cursor.fetchall()
    conn.close()
    return render_template("index.html", notes=notes)

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        # List of admin emails
        admin_emails = [
            "ubalepratiksha95@gmail.com",
            "susmitapatil457@gmail.com",
            "divyalanghe3008@gmail.com"
        ]

        role = "admin" if email in admin_emails else "user"

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            (name, email, password, role)
        )

        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("register.html")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_role"] = user["role"]
            return redirect("/dashboard")
        else:
            return "Invalid Email or Password"

    return render_template("login.html")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" in session:
        return render_template("dashboard.html", name=session["user_name"])
    return redirect("/login")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- UPLOAD ----------------
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        title = request.form["title"]
        subject = request.form["subject"]
        branch = request.form["branch"]
        year = request.form["year"]
        description = request.form["description"]
        file = request.files["file"]

        if file and file.filename != "":
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notes
                (title, subject, branch, year, description, file_path, uploaded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (title, subject, branch, year, description, filename, session["user_id"]))
            conn.commit()
            conn.close()

            return redirect("/notes")

    return render_template("upload.html")

# ---------------- VIEW NOTES WITH SMART SEARCH ----------------
@app.route("/notes")
def view_notes():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cursor = conn.cursor()
    search = request.args.get("search")

    if search and search.strip() != "":
        search = "%" + search.strip().lower() + "%"
        cursor.execute("""
            SELECT * FROM notes
            WHERE LOWER(title) LIKE ?
            OR LOWER(subject) LIKE ?
            OR LOWER(branch) LIKE ?
            OR LOWER(year) LIKE ?
            ORDER BY id DESC
        """, (search, search, search, search))
    else:
        cursor.execute("SELECT * FROM notes ORDER BY id DESC")

    notes = cursor.fetchall()
    conn.close()

    return render_template("notes.html", notes=notes)

# ---------------- DOWNLOAD ----------------
@app.route("/download/<int:note_id>")
def download(note_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notes WHERE id=?", (note_id,))
    note = cursor.fetchone()

    if not note:
        conn.close()
        return "Note not found"

    filename = note["file_path"]
    full_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    if not os.path.exists(full_path):
        conn.close()
        return "File missing"

    cursor.execute(
        "UPDATE notes SET download_count = download_count + 1 WHERE id=?",
        (note_id,)
    )
    conn.commit()
    conn.close()

    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)

# ---------------- ADMIN PANEL ----------------
@app.route("/admin")
def admin_panel():
    if session.get("user_role") != "admin":
        return "Access Denied"

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    cursor.execute("SELECT * FROM notes")
    notes = cursor.fetchall()

    conn.close()

    return render_template("admin.html", users=users, notes=notes)

# ---------------- DELETE USER ----------------
@app.route("/delete_user/<int:user_id>")
def delete_user(user_id):
    if session.get("user_role") != "admin":
        return "Access Denied"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

    return redirect("/admin")

# ---------------- DELETE NOTE ----------------
@app.route("/delete_note/<int:note_id>")
def delete_note(note_id):
    if session.get("user_role") != "admin":
        return "Access Denied"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notes WHERE id=?", (note_id,))
    note = cursor.fetchone()

    if note:
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], note["file_path"])
        if os.path.exists(file_path):
            os.remove(file_path)

        cursor.execute("DELETE FROM notes WHERE id=?", (note_id,))
        conn.commit()

    conn.close()
    return redirect("/admin")


if __name__ == "__main__":

    app.run(debug=True)
