import time
from datetime import datetime
import os
from flask import Flask, request, render_template, flash, url_for, redirect
import mysql.connector
from mysql.connector import pooling, IntegrityError
from dotenv import load_dotenv

# Load .env
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "hostel-db"),  # use docker service name
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "admin@123"),
    "database": os.getenv("DB_NAME", "hostel_db"),
    "port": int(os.getenv("DB_PORT", 3306)),
}

# Create connection pool
POOL_NAME = "hostel_pool"
POOL_SIZE = 5

try:
    cnxpool = pooling.MySQLConnectionPool(pool_name=POOL_NAME, pool_size=POOL_SIZE, **DB_CONFIG)
except mysql.connector.Error as e:
    raise SystemExit(f"Failed to initialize MySQL pool: {e}")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-change-me")


def get_conn():
    return cnxpool.get_connection()

@app.context_processor
def inject_now():
    return {"now": datetime.utcnow}

def init_db_with_retry(retries=5, delay=10):
    for i in range(retries):
        try:
            init_db()
            return
        except Exception as e:
            print(f"DB init failed ({i+1}/{retries}): {e}")
            time.sleep(delay)
    raise SystemExit("Could not initialize DB after retries")
# ✅ Auto-create database tables
def init_db():
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            room VARCHAR(50) NOT NULL,
            phone VARCHAR(50),
            email VARCHAR(255),
            fees_paid TINYINT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()
        print("✅ Students table ensured")
    finally:
        cursor.close()
        conn.close()

# ----------------- Existing routes -----------------
@app.route("/")
def index():
    keyword = request.args.get("keyword", "")
    conn = get_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        if keyword:
            like = f"%{keyword}%"
            sql = """
            SELECT * FROM students
            WHERE CAST(id AS CHAR) LIKE %s OR name LIKE %s OR room LIKE %s OR phone LIKE %s
            ORDER BY created_at DESC
            """
            cursor.execute(sql, (like, like, like, like))
        else:
            cursor.execute("SELECT * FROM students ORDER BY created_at DESC")
        students = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template("index.html", students=students, keyword=keyword)

@app.route("/add", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        try:
            sid = int(request.form["id"])
            name = request.form["name"].strip()
            room = request.form["room"].strip()
            phone = request.form.get("phone", "").strip() or None
            email = request.form.get("email", "").strip() or None
        except (KeyError, ValueError):
            flash("Invalid form data", "danger")
            return redirect(url_for("add_student"))

        conn = get_conn()
        cursor = conn.cursor()
        try:
            query = "INSERT INTO students (id, name, room, phone, email) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(query, (sid, name, room, phone, email))
            conn.commit()
            flash("Student added successfully", "success")
            return redirect(url_for("index"))
        except IntegrityError as e:
            conn.rollback()
            flash(f"Error: {str(e)}", "danger")
            return redirect(url_for("add_student"))
        finally:
            cursor.close()
            conn.close()

    return render_template("add_edit_student.html", action="Add", student=None)

@app.route("/edit/<int:sid>", methods=["GET", "POST"])
def edit_student(sid):
    conn = get_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        if request.method == "POST":
            name = request.form["name"].strip()
            room = request.form["room"].strip()
            phone = request.form.get("phone", "").strip() or None
            email = request.form.get("email", "").strip() or None

            cursor2 = conn.cursor()
            try:
                cursor2.execute("UPDATE students SET name=%s, room=%s, phone=%s, email=%s WHERE id=%s",
                                (name, room, phone, email, sid))
                conn.commit()
                flash("Student updated", "success")
                return redirect(url_for("index"))
            except Exception as e:
                conn.rollback()
                flash(f"Update failed: {e}", "danger")
            finally:
                cursor2.close()

        cursor.execute("SELECT * FROM students WHERE id=%s", (sid,))
        student = cursor.fetchone()
        if not student:
            flash("Student not found", "warning")
            return redirect(url_for("index"))
    finally:
        cursor.close()
        conn.close()

    return render_template("add_edit_student.html", action="Edit", student=student)

@app.route("/pay/<int:sid>")
def pay_fees(sid):
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE students SET fees_paid = 1 WHERE id = %s", (sid,))
        conn.commit()
        flash("Fees marked as paid", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Could not mark fees: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for("index"))

@app.route("/delete/<int:sid>", methods=["GET", "POST"])
def delete_student(sid):
    if request.method == "POST":
        conn = get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM students WHERE id=%s", (sid,))
            conn.commit()
            flash("Student deleted", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Delete failed: {e}", "danger")
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for("index"))

    conn = get_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM students WHERE id=%s", (sid,))
        student = cursor.fetchone()
        if not student:
            flash("Student not found", "warning")
            return redirect(url_for("index"))
    finally:
        cursor.close()
        conn.close()

    return render_template("confirm_delete.html", student=student)

init_db()
init_db_with_retry()

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=5000, debug=debug)

