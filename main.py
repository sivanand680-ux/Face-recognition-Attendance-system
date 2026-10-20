
import os
import time
from flask import Flask, render_template, request, redirect, session, flash
from mysql.connector import IntegrityError
import cv2
import random
import numpy as np
import mysql.connector
import pandas as pd
from flask import send_file
from io import BytesIO
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Response


UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "static/uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "attendance_secret")

# ---------------- MYSQL CONFIG ----------------
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),      # XAMPP default
    "database": os.environ.get("DB_NAME", "smart_attendance"),
    "port": int(os.environ.get("DB_PORT", "3306")),
}
#------------home-------------------
@app.route("/")
def home():
    return redirect("/login_portal")


# ---------------- DB CONNECTION ----------------
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)
#--------------celanup-------
def is_admin_logged_in():
    return "user" in session

def is_teacher_logged_in():
    return "teacher_id" in session

def is_student_logged_in():
    return "student_id" in session
def fetch_courses(cur):
    cur.execute("SELECT course_name FROM courses ORDER BY course_name")
    return cur.fetchall()
def fetch_batches(cur):
    cur.execute("SELECT batch_name FROM batches ORDER BY batch_name")
    return cur.fetchall()
# ---------------- DB SETUP ----------------

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INT AUTO_INCREMENT PRIMARY KEY,
            roll_no VARCHAR(50) UNIQUE,
            name VARCHAR(100),
            course VARCHAR(100),
            email VARCHAR(100) UNIQUE,
            father_name VARCHAR(100),
            father_mobile VARCHAR(15),
            mother_name VARCHAR(100),
            mother_mobile VARCHAR(15),
            batch VARCHAR(20),
            password VARCHAR(100),
            phone VARCHAR(20),
            address TEXT,
            profile_photo VARCHAR(255)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT,
            roll_no VARCHAR(50),
            name VARCHAR(100),
            date DATE,
            time TIME,
            subject_id INT NULL,
            marked_by_teacher_id VARCHAR(50) NULL,
            status VARCHAR(30) DEFAULT 'present'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            teacher_id VARCHAR(50) UNIQUE,
            name VARCHAR(100),
            course VARCHAR(100),
            batch VARCHAR(50),
            password VARCHAR(100),
            email VARCHAR(100) UNIQUE,
            phone VARCHAR(20),
            qualification VARCHAR(120),
            specialization VARCHAR(120),
            experience_years INT DEFAULT 0,
            photo VARCHAR(255)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            course_name VARCHAR(100) UNIQUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS batches (
            id INT AUTO_INCREMENT PRIMARY KEY,
            batch_name VARCHAR(100) UNIQUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS academic_years (
            id INT AUTO_INCREMENT PRIMARY KEY,
            course_id INT,
            batch_id INT,
            year VARCHAR(50)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS teacher_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(100),
            phone VARCHAR(20),
            qualification VARCHAR(120),
            specialization VARCHAR(120),
            experience_years INT DEFAULT 0,
            course VARCHAR(100),
            batch VARCHAR(50),
            password VARCHAR(100),
            photo VARCHAR(255),
            document_file VARCHAR(255),
            status VARCHAR(30) DEFAULT 'pending',
            generated_teacher_id VARCHAR(50),
            admin_remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INT AUTO_INCREMENT PRIMARY KEY,
            subject_name VARCHAR(120),
            course VARCHAR(100),
            batch VARCHAR(50)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS teacher_subjects (
            id INT AUTO_INCREMENT PRIMARY KEY,
            teacher_id VARCHAR(50),
            subject_id INT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS timetable (
            id INT AUTO_INCREMENT PRIMARY KEY,
            course VARCHAR(100),
            batch VARCHAR(50),
            subject_id INT,
            teacher_id VARCHAR(50),
            day_name VARCHAR(20),
            start_time TIME,
            end_time TIME
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT,
            from_date DATE,
            to_date DATE,
            reason TEXT,
            status VARCHAR(30) DEFAULT 'pending',
            admin_remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS portal_settings (
            id INT PRIMARY KEY,
            university_name VARCHAR(150) DEFAULT 'University Portal',
            logo VARCHAR(255),
            background_images TEXT
        )
    """)

    cur.execute("""
        INSERT IGNORE INTO portal_settings (id, university_name)
        VALUES (1, 'University Portal')
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(200),
            description TEXT,
            image VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database ready")


try:
    init_db()
    print("✅ Successfully connected to MySQL database: smart_attendance")
except Exception as _e:
    print(f"⚠️ Database connection notice: {_e}")
#_______________LIVE CAMERA________________________


#----------------------------teacher id------------------------------
import random

def generate_teacher_id(batch_name):
    # Extract letters & numbers from batch (e.g. BCA2023 → BCA23)
    letters = ''.join([c for c in batch_name if c.isalpha()])[:3].upper()
    numbers = ''.join([c for c in batch_name if c.isdigit()])[-2:]

    rand = random.randint(1000, 9999)
    return f"TCH-{letters}{numbers}-{rand}"

#---------------pwecentage_____________
def calculate_attendance_percentage():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT COUNT(DISTINCT date) AS total_days FROM attendance")
    total_days = cur.fetchone()["total_days"] or 1

    cur.execute("""
        SELECT roll_no, name, COUNT(*) AS present_days
        FROM attendance
        GROUP BY roll_no, name
    """)

    records = cur.fetchall()
    cur.close()
    conn.close()

    for r in records:
        r["percentage"] = round((r["present_days"] / total_days) * 100, 2)

    return records
#---------------montly report----------------------
def get_monthly_attendance(batch):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT DATE_FORMAT(a.date, '%Y-%m') AS month,
               COUNT(*) AS total
        FROM attendance a
        JOIN students s ON a.roll_no = s.roll_no
        WHERE s.batch = %s
        GROUP BY month
        ORDER BY month
    """, (batch,))

    data = cur.fetchall()

    cur.close()
    conn.close()

    return data


#-------------------student list same batch----------------------
def get_students_by_batch(batch):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT roll_no, name
        FROM students
        WHERE batch = %s
        ORDER BY roll_no
    """, (batch,))

    students = cur.fetchall()

    cur.close()
    conn.close()

    return students



#---------------------------------------- Admin LOGIN ------------------------------------
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == "admin" and password == "admin":
            session["user"] = "admin"
            session["role"] = "admin"   # add this

            return redirect("/dashboard")

        flash("Invalid admin credentials", "danger")

    return render_template("login.html")

#------------------------login portal-------------------------------------
@app.route("/login_portal")
def login_portal():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # Portal settings
    cur.execute("SELECT * FROM portal_settings WHERE id=1")
    portal = cur.fetchone()

    # News
    cur.execute("SELECT * FROM news ORDER BY created_at DESC")
    news = cur.fetchall()

    cur.close()
    conn.close()

    backgrounds = []
    if portal and portal["background_images"]:
        backgrounds = portal["background_images"].split(",")

    return render_template(
        "login_portal.html",
        university_name=portal["university_name"] if portal else "University Portal",
        logo=portal["logo"] if portal else None,
        backgrounds=backgrounds,
        news=news
    )


#-----------------------------------student login------------------------------
@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        roll_no = request.form["roll_no"]
        email = request.form["email"]

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, name FROM students
            WHERE roll_no=%s AND email=%s
        """, (roll_no, email))

        student = cur.fetchone()
        cur.close()
        conn.close()

        if student:
            session["student_id"] = student[0]
            session["student_name"] = student[1]
            return redirect("/student_dashboard")

        flash("Invalid student credentials", "danger")

    return render_template("student_login.html")
#------------------------------------teacher login---------------------------------
@app.route("/teacher_login", methods=["GET", "POST"])
def teacher_login():
    if request.method == "POST":
        teacher_id = request.form["teacher_id"]
        password = request.form["password"]

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT teacher_id, name, course, batch
            FROM teachers
            WHERE teacher_id=%s AND password=%s
        """, (teacher_id, password))

        teacher = cur.fetchone()

        cur.close()
        conn.close()

        if teacher:
            session["teacher_id"] = teacher["teacher_id"]
            session["teacher_name"] = teacher["name"]
            session["course"] = teacher["course"]
            session["batch"] = teacher["batch"]

            # ADD THIS
            session["role"] = "teacher"

            return redirect("/teacher_dashboard")
        else:
            return render_template("teacher_login.html", error="Invalid credentials")

    return render_template("teacher_login.html")

#---------------------export report_______________________
@app.route("/export_attendance")
def export_attendance():
    if "teacher_id" not in session:
        return redirect("/teacher_login")

    date = request.args.get("date")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if date:
        cur.execute("""
            SELECT a.roll_no, a.name, a.date, a.time
            FROM attendance a
            JOIN students s ON a.roll_no = s.roll_no
            WHERE a.date = %s
              AND s.batch = %s
            ORDER BY a.time
        """, (date, session["batch"]))
    else:
        cur.execute("""
            SELECT a.roll_no, a.name, a.date, a.time
            FROM attendance a
            JOIN students s ON a.roll_no = s.roll_no
            WHERE s.batch = %s
            ORDER BY a.date DESC, a.time DESC
        """, (session["batch"],))

    data = cur.fetchall()

    cur.close()
    conn.close()

    if not data:
        return "No attendance data found for export."

    for row in data:
        row["date"] = row["date"].strftime("%Y-%m-%d") if row["date"] else ""
        row["time"] = str(row["time"]) if row["time"] else ""

    df = pd.DataFrame(data, columns=["roll_no", "name", "date", "time"])

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance")

    output.seek(0)

    return send_file(
        output,
        download_name="attendance.xlsx",
        as_attachment=True
    )

# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM teachers")
    total_teachers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attendance")
    total_attendance = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE DATE(date)=CURDATE()")
    today_attendance = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        total_teachers=total_teachers,
        total_attendance=total_attendance,
        today_attendance=today_attendance
    )
#--------------------------student dashboard__________________________________
@app.route("/student_dashboard")
def student_dashboard():
    if "student_id" not in session:
        return redirect("/student_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM students WHERE id=%s", (session["student_id"],))
    student = cur.fetchone()

    cur.execute("""
        SELECT date, time
        FROM attendance
        WHERE student_id=%s
        ORDER BY date DESC, time DESC
    """, (session["student_id"],))
    records = cur.fetchall()

    cur.execute("SELECT COUNT(DISTINCT date) AS total_days FROM attendance")
    total_days_row = cur.fetchone()
    total_days = total_days_row["total_days"] or 0

    cur.execute("""
        SELECT COUNT(*) AS present_days
        FROM attendance
        WHERE student_id=%s
    """, (session["student_id"],))
    present_days_row = cur.fetchone()
    present_days = present_days_row["present_days"] or 0

    percentage = round((present_days / total_days) * 100, 2) if total_days > 0 else 0

    cur.execute("""
        SELECT 
            sub.subject_name,
            COUNT(a.id) AS present_count
        FROM attendance a
        JOIN subjects sub ON a.subject_id = sub.id
        WHERE a.student_id = %s
        GROUP BY sub.id, sub.subject_name
        ORDER BY sub.subject_name
    """, (session["student_id"],))
    subject_present_rows = cur.fetchall()

    cur.execute("""
        SELECT 
            sub.id,
            sub.subject_name,
            COUNT(a.id) AS total_classes
        FROM subjects sub
        LEFT JOIN attendance a ON sub.id = a.subject_id
        WHERE sub.course = %s AND sub.batch = %s
        GROUP BY sub.id, sub.subject_name
        ORDER BY sub.subject_name
    """, (student["course"], student["batch"]))
    subject_total_rows = cur.fetchall()

    present_map = {row["subject_name"]: row["present_count"] for row in subject_present_rows}

    subject_reports = []
    for row in subject_total_rows:
        subject_name = row["subject_name"]
        total_classes = row["total_classes"] or 0
        present_count = present_map.get(subject_name, 0)
        subject_percentage = round((present_count / total_classes) * 100, 2) if total_classes > 0 else 0

        subject_reports.append({
            "subject_name": subject_name,
            "total_classes": total_classes,
            "present_count": present_count,
            "percentage": subject_percentage
        })

    cur.execute("""
        SELECT
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending_count,
            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved_count,
            SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected_count
        FROM leave_requests
        WHERE student_id = %s
    """, (session["student_id"],))
    leave_row = cur.fetchone()

    leave_summary = {
        "pending": leave_row["pending_count"] or 0,
        "approved": leave_row["approved_count"] or 0,
        "rejected": leave_row["rejected_count"] or 0
    }

    cur.close()
    conn.close()

    profile_photo_url = None
    if student and student.get("profile_photo"):
        profile_photo_url = f"/static/uploads/{student['profile_photo']}"

    return render_template(
        "student_dashboard.html",
        student_name=student["name"] if student else "",
        roll_no=student["roll_no"] if student else "",
        course=student["course"] if student else "",
        batch=student["batch"] if student else "",
        email=student["email"] if student else "",
        phone=student["phone"] if student else "",
        address=student["address"] if student else "",
        profile_photo_url=profile_photo_url,
        percentage=percentage,
        records=records,
        subject_reports=subject_reports,
        leave_summary=leave_summary
    )

#-------------update student profile-----------
@app.route("/update_student_profile", methods=["POST"])
def update_student_profile():
    if "student_id" not in session:
        return redirect("/student_login")

    student_name = request.form["student_name"]
    roll_no = request.form["roll_no"]
    email = request.form["email"]
    phone = request.form["phone"]
    address = request.form["address"]

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE students
        SET name=%s, roll_no=%s, email=%s, phone=%s, address=%s
        WHERE id=%s
    """, (student_name, roll_no, email, phone, address, session["student_id"]))

    conn.commit()
    cur.close()
    conn.close()

    session["student_name"] = student_name
    return redirect("/student_dashboard")
#---------photo update-----------
@app.route("/upload_student_photo", methods=["POST"])
def upload_student_photo():
    if "student_id" not in session:
        return redirect("/student_login")

    photo = request.files.get("photo")

    if photo and photo.filename:
        filename = secure_filename(photo.filename)
        filename = f"{session['student_id']}_{filename}"
        photo.save(os.path.join(UPLOAD_FOLDER, filename))

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE students
            SET profile_photo=%s
            WHERE id=%s
        """, (filename, session["student_id"]))

        conn.commit()
        cur.close()
        conn.close()

    return redirect("/student_dashboard")

#--------------student profile________________
@app.route("/student_profile/<roll_no>")
def student_profile(roll_no):
    if "teacher_id" not in session:
        return redirect("/teacher_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM students WHERE roll_no=%s", (roll_no,))
    student = cur.fetchone()

    cur.execute("""
        SELECT date, time FROM attendance
        WHERE roll_no=%s
        ORDER BY date DESC
    """, (roll_no,))
    attendance = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "student_profile.html",
        student=student,
        attendance=attendance
    )



#------------------------------------teacher dashboard---------------------------------------
@app.route("/teacher_dashboard", methods=["GET", "POST"])
def teacher_dashboard():
    if "teacher_id" not in session:
        return redirect("/teacher_login")

    selected_date = None
    attendance = []

    # ✅ Always create connection & cursor
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # Date-wise attendance (POST)
    if request.method == "POST":
        selected_date = request.form["date"]

        cur.execute("""
    SELECT a.roll_no, a.name, a.date, a.time
    FROM attendance a
    JOIN students s ON a.roll_no = s.roll_no
    WHERE a.date = %s
      AND s.batch = %s
    ORDER BY a.time
""", (selected_date, session["batch"]))


        attendance = cur.fetchall()

    # Attendance percentage
    percentages = calculate_attendance_percentage()

    # Monthly analysis
    monthly_data = get_monthly_attendance(session["batch"])
    students = get_students_by_batch(session["batch"])


    # Students list (same batch)
    students = get_students_by_batch(
        session["batch"]
    )

    cur.close()
    conn.close()

    return render_template(
        "teacher_dashboard.html",
        teacher_name=session["teacher_name"],
        course=session["course"],
        batch=session["batch"],
        attendance=attendance,
        selected_date=selected_date,
        percentages=percentages,
        monthly_data=monthly_data,
        students=students
    )


#----------------------------add teacher-----------------------
@app.route("/add_teacher", methods=["GET", "POST"])
def add_teacher():
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # Fetch courses
    cur.execute("SELECT course_name FROM courses ORDER BY course_name")
    courses = cur.fetchall()

    # Fetch batches
    cur.execute("SELECT batch_name FROM batches ORDER BY batch_name")
    batches = cur.fetchall()

    if request.method == "POST":
        name = request.form["name"]
        course = request.form["course"]
        batch = request.form["batch"]
        password = request.form["password"]

        teacher_id = generate_teacher_id(batch)

        cur.execute("""
            INSERT INTO teachers (teacher_id, name, course, batch, password)
            VALUES (%s, %s, %s, %s, %s)
        """, (teacher_id, name, course, batch, password))

        conn.commit()

        # ✅ STORE FOR POPUP
        session["teacher_created"] = True
        session["new_teacher_id"] = teacher_id

        cur.close()
        conn.close()

        return redirect("/add_teacher")

    cur.close()
    conn.close()

    return render_template(
        "add_teacher.html",
        courses=courses,
        batches=batches
    )
#====================teacher logout================
@app.route("/teacher_logout")
def teacher_logout():
    session.clear()
    return redirect("/teacher_login")

#==============POP==============
@app.route("/clear_teacher_popup")
def clear_teacher_popup():
    session.pop("teacher_created", None)
    session.pop("new_teacher_id", None)
    return "", 204

@app.route("/clear_student_popup")
def clear_student_popup():
    session.pop("student_registered", None)
    session.pop("registered_student_name", None)
    return "", 204


# ---------------- FACE DUPLICATE CHECK ----------------
def detect_existing_face():
    if not os.path.exists("trainer/trainer.yml"):
        return None

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read("trainer/trainer.yml")

    detector = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cam.isOpened():
        cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        return None

    matched_name = None
    attempts = 0

    while attempts < 50:
        ret, img = cam.read()
        if not ret:
            attempts += 1
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            face = gray[y:y+h, x:x+w]
            face = cv2.resize(face, (200, 200))

            student_id, conf = recognizer.predict(face)

            if conf < 65:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT name FROM students WHERE id=%s", (student_id,))
                row = cur.fetchone()
                cur.close()
                conn.close()

                if row:
                    matched_name = row[0]
                    break

        if matched_name:
            break

        cv2.imshow("Duplicate Face Check", img)
        if cv2.waitKey(1) == 27:
            break

        attempts += 1

    cam.release()
    cv2.destroyAllWindows()
    return matched_name


# ---------------- FACE CAPTURE ----------------
def capture_faces(student_id, student_name):
    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cam.isOpened():
        cam = cv2.VideoCapture(0)

    if not cam.isOpened():
        print("❌ Camera not opening")
        cam.release()
        return False

    detector = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    os.makedirs(f"dataset/{student_id}", exist_ok=True)

    count = 0
    deadline = time.monotonic() + 30

    try:
        while count < 30 and time.monotonic() < deadline:
            ret, img = cam.read()
            if not ret or img is None:
                if cv2.waitKey(1) == 27:
                    break
                continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(gray, 1.3, 5)

            for (x, y, w, h) in faces:
                face = gray[y:y+h, x:x+w]
                face = cv2.resize(face, (200, 200))

                next_count = count + 1
                if not cv2.imwrite(f"dataset/{student_id}/{next_count}.jpg", face):
                    continue
                count = next_count

                # Premium UI
                cv2.rectangle(img, (x,y), (x+w,y+h), (0,255,0), 2)

                cv2.putText(img, student_name, (x, y-40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)

                cv2.putText(img, f"{count}/30", (x, y-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)

                if count >= 30:
                    break

            cv2.putText(img, "Face Registration In Progress",
                        (20,40), cv2.FONT_HERSHEY_SIMPLEX,
                        1, (255,255,255), 2)

            cv2.imshow("Smart Attendance System", img)

            if cv2.waitKey(1) == 27:
                break

    finally:
        cam.release()
        cv2.destroyAllWindows()

    return count >= 30
# ---------------- TRAIN MODEL ----------------
def train_model():
    try:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
    except:
        print("❌ Install opencv-contrib-python")
        return

    faces, ids = [], []

    if not os.path.exists("dataset"):
        return

    for folder in os.listdir("dataset"):
        for img in os.listdir(f"dataset/{folder}"):
            path = f"dataset/{folder}/{img}"
            image = cv2.imread(path, 0)

            if image is None:
                continue

            faces.append(image)
            ids.append(int(folder))

    if len(faces) == 0:
        print("No faces found")
        return

    recognizer.train(faces, np.array(ids))
    os.makedirs("trainer", exist_ok=True)
    recognizer.save("trainer/trainer.yml")
# ---------------- REGISTER STUDENT ----------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT course_name FROM courses ORDER BY course_name")
    courses = cur.fetchall()

    cur.execute("SELECT batch_name FROM batches ORDER BY batch_name")
    batches = cur.fetchall()

    if request.method == "POST":
        roll_no = request.form["roll_no"].strip()
        name = request.form["name"].strip()
        email = request.form["email"].strip()
        course = request.form["course"].strip()
        batch = request.form["batch"].strip()

        cur.execute("SELECT id FROM students WHERE roll_no=%s OR email=%s", (roll_no, email))
        existing = cur.fetchone()
        if existing:
            flash("Student with this roll number or email already exists.", "danger")
            cur.close()
            conn.close()
            return render_template("register.html", courses=courses, batches=batches)

        cur.close()
        conn.close()

        duplicate_name = detect_existing_face()
        if duplicate_name:
            flash(f"This face is already registered as '{duplicate_name}'.", "danger")
            return render_template("register.html", courses=courses, batches=batches)

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO students (roll_no, name, email, course, batch)
                VALUES (%s, %s, %s, %s, %s)
            """, (roll_no, name, email, course, batch))

            conn.commit()
            student_id = cur.lastrowid

            cur.close()
            conn.close()

            if not capture_faces(student_id, name):
                flash("Student was added, but face capture did not complete. Retry from Manage Students.", "warning")
                return redirect("/manage_students")

            train_model()

            session["student_registered"] = True
            session["registered_student_name"] = name

            return redirect("/register")

        except IntegrityError as e:
            conn.rollback()

            if "roll_no" in str(e):
                flash(f"Roll number '{roll_no}' is already registered.", "danger")
            elif "email" in str(e):
                flash(f"Email '{email}' is already registered.", "danger")
            else:
                flash("Student already exists.", "danger")

            cur.close()
            conn.close()

    return render_template("register.html", courses=courses, batches=batches)

#----------------faecdone-------------------------
# ---------------- ATTENDANCE ----------------
@app.route("/attendance")
def attendance():
    if "user" not in session and "teacher_id" not in session:
        return redirect("/")

    is_teacher = session.get("role") == "teacher"

    if not os.path.exists("trainer/trainer.yml"):
        flash("Face recognition model is not trained yet. Please register students and capture faces first.", "danger")
        return redirect("/teacher_sessions" if is_teacher else "/dashboard")

    if is_teacher and (not session.get("active_subject_id") or not session.get("active_batch")):
        if session.get("batch"):
            session["active_batch"] = session["batch"]
            if not session.get("active_subject_id"):
                try:
                    conn_sub = get_db_connection()
                    cur_sub = conn_sub.cursor(dictionary=True)
                    cur_sub.execute("""
                        SELECT s.id, s.subject_name 
                        FROM teacher_subjects ts 
                        JOIN subjects s ON ts.subject_id = s.id 
                        WHERE ts.teacher_id = %s LIMIT 1
                    """, (session.get("teacher_id"),))
                    sub_row = cur_sub.fetchone()
                    if sub_row:
                        session["active_subject_id"] = sub_row["id"]
                        session["active_subject_name"] = sub_row["subject_name"]
                    cur_sub.close()
                    conn_sub.close()
                except Exception:
                    pass
        if not session.get("active_batch"):
            flash("Please start attendance from My Sessions.", "warning")
            return redirect("/teacher_sessions")

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read("trainer/trainer.yml")

    detector = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cam.isOpened():
        cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        flash("Unable to open camera.", "danger")
        return redirect("/teacher_sessions" if is_teacher else "/dashboard")

    conn = get_db_connection()
    cur = conn.cursor()

    marked_students = []
    marked_student_ids = set()
    status_message = "Point face at camera (ANY KEY = Mark | ESC = Close)"
    status_color = (255, 255, 255)
    consecutive_frames = 0
    last_detected_id = None

    while True:
        ret, img = cam.read()
        if not ret or img is None:
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, 1.3, 5)

        h, w = img.shape[:2]

        cv2.rectangle(img, (0, 0), (w, 90), (15, 23, 42), -1)
        cv2.rectangle(img, (0, h - 55), (w, h), (15, 23, 42), -1)
        cv2.rectangle(img, (w - 300, 90), (w, h - 55), (20, 30, 48), -1)

        cv2.putText(
            img,
            "SMART ATTENDANCE CAMERA",
            (20, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        if is_teacher:
            top_text = f"Subject: {session.get('active_subject_name', 'General')} | Batch: {session.get('active_batch', 'N/A')}"
        else:
            top_text = "Admin Attendance Mode - Any Student Recognized Can Mark"

        cv2.putText(
            img,
            top_text,
            (20, 64),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2
        )

        cv2.putText(
            img,
            "ANY KEY = Mark Attendance | ESC / Q = Close",
            (20, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (220, 220, 220),
            2
        )

        cv2.putText(
            img,
            f"Status: {status_message}",
            (w - 540, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            status_color,
            2
        )

        cv2.putText(
            img,
            f"Marked: {len(marked_students)}",
            (w - 280, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        cv2.putText(
            img,
            "Marked Students",
            (w - 280, 150),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2
        )

        panel_y = 185
        recent_marked = marked_students[-10:]
        for idx, student_name in enumerate(recent_marked, start=1):
            cv2.putText(
                img,
                f"{idx}. {student_name}",
                (w - 280, panel_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (220, 220, 220),
                2
            )
            panel_y += 28

        current_candidate = None

        for (x, y, fw, fh) in faces:
            face = gray[y:y+fh, x:x+fw]
            face = cv2.resize(face, (200, 200))

            student_id, conf = recognizer.predict(face)
            confidence_pct = max(0, min(100, round(100 - conf, 1)))
            confidence_text = f"Confidence: {confidence_pct}%"

            if conf < 70:
                cur.execute(
                    "SELECT name, roll_no, batch FROM students WHERE id=%s",
                    (student_id,)
                )
                row = cur.fetchone()

                if not row:
                    continue

                name, roll_no, student_batch = row

                if is_teacher and session.get("active_batch") and student_batch != session.get("active_batch"):
                    cv2.rectangle(img, (x, y), (x + fw, y + fh), (0, 165, 255), 2)
                    cv2.putText(img, name, (x, y - 28),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 165, 255), 2)
                    cv2.putText(img, "Not in this batch", (x, y - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 165, 255), 2)
                    cv2.putText(img, confidence_text, (x, y + fh + 22),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 165, 255), 2)
                    status_message = f"{name} recognized but not in this batch"
                    status_color = (0, 165, 255)
                    continue

                if student_id in marked_student_ids:
                    cv2.rectangle(img, (x, y), (x + fw, y + fh), (0, 255, 255), 2)
                    cv2.putText(img, name, (x, y - 28),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
                    cv2.putText(img, "Marked in this session", (x, y - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 255, 255), 2)
                    cv2.putText(img, confidence_text, (x, y + fh + 22),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
                    status_message = f"{name} already marked"
                    status_color = (0, 255, 255)
                    continue

                # Eligible candidate recognized!
                current_candidate = (student_id, name, roll_no, student_batch)
                cv2.rectangle(img, (x, y), (x + fw, y + fh), (0, 255, 0), 2)
                cv2.putText(img, name, (x, y - 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
                cv2.putText(img, "Press ANY KEY to mark", (x, y - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 255, 0), 2)
                cv2.putText(img, confidence_text, (x, y + fh + 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

                status_message = f"{name} recognized! Press ANY KEY to confirm"
                status_color = (0, 255, 0)
                break

            else:
                cv2.rectangle(img, (x, y), (x + fw, y + fh), (0, 0, 255), 2)
                cv2.putText(img, "Unknown Face", (x, y - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 255), 2)
                cv2.putText(img, confidence_text, (x, y + fh + 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
                status_message = "Unknown face detected"
                status_color = (0, 0, 255)

        if current_candidate:
            if last_detected_id == current_candidate[0]:
                consecutive_frames += 1
            else:
                last_detected_id = current_candidate[0]
                consecutive_frames = 1
        else:
            consecutive_frames = 0
            last_detected_id = None

        cv2.imshow("Attendance", img)

        key = cv2.waitKey(1) & 0xFF

        trigger_mark = False

        if key != 255:
            # A key was pressed!
            if key in (27, ord('q'), ord('Q')):
                break
            else:
                # ANY other key marks attendance!
                trigger_mark = True
        elif consecutive_frames >= 15:
            # Auto-mark if recognized face held steadily for ~0.5 second
            trigger_mark = True
            consecutive_frames = 0

        if trigger_mark and current_candidate:
            student_id, name, roll_no, student_batch = current_candidate

            now = datetime.now()
            date = now.date()
            time_str = now.strftime("%H:%M:%S")

            if is_teacher and session.get("active_subject_id"):
                cur.execute("""
                    SELECT id FROM attendance
                    WHERE student_id=%s AND date=%s AND subject_id=%s
                """, (student_id, date, session.get("active_subject_id")))
            else:
                cur.execute("""
                    SELECT id FROM attendance
                    WHERE student_id=%s AND date=%s
                """, (student_id, date))

            existing = cur.fetchone()

            if existing:
                status_message = f"{name} already marked today"
                status_color = (0, 255, 255)
                marked_student_ids.add(student_id)
                if name not in marked_students:
                    marked_students.append(name)
                current_candidate = None
                continue

            if is_teacher and session.get("active_subject_id"):
                cur.execute("""
                    INSERT INTO attendance
                    (student_id, roll_no, name, date, time, subject_id, marked_by_teacher_id, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    student_id,
                    roll_no,
                    name,
                    date,
                    time_str,
                    session.get("active_subject_id"),
                    session.get("teacher_id"),
                    "present"
                ))
            elif is_teacher:
                cur.execute("""
                    INSERT INTO attendance
                    (student_id, roll_no, name, date, time, marked_by_teacher_id, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    student_id,
                    roll_no,
                    name,
                    date,
                    time_str,
                    session.get("teacher_id"),
                    "present"
                ))
            else:
                cur.execute("""
                    INSERT INTO attendance (student_id, roll_no, name, date, time, status)
                    VALUES (%s, %s, %s, %s, %s, 'present')
                """, (student_id, roll_no, name, date, time_str))

            conn.commit()
            marked_student_ids.add(student_id)
            marked_students.append(name)
            status_message = f"{name} marked successfully"
            status_color = (0, 255, 0)

            popup = img.copy()
            overlay = popup.copy()
            cv2.rectangle(overlay, (140, 180), (w - 140, h - 180), (16, 185, 129), -1)
            cv2.addWeighted(overlay, 0.22, popup, 0.78, 0, popup)
            cv2.rectangle(popup, (160, 210), (w - 160, h - 210), (22, 163, 74), -1)

            cv2.putText(popup, "ATTENDANCE MARKED", (190, 280),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
            cv2.putText(popup, f"Student: {name}", (190, 335),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.82, (255, 255, 255), 2)
            cv2.putText(popup, f"Roll No: {roll_no}", (190, 375),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.72, (240, 255, 240), 2)
            cv2.putText(popup, "Continue scanning...", (190, 420),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.72, (240, 255, 240), 2)

            cv2.imshow("Attendance", popup)
            cv2.waitKey(900)
            current_candidate = None

    cam.release()
    cv2.destroyAllWindows()
    cur.close()
    conn.close()

    if marked_students:
        flash(f"Attendance marked for: {', '.join(marked_students)}", "success")
    else:
        flash("Camera closed without marking attendance.", "info")

    if is_teacher:
        return redirect("/teacher_sessions")
    return redirect("/dashboard")

#-----------------CLEAR ACTIVE SESSION-------------
@app.route("/clear_active_session")
def clear_active_session():
    session.pop("active_timetable_id", None)
    session.pop("active_subject_id", None)
    session.pop("active_subject_name", None)
    session.pop("active_batch", None)
    session.pop("active_course", None)
    return redirect("/teacher_sessions")

#=====================Attendance table++++++++++++++++========================
@app.route("/attendance_table")
def attendance_table():
    if "user" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    # Total distinct attendance days
    cur.execute("SELECT COUNT(DISTINCT date) FROM attendance")
    total_days = cur.fetchone()[0] or 0

    # Attendance records with roll number
    cur.execute("""
        SELECT s.roll_no, s.name, a.student_id, a.date, a.time
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        ORDER BY a.date DESC, a.time DESC
    """)
    records = cur.fetchall()

    # Calculate attendance count per student
    cur.execute("""
        SELECT student_id, COUNT(*) 
        FROM attendance
        GROUP BY student_id
    """)
    counts = cur.fetchall()

    cur.close()
    conn.close()

    # Convert counts to dictionary
    attendance_count = {sid: count for sid, count in counts}

    # Final data with percentage
    final_records = []
    for row in records:
        roll_no, name, student_id, date, time = row
        present_days = attendance_count.get(student_id, 0)
        percentage = round((present_days / total_days) * 100, 2) if total_days > 0 else 0
        final_records.append((roll_no, name, date, time, percentage))

    return render_template(
        "attendance_table.html",
        records=final_records
    )
#-----------------------------teaher register-------------
@app.route("/teacher_register", methods=["GET", "POST"])
def teacher_register():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT course_name FROM courses ORDER BY course_name")
    courses = cur.fetchall()

    cur.execute("SELECT batch_name FROM batches ORDER BY batch_name")
    batches = cur.fetchall()

    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip()
        phone = request.form["phone"].strip()
        qualification = request.form["qualification"].strip()
        specialization = request.form["specialization"].strip()
        experience_years = request.form["experience_years"].strip() or 0
        course = request.form["course"].strip()
        batch = request.form["batch"].strip()
        password = request.form["password"].strip()

        photo = request.files.get("photo")
        document = request.files.get("document")

        photo_name = None
        document_name = None

        if photo and photo.filename:
            photo_name = secure_filename(photo.filename)
            photo.save(os.path.join(UPLOAD_FOLDER, photo_name))

        if document and document.filename:
            document_name = secure_filename(document.filename)
            document.save(os.path.join(UPLOAD_FOLDER, document_name))

        try:
            cur.execute("""
                INSERT INTO teacher_requests
                (name, email, phone, qualification, specialization, experience_years, course, batch, password, photo, document_file)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                name,
                email,
                phone,
                qualification,
                specialization,
                experience_years,
                course,
                batch,
                password,
                photo_name,
                document_name
            ))
            conn.commit()
            flash("Registration request submitted. Wait for admin approval.", "success")
            return redirect("/teacher_register")

        except IntegrityError:
            conn.rollback()
            flash("Email already exists in teacher requests.", "danger")

    cur.close()
    conn.close()
    return render_template("teacher_register.html", courses=courses, batches=batches)

#----------------- teacher reques-----------------
@app.route("/admin_teacher_requests")
def admin_teacher_requests():
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT * FROM teacher_requests
        ORDER BY created_at DESC
    """)
    requests_data = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("admin_teacher_requests.html", requests_data=requests_data)
#----------------approve request---------------
@app.route("/approve_teacher_request/<int:request_id>", methods=["POST"])
def approve_teacher_request(request_id):
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM teacher_requests WHERE id=%s", (request_id,))
    req = cur.fetchone()

    if not req or req["status"] != "pending":
        cur.close()
        conn.close()
        flash("Invalid teacher request.", "danger")
        return redirect("/admin_teacher_requests")

    teacher_id = generate_teacher_id(req["batch"])

    try:
        cur.execute("""
            INSERT INTO teachers
            (teacher_id, name, course, batch, password, email, phone, qualification, specialization, experience_years, photo)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            teacher_id,
            req["name"],
            req["course"],
            req["batch"],
            req["password"],
            req["email"],
            req["phone"],
            req["qualification"],
            req["specialization"],
            req["experience_years"],
            req["photo"]
        ))

        cur.execute("""
            UPDATE teacher_requests
            SET status='approved', generated_teacher_id=%s
            WHERE id=%s
        """, (teacher_id, request_id))

        conn.commit()
        flash(f"Teacher approved successfully. Teacher ID: {teacher_id}", "success")

    except IntegrityError:
        conn.rollback()
        flash("Approval failed due to duplicate teacher data.", "danger")

    cur.close()
    conn.close()
    return redirect("/admin_teacher_requests")


#--------------reject request-----------------------------
@app.route("/reject_teacher_request/<int:request_id>", methods=["POST"])
def reject_teacher_request(request_id):
    if "user" not in session:
        return redirect("/admin_login")

    remark = request.form.get("admin_remark", "").strip()

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE teacher_requests
        SET status='rejected', admin_remark=%s
        WHERE id=%s
    """, (remark, request_id))

    conn.commit()
    cur.close()
    conn.close()

    flash("Teacher request rejected.", "warning")
    return redirect("/admin_teacher_requests")
#--------------TEACHER REQUEST STATUS--------------------
@app.route("/teacher_request_status", methods=["GET", "POST"])
def teacher_request_status():
    request_data = None

    if request.method == "POST":
        email = request.form["email"].strip()

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT name, email, status, generated_teacher_id, admin_remark, created_at
            FROM teacher_requests
            WHERE email=%s
            ORDER BY created_at DESC
            LIMIT 1
        """, (email,))

        request_data = cur.fetchone()

        cur.close()
        conn.close()

        if not request_data:
            flash("No teacher request found for this email.", "danger")

    return render_template("teacher_request_status.html", request_data=request_data)

#--------------------- manage subject----------------------
@app.route("/manage_subjects", methods=["GET", "POST"])
def manage_subjects():
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT course_name FROM courses ORDER BY course_name")
    courses = cur.fetchall()

    cur.execute("SELECT batch_name FROM batches ORDER BY batch_name")
    batches = cur.fetchall()

    if request.method == "POST":
        subject_name = request.form["subject_name"].strip()
        course = request.form["course"].strip()
        batch = request.form["batch"].strip()

        cur.execute("""
            INSERT INTO subjects (subject_name, course, batch)
            VALUES (%s, %s, %s)
        """, (subject_name, course, batch))
        conn.commit()

        flash("Subject added successfully.", "success")
        cur.close()
        conn.close()
        return redirect("/manage_subjects")

    cur.execute("""
        SELECT * FROM subjects
        ORDER BY course, batch, subject_name
    """)
    subjects = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "manage_subjects.html",
        subjects=subjects,
        courses=courses,
        batches=batches
    )

#--------------------------- teacher subject----------------
@app.route("/assign_subjects", methods=["GET", "POST"])
def assign_subjects():
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        teacher_id = request.form["teacher_id"]
        subject_id = request.form["subject_id"]

        cur.execute("""
            INSERT INTO teacher_subjects (teacher_id, subject_id)
            VALUES (%s, %s)
        """, (teacher_id, subject_id))
        conn.commit()
        flash("Subject assigned to teacher.", "success")

    cur.execute("SELECT teacher_id, name, course, batch FROM teachers ORDER BY name")
    teachers = cur.fetchall()

    cur.execute("SELECT * FROM subjects ORDER BY subject_name")
    subjects = cur.fetchall()

    cur.execute("""
        SELECT ts.id, t.name AS teacher_name, t.teacher_id, s.subject_name, s.course, s.batch
        FROM teacher_subjects ts
        JOIN teachers t ON ts.teacher_id = t.teacher_id
        JOIN subjects s ON ts.subject_id = s.id
        ORDER BY t.name
    """)
    assignments = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "assign_subjects.html",
        teachers=teachers,
        subjects=subjects,
        assignments=assignments
    )
#-------------create timetable-------------
@app.route("/manage_timetable", methods=["GET", "POST"])
def manage_timetable():
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT course_name FROM courses ORDER BY course_name")
    courses = cur.fetchall()

    cur.execute("SELECT batch_name FROM batches ORDER BY batch_name")
    batches = cur.fetchall()

    cur.execute("""
        SELECT id, subject_name, course, batch
        FROM subjects
        ORDER BY subject_name
    """)
    subjects = cur.fetchall()

    cur.execute("""
        SELECT teacher_id, name, course, batch
        FROM teachers
        ORDER BY name
    """)
    teachers = cur.fetchall()

    if request.method == "POST":
        course = request.form["course"].strip()
        batch = request.form["batch"].strip()
        subject_id = request.form["subject_id"].strip()
        teacher_id = request.form["teacher_id"].strip()
        day_name = request.form["day_name"].strip()
        start_time = request.form["start_time"].strip()
        end_time = request.form["end_time"].strip()

        cur.execute("""
            INSERT INTO timetable (course, batch, subject_id, teacher_id, day_name, start_time, end_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (course, batch, subject_id, teacher_id, day_name, start_time, end_time))
        conn.commit()

        cur.close()
        conn.close()
        flash("Timetable created successfully.", "success")
        return redirect("/manage_timetable")

    cur.execute("""
        SELECT tt.id, tt.course, tt.batch, tt.day_name, tt.start_time, tt.end_time,
               s.subject_name, t.name AS teacher_name, t.teacher_id
        FROM timetable tt
        JOIN subjects s ON tt.subject_id = s.id
        JOIN teachers t ON tt.teacher_id = t.teacher_id
        ORDER BY tt.day_name, tt.start_time
    """)
    timetable_rows = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "manage_timetable.html",
        courses=courses,
        batches=batches,
        subjects=subjects,
        teachers=teachers,
        timetable_rows=timetable_rows
    )

#-------------DELETE TIMETABLE------------
@app.route("/delete_timetable/<int:id>")
def delete_timetable(id):
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM timetable WHERE id=%s", (id,))
    conn.commit()
    cur.close()
    conn.close()

    flash("Timetable entry deleted.", "success")
    return redirect("/manage_timetable")

#----------------teacher session timetable-------------
@app.route("/teacher_sessions")
def teacher_sessions():
    if "teacher_id" not in session:
        return redirect("/teacher_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT tt.id, tt.day_name, tt.start_time, tt.end_time,
               tt.course, tt.batch, s.subject_name, s.id AS subject_id
        FROM timetable tt
        JOIN subjects s ON tt.subject_id = s.id
        WHERE tt.teacher_id = %s
        ORDER BY tt.day_name, tt.start_time
    """, (session["teacher_id"],))

    sessions = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("teacher_sessions.html", sessions=sessions)
#--------------------start teacher attendance---------
@app.route("/start_teacher_attendance/<int:timetable_id>")
def start_teacher_attendance(timetable_id):
    if "teacher_id" not in session:
        return redirect("/teacher_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT tt.*, s.id AS subject_id, s.subject_name
        FROM timetable tt
        JOIN subjects s ON tt.subject_id = s.id
        WHERE tt.id = %s AND tt.teacher_id = %s
    """, (timetable_id, session["teacher_id"]))

    row = cur.fetchone()

    cur.close()
    conn.close()

    if not row:
        flash("Invalid timetable session.", "danger")
        return redirect("/teacher_sessions")

    session["active_timetable_id"] = row["id"]
    session["active_subject_id"] = row["subject_id"]
    session["active_subject_name"] = row["subject_name"]
    session["active_batch"] = row["batch"]
    session["active_course"] = row["course"]

    return redirect("/attendance")

#-----------------low attendance-----------------
@app.route("/low_attendance")
def low_attendance():
    if "user" not in session and "teacher_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT COUNT(DISTINCT date) AS total_days FROM attendance")
    total_days = cur.fetchone()["total_days"] or 1

    cur.execute("""
        SELECT s.roll_no, s.name, s.course, s.batch, COUNT(a.id) AS present_days
        FROM students s
        LEFT JOIN attendance a ON s.id = a.student_id
        GROUP BY s.id, s.roll_no, s.name, s.course, s.batch
    """)
    rows = cur.fetchall()

    for row in rows:
        row["percentage"] = round((row["present_days"] / total_days) * 100, 2)

    low_students = [r for r in rows if r["percentage"] < 75]

    cur.close()
    conn.close()

    return render_template("low_attendance.html", students=low_students)
#---------------teacher low attendance----------
@app.route("/teacher_low_attendance")
def teacher_low_attendance():
    if "teacher_id" not in session:
        return redirect("/teacher_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT COUNT(DISTINCT a.date) AS total_days
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE s.batch = %s
    """, (session["batch"],))
    total_days_row = cur.fetchone()
    total_days = total_days_row["total_days"] or 0

    cur.execute("""
        SELECT s.id, s.roll_no, s.name, s.course, s.batch,
               COUNT(a.id) AS present_days
        FROM students s
        LEFT JOIN attendance a ON s.id = a.student_id
        WHERE s.batch = %s
        GROUP BY s.id, s.roll_no, s.name, s.course, s.batch
        ORDER BY s.roll_no
    """, (session["batch"],))
    rows = cur.fetchall()

    for row in rows:
        row["percentage"] = round((row["present_days"] / total_days) * 100, 2) if total_days > 0 else 0

    low_students = [row for row in rows if row["percentage"] < 75]

    cur.close()
    conn.close()

    return render_template(
        "teacher_low_attendance.html",
        students=low_students,
        total_days=total_days,
        batch=session["batch"]
    )
#--------------subject attendnace-----
@app.route("/subject_attendance_report")
def subject_attendance_report():
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            sub.subject_name,
            sub.course,
            sub.batch,
            COUNT(a.id) AS total_marked
        FROM subjects sub
        LEFT JOIN attendance a ON sub.id = a.subject_id
        GROUP BY sub.id, sub.subject_name, sub.course, sub.batch
        ORDER BY sub.course, sub.batch, sub.subject_name
    """)
    report_rows = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("subject_attendance_report.html", report_rows=report_rows)
#------------teacher subject report--------
@app.route("/teacher_subject_report")
def teacher_subject_report():
    if "teacher_id" not in session:
        return redirect("/teacher_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            sub.subject_name,
            sub.course,
            sub.batch,
            COUNT(a.id) AS total_marked
        FROM teacher_subjects ts
        JOIN subjects sub ON ts.subject_id = sub.id
        LEFT JOIN attendance a
            ON a.subject_id = sub.id
           AND a.marked_by_teacher_id = ts.teacher_id
        WHERE ts.teacher_id = %s
        GROUP BY sub.id, sub.subject_name, sub.course, sub.batch
        ORDER BY sub.subject_name
    """, (session["teacher_id"],))

    report_rows = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("teacher_subject_report.html", report_rows=report_rows)

#-------------------leave request----------------
@app.route("/leave_request", methods=["GET", "POST"])
def leave_request():
    if "student_id" not in session:
        return redirect("/student_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        from_date = request.form["from_date"]
        to_date = request.form["to_date"]
        reason = request.form["reason"]

        cur.execute("""
            INSERT INTO leave_requests (student_id, from_date, to_date, reason)
            VALUES (%s, %s, %s, %s)
        """, (session["student_id"], from_date, to_date, reason))
        conn.commit()
        flash("Leave request submitted.", "success")

    cur.execute("""
        SELECT * FROM leave_requests
        WHERE student_id=%s
        ORDER BY created_at DESC
    """, (session["student_id"],))
    requests_data = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("leave_request.html", requests_data=requests_data)
#----------------manage leave request---------------
@app.route("/manage_leave_requests")
def manage_leave_requests():
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            lr.*,
            s.name,
            s.roll_no,
            COALESCE(s.course, 'N/A') AS course,
            COALESCE(s.batch, 'N/A') AS batch
        FROM leave_requests lr
        JOIN students s ON lr.student_id = s.id
        ORDER BY lr.created_at DESC
    """)
    requests_data = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("manage_leave_requests.html", requests_data=requests_data)

#--------------------approveeee leave-----------
@app.route("/approve_leave/<int:leave_id>", methods=["POST"])
def approve_leave(leave_id):
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE leave_requests
        SET status='approved'
        WHERE id=%s
    """, (leave_id,))

    conn.commit()
    cur.close()
    conn.close()

    flash("Leave approved.", "success")
    return redirect("/manage_leave_requests")
#---------reject leave reqquest------
@app.route("/reject_leave/<int:leave_id>", methods=["POST"])
def reject_leave(leave_id):
    if "user" not in session:
        return redirect("/admin_login")

    remark = request.form.get("admin_remark", "").strip()

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE leave_requests
        SET status='rejected', admin_remark=%s
        WHERE id=%s
    """, (remark, leave_id))

    conn.commit()
    cur.close()
    conn.close()

    flash("Leave request rejected.", "warning")
    return redirect("/manage_leave_requests")

#---------manage student----------
@app.route("/manage_students")
def manage_students():
    if not is_admin_logged_in():
        return redirect("/admin_login")

    selected_course = request.args.get("course", "").strip()
    selected_batch = request.args.get("batch", "").strip()

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    courses = fetch_courses(cur)
    batches = fetch_batches(cur)

    query = """
        SELECT id, roll_no, name, email, course, batch, phone
        FROM students
        WHERE 1=1
    """
    params = []

    if selected_course:
        query += " AND course = %s"
        params.append(selected_course)

    if selected_batch:
        query += " AND batch = %s"
        params.append(selected_batch)

    query += " ORDER BY roll_no"

    cur.execute(query, tuple(params))
    students = cur.fetchall()

    for student in students:
        dataset_path = os.path.join("dataset", str(student["id"]))
        has_face = os.path.isdir(dataset_path) and len(os.listdir(dataset_path)) >= 30
        student["face_registered"] = has_face

    cur.close()
    conn.close()

    return render_template(
        "manage_students.html",
        students=students,
        courses=courses,
        batches=batches,
        selected_course=selected_course,
        selected_batch=selected_batch
    )

#--------------edit studet-------------------
@app.route("/edit_student/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id):
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT course_name FROM courses ORDER BY course_name")
    courses = cur.fetchall()

    cur.execute("SELECT batch_name FROM batches ORDER BY batch_name")
    batches = cur.fetchall()

    if request.method == "POST":
        roll_no = request.form["roll_no"].strip()
        name = request.form["name"].strip()
        email = request.form["email"].strip()
        course = request.form["course"].strip()
        batch = request.form["batch"].strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        try:
            cur.execute("""
                UPDATE students
                SET roll_no=%s,
                    name=%s,
                    email=%s,
                    course=%s,
                    batch=%s,
                    phone=%s,
                    address=%s
                WHERE id=%s
            """, (roll_no, name, email, course, batch, phone, address, student_id))

            conn.commit()
            flash("Student updated successfully.", "success")
            cur.close()
            conn.close()
            return redirect("/manage_students")

        except IntegrityError:
            conn.rollback()
            flash("Roll number or email already exists.", "danger")

    cur.execute("SELECT * FROM students WHERE id=%s", (student_id,))
    student = cur.fetchone()

    cur.close()
    conn.close()

    if not student:
        flash("Student not found.", "danger")
        return redirect("/manage_students")

    return render_template(
        "edit_student.html",
        student=student,
        courses=courses,
        batches=batches
    )
#---------------delete student---------------
@app.route("/delete_student/<int:student_id>")
def delete_student(student_id):
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM students WHERE id=%s", (student_id,))
    conn.commit()

    cur.close()
    conn.close()

    flash("Student deleted successfully.", "success")
    return redirect("/manage_students")
#-------------------manage teachers------------
@app.route("/manage_teachers")
def manage_teachers():
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT id, teacher_id, name, email, phone, course, batch, qualification, specialization
        FROM teachers
        ORDER BY name
    """)
    teachers = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("manage_teachers.html", teachers=teachers)
#----------------capture student face-----------------
@app.route("/capture_student_face/<int:student_id>")
def capture_student_face(student_id):
    if not is_admin_logged_in():
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT name FROM students WHERE id=%s", (student_id,))
    row = cur.fetchone()

    cur.close()
    conn.close()

    if not row:
        flash("Student not found.", "danger")
        return redirect("/manage_students")

    student_name = row[0]

    if not capture_faces(student_id, student_name):
        flash("Face capture did not complete. Check that the webcam is available and your face is visible, then retry.", "warning")
        return redirect("/manage_students")

    train_model()

    flash(f"Face captured successfully for {student_name}.", "success")
    return redirect("/manage_students")

#--------------EDit teacher_____________________
@app.route("/edit_teacher/<int:teacher_db_id>", methods=["GET", "POST"])
def edit_teacher(teacher_db_id):
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT course_name FROM courses ORDER BY course_name")
    courses = cur.fetchall()

    cur.execute("SELECT batch_name FROM batches ORDER BY batch_name")
    batches = cur.fetchall()

    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip()
        phone = request.form["phone"].strip()
        course = request.form["course"].strip()
        batch = request.form["batch"].strip()
        qualification = request.form["qualification"].strip()
        specialization = request.form["specialization"].strip()
        experience_years = request.form.get("experience_years", "0").strip() or 0
        password = request.form.get("password", "").strip()

        try:
            if password:
                cur.execute("""
                    UPDATE teachers
                    SET name=%s,
                        email=%s,
                        phone=%s,
                        course=%s,
                        batch=%s,
                        qualification=%s,
                        specialization=%s,
                        experience_years=%s,
                        password=%s
                    WHERE id=%s
                """, (
                    name, email, phone, course, batch,
                    qualification, specialization, experience_years,
                    password, teacher_db_id
                ))
            else:
                cur.execute("""
                    UPDATE teachers
                    SET name=%s,
                        email=%s,
                        phone=%s,
                        course=%s,
                        batch=%s,
                        qualification=%s,
                        specialization=%s,
                        experience_years=%s
                    WHERE id=%s
                """, (
                    name, email, phone, course, batch,
                    qualification, specialization, experience_years,
                    teacher_db_id
                ))

            conn.commit()
            flash("Teacher updated successfully.", "success")
            cur.close()
            conn.close()
            return redirect("/manage_teachers")

        except IntegrityError:
            conn.rollback()
            flash("Teacher email already exists.", "danger")

    cur.execute("SELECT * FROM teachers WHERE id=%s", (teacher_db_id,))
    teacher = cur.fetchone()

    cur.close()
    conn.close()

    if not teacher:
        flash("Teacher not found.", "danger")
        return redirect("/manage_teachers")

    return render_template(
        "edit_teacher.html",
        teacher=teacher,
        courses=courses,
        batches=batches
    )
#-----------------delete teacher--------------
@app.route("/delete_teacher/<int:teacher_db_id>")
def delete_teacher(teacher_db_id):
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM teachers WHERE id=%s", (teacher_db_id,))
    conn.commit()

    cur.close()
    conn.close()

    flash("Teacher deleted successfully.", "success")
    return redirect("/manage_teachers")
#----------------------------delete teacher subject--------------
@app.route("/delete_teacher_subject/<int:id>")
def delete_teacher_subject(id):
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM teacher_subjects WHERE id=%s", (id,))
    conn.commit()

    cur.close()
    conn.close()

    flash("Assignment removed successfully.", "success")
    return redirect("/assign_subjects")

#-----------import students---------------------
@app.route("/import_students", methods=["GET", "POST"])
def import_students():
    if not is_admin_logged_in():
        return redirect("/admin_login")

    if request.method == "POST":
        file = request.files.get("file")

        if not file or not file.filename:
            flash("Please choose an Excel file.", "danger")
            return redirect("/import_students")

        try:
            df = pd.read_excel(file)

            required_columns = ["roll_no", "name", "email", "course", "batch"]
            missing = [col for col in required_columns if col not in df.columns]

            if missing:
                flash(f"Missing columns: {', '.join(missing)}", "danger")
                return redirect("/import_students")

            conn = get_db_connection()
            cur = conn.cursor()

            added = 0
            skipped = 0

            for _, row in df.iterrows():
                roll_no = str(row.get("roll_no", "")).strip()
                name = str(row.get("name", "")).strip()
                email = str(row.get("email", "")).strip()
                course = str(row.get("course", "")).strip()
                batch = str(row.get("batch", "")).strip()
                phone = str(row.get("phone", "")).strip() if "phone" in df.columns and pd.notna(row.get("phone")) else ""
                address = str(row.get("address", "")).strip() if "address" in df.columns and pd.notna(row.get("address")) else ""

                if not roll_no or not name or not email or not course or not batch:
                    skipped += 1
                    continue

                try:
                    cur.execute("""
                        INSERT INTO students (roll_no, name, email, course, batch, phone, address)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (roll_no, name, email, course, batch, phone, address))
                    added += 1
                except IntegrityError:
                    skipped += 1

            conn.commit()
            cur.close()
            conn.close()

            flash(f"Import completed. Added: {added}, Skipped: {skipped}", "success")
            return redirect("/manage_students")

        except Exception as e:
            flash(f"Import failed: {str(e)}", "danger")
            return redirect("/import_students")

    return render_template("import_students.html")

#-----------------------------admin newss---------------------------------
@app.route("/admin_news", methods=["GET", "POST"])
def admin_news():
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        form_type = request.form.get("form_type")

        # =========================
        # PORTAL APPEARANCE SETTINGS
        # =========================
        if form_type == "portal_settings":
            university_name = request.form.get("university_name")
            logo = request.files.get("logo")
            backgrounds = request.files.getlist("backgrounds")

            # Existing logo fallback
            cur.execute("SELECT * FROM portal_settings WHERE id=1")
            portal = cur.fetchone()

            logo_name = portal["logo"] if portal else None

            if logo and logo.filename:
                logo_name = secure_filename(logo.filename)
                logo.save(os.path.join(UPLOAD_FOLDER, logo_name))

            bg_files = []
            for bg in backgrounds:
                if bg and bg.filename: 
                    fname = secure_filename(bg.filename)
                    bg.save(os.path.join(UPLOAD_FOLDER, fname))
                    bg_files.append(fname)

            bg_string = ",".join(bg_files) if bg_files else portal["background_images"]

            cur.execute("""
                UPDATE portal_settings
                SET university_name=%s,
                    logo=%s,
                    background_images=%s
                WHERE id=1
            """, (university_name, logo_name, bg_string))

            conn.commit()

        # =========================
        # PORTAL ANNOUNCEMENTS
        # =========================
        elif form_type == "portal_announcement":
            title = request.form.get("title")
            description = request.form.get("description")
            image = request.files.get("image")

            filename = None
            if image and image.filename:
                filename = secure_filename(image.filename)
                image.save(os.path.join(UPLOAD_FOLDER, filename))

            cur.execute("""
                INSERT INTO news (title, description, image)
                VALUES (%s, %s, %s)
            """, (title, description, filename))

            conn.commit()

    # =========================
    # FETCH DATA FOR PAGE
    # =========================
    cur.execute("SELECT * FROM news ORDER BY created_at DESC")
    news = cur.fetchall()

    cur.execute("SELECT * FROM portal_settings WHERE id=1")
    portal = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        "admin_news.html",
        news=news,
        portal=portal
    )

#------------------portal-------------------------
@app.route("/portal_settings", methods=["POST"])
def portal_settings():
    if "user" not in session:
        return redirect("/admin_login")

    name = request.form["university_name"]
    logo = request.files.get("logo")
    backgrounds = request.files.getlist("backgrounds")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # Handle logo
    if logo and logo.filename:
        logo_name = secure_filename(logo.filename)
        logo.save(os.path.join(UPLOAD_FOLDER, logo_name))
    else:
        cur.execute("SELECT logo FROM portal_settings WHERE id=1")
        logo_name = cur.fetchone()["logo"]

    # Handle background images
    bg_files = []
    for bg in backgrounds:
        if bg.filename:
            fname = secure_filename(bg.filename)
            bg.save(os.path.join(UPLOAD_FOLDER, fname))
            bg_files.append(fname)

    bg_string = ",".join(bg_files) if bg_files else None

    cur.execute("""
        UPDATE portal_settings
        SET university_name=%s, logo=%s,
            background_images=COALESCE(%s, background_images)
        WHERE id=1
    """, (name, logo_name, bg_string))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/admin_news")

#-------------------------------------delete news------------------------------
@app.route("/delete_news/<int:id>")
def delete_news(id):
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor()

    # Optional: get image name to delete file also
    cur.execute("SELECT image FROM news WHERE id=%s", (id,))
    data = cur.fetchone()

    if data and data[0]:
        image_path = os.path.join(UPLOAD_FOLDER, data[0])
        if os.path.exists(image_path):
            os.remove(image_path)

    # Delete from DB
    cur.execute("DELETE FROM news WHERE id=%s", (id,))
    conn.commit()

    cur.close()
    conn.close()

    return redirect("/admin_news")
#--------------------managebatches-------------------
@app.route("/manage_batches", methods=["GET", "POST"])
def manage_batches():
    if "user" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    form = request.form.get("form_type")

    # Add course
    if form == "course":
        name = request.form.get("course_name")
        if name:
            cur.execute("INSERT IGNORE INTO courses (course_name) VALUES (%s)", (name,))
            conn.commit()

    # Add batch
    if form == "batch":
        name = request.form.get("batch_name")
        if name:
            cur.execute("INSERT IGNORE INTO batches (batch_name) VALUES (%s)", (name,))
            conn.commit()

    # Add academic year
    if form == "year":
        course_id = request.form.get("course_id")
        batch_id = request.form.get("batch_id")
        year = request.form.get("year")
        if course_id and batch_id and year:
            cur.execute("""
                INSERT INTO academic_years (course_id, batch_id, year)
                VALUES (%s, %s, %s)
            """, (course_id, batch_id, year))
            conn.commit()

    # Fetch data
    cur.execute("SELECT * FROM courses")
    courses = cur.fetchall()

    cur.execute("SELECT * FROM batches")
    batches = cur.fetchall()

    cur.execute("""
        SELECT academic_years.id, courses.course_name, batches.batch_name, academic_years.year
        FROM academic_years
        JOIN courses ON academic_years.course_id = courses.id
        JOIN batches ON academic_years.batch_id = batches.id
        ORDER BY academic_years.year DESC
    """)
    years = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "manage_batches.html",
        courses=courses,
        batches=batches,
        years=years
    )
#==================delete batchess-----------------
@app.route("/delete_course/<int:id>")
def delete_course(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM courses WHERE id=%s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/manage_batches")
#----------------------------------------------------------
@app.route("/delete_batch/<int:id>")
def delete_batch(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM batches WHERE id=%s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/manage_batches")

def gen_frames(student_id=None):
    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cam.isOpened():
        cam = cv2.VideoCapture(0)
    detector = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    try:
        while True:
            success, frame = cam.read()
            if not success or frame is None:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(gray, 1.3, 5)
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    finally:
        cam.release()

#---------------VIDEO________________
@app.route('/video_feed')
def video_feed():
    if "face_student_id" not in session:
        return "No student"

    return Response(
        gen_frames(session["face_student_id"]),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )




# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
