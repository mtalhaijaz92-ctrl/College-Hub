"""College Hub API (FastAPI + MySQL).  Local run:  uvicorn main:app --reload"""
import hashlib
import hmac
import os
import re
import time
from collections import defaultdict
from contextlib import asynccontextmanager, contextmanager
from datetime import date
from typing import List, Optional

import jwt
import pymysql
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from pymysql.constants import CLIENT
from pymysql.cursors import DictCursor

load_dotenv()
SECRET = os.environ["JWT_SECRET"]
ADMIN_USER = os.getenv("ADMIN_USER", "admin")      # only used for RESET_ADMIN rescue of college #1
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")
SIGNUP_CODE = os.getenv("SIGNUP_CODE", "")          # optional: if set, new colleges must type this code to register
COLLEGE_NAME = os.getenv("COLLEGE_NAME", "My College")
ORIGINS = [o.strip().rstrip("/") for o in os.getenv("FRONTEND_ORIGIN", "http://localhost:5500").split(",")]

DDL = [
    """CREATE TABLE IF NOT EXISTS colleges (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(80) NOT NULL,
       username VARCHAR(40) NOT NULL UNIQUE, pw_hash VARCHAR(200) NOT NULL, must_change TINYINT NOT NULL DEFAULT 0,
       created_on DATE NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS salary_payments (id INT AUTO_INCREMENT PRIMARY KEY, T_ID INT NOT NULL,
       pay_month CHAR(7) NOT NULL, amount INT NOT NULL, paid TINYINT NOT NULL DEFAULT 0, paid_on DATE NULL,
       note VARCHAR(100) NOT NULL DEFAULT '', UNIQUE KEY uq_teacher_month (T_ID, pay_month))""",
]
TENANT_TABLES = ["students", "teachers_info", "subjects", "class_subjects"]  # each gets a college_id column


@asynccontextmanager
async def lifespan(_app):
    """First start after this update: creates `colleges`, tags all old rows as college #1, moves the old admin login to it."""
    with db() as c:
        for q in DDL:
            c.execute(q)
        for t in TENANT_TABLES:
            try:
                c.execute(f"ALTER TABLE {t} ADD COLUMN college_id INT NOT NULL DEFAULT 1, ADD INDEX idx_{t}_college (college_id)")
            except pymysql.err.OperationalError as e:
                if e.args[0] != 1060:  # 1060 = column already exists (normal on every later start)
                    raise
        try:  # teacher phone number column (new)
            c.execute("ALTER TABLE teachers_info ADD COLUMN T_phno VARCHAR(15) NOT NULL DEFAULT '' AFTER T_Gender")
        except pymysql.err.OperationalError as e:
            if e.args[0] != 1060:  # 1060 = column already exists
                raise
        c.execute("SELECT COUNT(*) n FROM colleges")
        if c.fetchone()["n"] == 0:
            c.execute("SELECT COUNT(*) n FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='admin_account'")
            if c.fetchone()["n"]:
                c.execute("SELECT * FROM admin_account WHERE id=1")
                old = c.fetchone()
                if old:
                    c.execute("INSERT INTO colleges (id,name,username,pw_hash,must_change,created_on) VALUES (1,%s,%s,%s,%s,CURDATE())",
                              (COLLEGE_NAME, old["username"], old["pw_hash"], old["must_change"]))
        if os.getenv("RESET_ADMIN") == "1":  # forgot-password rescue for college #1
            c.execute("REPLACE INTO colleges (id,name,username,pw_hash,must_change,created_on) VALUES (1,%s,%s,%s,1,CURDATE())",
                      (COLLEGE_NAME, ADMIN_USER, hash_pw(ADMIN_PASS)))
    yield


app = FastAPI(title="College Hub API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["*"], allow_headers=["*"])
bearer = HTTPBearer(auto_error=False)


@contextmanager
def db():
    """One connection per request; commits on success, rolls back on any error."""
    extra = {"ssl_ca": os.environ["DB_SSL_CA"]} if os.getenv("DB_SSL_CA") else {}
    conn = pymysql.connect(
        host=os.environ["DB_HOST"], port=int(os.getenv("DB_PORT", "3306")),
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
        cursorclass=DictCursor, client_flag=CLIENT.FOUND_ROWS, **extra,
    )
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except pymysql.err.IntegrityError:
        conn.rollback()
        raise HTTPException(409, "This record is linked to other data (or already exists). Remove or reassign the linked records first.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ================= PASSWORD HANDLING =================
# The lines marked "# HASHING" below are the original password-hashing code. They are commented out,
# so passwords are now saved in the database exactly as the user typed them (plain text, no hashing).

# HASHING: hash_pw() turned a password into "salt$hash" using PBKDF2-SHA256 (200,000 rounds) before saving it.
# def hash_pw(p, salt=None):
#     salt = salt or os.urandom(16).hex()
#     return salt + "$" + hashlib.pbkdf2_hmac("sha256", p.encode(), bytes.fromhex(salt), 200_000).hex()
def hash_pw(p, salt=None):
    return p  # saved directly, no hashing


# HASHING: check_pw() hashed the typed password again with the stored salt and compared it with the saved hash.
# def check_pw(p, stored):
#     return hmac.compare_digest(hash_pw(p, stored.split("$")[0]), stored)
OLD_HASH = re.compile(r"^[0-9a-f]{32}\$[0-9a-f]{64}$")  # shape of the old "salt$hash" values


def check_pw(p, stored):
    if OLD_HASH.match(stored):  # accounts created BEFORE this change still hold a hash, so they keep working
        salt = stored.split("$")[0]
        return hmac.compare_digest((salt + "$" + hashlib.pbkdf2_hmac("sha256", p.encode(), bytes.fromhex(salt), 200_000).hex()).encode(), stored.encode())
    return hmac.compare_digest(p.encode(), stored.encode())  # new accounts: simple plain-text comparison


# NOTE: fingerprint() is only for the login token (it logs old sessions out when the password changes), not for storing passwords.
# It now uses a secret key (HMAC) so the token never exposes anything that could be used to guess the plain-text password.
# HASHING (old line): return hashlib.sha256(row["pw_hash"].encode()).hexdigest()[:16]
def fingerprint(row):
    return hmac.new(SECRET.encode(), row["pw_hash"].encode(), hashlib.sha256).hexdigest()[:16]


def make_token(row):
    return jwt.encode({"sub": str(row["id"]), "v": fingerprint(row), "exp": int(time.time()) + 8 * 3600},
                      SECRET, algorithm="HS256")


def admin_any(cred: Optional[HTTPAuthorizationCredentials] = Depends(bearer)):
    expired = HTTPException(401, "Session expired. Please sign in again.")
    if not cred:
        raise expired
    try:
        claims = jwt.decode(cred.credentials, SECRET, algorithms=["HS256"])
        cid = int(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise expired
    with db() as c:
        c.execute("SELECT * FROM colleges WHERE id=%s", (cid,))
        row = c.fetchone()
    if not row or claims.get("v") != fingerprint(row):
        raise expired
    return row  # the logged-in college; every query below is filtered by row["id"]


def admin(row=Depends(admin_any)):
    if row["must_change"]:
        raise HTTPException(403, "Please change the default password first.")
    return row


def next_id(c, table, col, base):
    c.execute(f"SELECT COALESCE(MAX({col}), %s) + 1 AS n FROM {table}", (base,))  # ids stay unique across ALL colleges
    return c.fetchone()["n"]


def found(c, what):
    if c.rowcount == 0:
        raise HTTPException(404, f"{what} not found")


def owns(c, table, col, val, cid, what):
    """404 unless this row belongs to the logged-in college (stops one college touching another's data)."""
    c.execute(f"SELECT 1 FROM {table} WHERE {col}=%s AND college_id=%s LIMIT 1", (val, cid))
    if not c.fetchone():
        raise HTTPException(404, f"{what} not found")


paid_text = lambda p: "paid" if p else "Pending"


# ---------- models ----------
class Login(BaseModel):
    username: str
    password: str


class Register(BaseModel):
    college: str = Field(min_length=2, max_length=80)
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=8, max_length=100)
    code: str = ""


class ChangePw(BaseModel):
    current: str
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=8, max_length=100)


class SalaryIn(BaseModel):
    amount: int = Field(ge=0)
    paid: bool
    note: str = Field(default="", max_length=100)


class StudentIn(BaseModel):
    name: str = Field(min_length=1, max_length=35)
    email: str = Field(min_length=3, max_length=60)
    gender: str = Field(pattern=r"(?i)^(male|female|other)$")
    phone: str = Field(pattern=r"^\d{10,13}$")
    age: int = Field(ge=5, le=80)
    cid: int
    fee: int = Field(ge=0)
    paid: bool


class TeacherIn(BaseModel):
    name: str = Field(min_length=1, max_length=25)
    age: int = Field(ge=18, le=80)
    gender: str = Field(pattern=r"(?i)^(male|female|other)$")
    phone: str = Field(pattern=r"^\d{10,13}$")
    salary: int = Field(ge=0)


class SubjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=25)
    tid: int


class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=10)
    subjects: List[int] = Field(min_length=1)


# ---------- auth ----------
@app.get("/")
def health():
    return {"status": "College Hub API is running"}


FAILS = defaultdict(list)


def throttle(key, limit, secs, msg):
    now = time.time()
    FAILS[key] = [t for t in FAILS[key] if now - t < secs]
    if len(FAILS[key]) >= limit:
        raise HTTPException(429, msg)
    return now


def ip_of(request):
    return request.client.host if request.client else "?"


@app.get("/api/status")
def status():
    """Public. Tells the login page whether registering a new college needs a signup code."""
    return {"code_required": bool(SIGNUP_CODE)}


@app.post("/api/register")
def register(b: Register, request: Request):
    if SIGNUP_CODE and not hmac.compare_digest(b.code.encode(), SIGNUP_CODE.encode()):
        raise HTTPException(403, "Wrong signup code")
    now = throttle("reg" + ip_of(request), 5, 3600, "Too many sign-ups from this network. Try again later.")
    with db() as c:
        c.execute("SELECT 1 FROM colleges WHERE username=%s", (b.username.strip(),))
        if c.fetchone():
            raise HTTPException(409, "This username is already taken. Choose another one.")
        c.execute("INSERT INTO colleges (name,username,pw_hash,must_change,created_on) VALUES (%s,%s,%s,0,CURDATE())",
                  (b.college.strip(), b.username.strip(), hash_pw(b.password)))
        c.execute("SELECT * FROM colleges WHERE id=%s", (c.lastrowid,))
        row = c.fetchone()
    FAILS["reg" + ip_of(request)].append(now)
    return {"token": make_token(row), "username": row["username"], "must_change": False}


@app.post("/api/login")
def login(b: Login, request: Request):
    ip = ip_of(request)
    now = throttle(ip, 10, 300, "Too many wrong attempts. Please wait a few minutes.")
    with db() as c:
        c.execute("SELECT * FROM colleges WHERE username=%s", (b.username.strip(),))
        row = c.fetchone()
    if not (row and check_pw(b.password, row["pw_hash"])):
        FAILS[ip].append(now)
        raise HTTPException(401, "Wrong username or password")
    return {"token": make_token(row), "username": row["username"], "must_change": bool(row["must_change"])}


@app.post("/api/change-password")
def change_password(b: ChangePw, row=Depends(admin_any)):
    if not check_pw(b.current, row["pw_hash"]):
        raise HTTPException(400, "Current password is wrong")
    if b.password == b.current:
        raise HTTPException(400, "Choose a new password that is different from the current one")
    with db() as c:
        c.execute("SELECT 1 FROM colleges WHERE username=%s AND id<>%s", (b.username, row["id"]))
        if c.fetchone():
            raise HTTPException(409, "This username is already taken. Choose another one.")
        c.execute("UPDATE colleges SET username=%s, pw_hash=%s, must_change=0 WHERE id=%s", (b.username, hash_pw(b.password), row["id"]))
        c.execute("SELECT * FROM colleges WHERE id=%s", (row["id"],))
        new = c.fetchone()
    return {"token": make_token(new), "username": new["username"]}


# ---------- read everything for THIS college ----------
@app.get("/api/data")
def all_data(col=Depends(admin)):
    k = col["id"]
    with db() as c:
        c.execute(
            "SELECT s.Regno regno, s.NAME name, s.email, s.GENDER gender, s.phno, s.AGE age, s.C_ID cid, "
            "COALESCE(f.FEE,0) fee, COALESCE(LOWER(f.Paid)='paid',0) paid "
            "FROM students s LEFT JOIN student_fee f ON f.Regno = s.Regno WHERE s.college_id=%s ORDER BY s.Regno", (k,))
        students = c.fetchall()
        for s in students:
            p = s.pop("phno")
            s["phone"] = "0" + str(p) if p else ""
            s["paid"] = bool(s["paid"])
        c.execute("SELECT T_ID id, T_Name name, T_AGE age, T_Gender gender, T_phno phone, salary FROM teachers_info WHERE college_id=%s ORDER BY T_ID", (k,))
        teachers = c.fetchall()
        c.execute("SELECT subject_ID id, T_subject name, T_ID tid FROM subjects WHERE college_id=%s ORDER BY subject_ID", (k,))
        subjects = c.fetchall()
        c.execute("SELECT cl.C_ID id, cl.C_name name, cs.S_ID FROM classes cl "
                  "LEFT JOIN class_subjects cs ON cs.C_ID=cl.C_ID AND cs.college_id=cl.college_id "
                  "WHERE cl.college_id=%s ORDER BY cl.C_ID", (k,))
        classes = {}
        for r in c.fetchall():
            x = classes.setdefault(r["id"], {"id": r["id"], "name": r["name"], "subjects": []})
            if r["S_ID"] is not None and r["S_ID"] not in x["subjects"]:
                x["subjects"].append(r["S_ID"])
    return {"college": col["name"], "students": students, "teachers": teachers, "subjects": subjects, "classes": list(classes.values())}


# ---------- students (+ their fee row) ----------
@app.post("/api/students")
def add_student(s: StudentIn, col=Depends(admin)):
    k = col["id"]
    with db() as c:
        owns(c, "classes", "C_ID", s.cid, k, "Class")
        no = next_id(c, "students", "Regno", 1000)
        c.execute("INSERT INTO students (Regno,NAME,email,GENDER,phno,AGE,C_ID,college_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                  (no, s.name, s.email, s.gender.capitalize(), int(s.phone), s.age, s.cid, k))
        c.execute("INSERT INTO student_fee (Regno,FEE,Paid) VALUES (%s,%s,%s)", (no, s.fee, paid_text(s.paid)))
    return {"regno": no}


@app.put("/api/students/{regno}")
def edit_student(regno: int, s: StudentIn, col=Depends(admin)):
    k = col["id"]
    with db() as c:
        owns(c, "classes", "C_ID", s.cid, k, "Class")
        c.execute("UPDATE students SET NAME=%s,email=%s,GENDER=%s,phno=%s,AGE=%s,C_ID=%s WHERE Regno=%s AND college_id=%s",
                  (s.name, s.email, s.gender.capitalize(), int(s.phone), s.age, s.cid, regno, k))
        found(c, "Student")
        c.execute("UPDATE student_fee SET FEE=%s, Paid=%s WHERE Regno=%s", (s.fee, paid_text(s.paid), regno))
        if c.rowcount == 0:
            c.execute("INSERT INTO student_fee (Regno,FEE,Paid) VALUES (%s,%s,%s)", (regno, s.fee, paid_text(s.paid)))
    return {"ok": True}


@app.delete("/api/students/{regno}")
def delete_student(regno: int, col=Depends(admin)):
    with db() as c:
        owns(c, "students", "Regno", regno, col["id"], "Student")
        c.execute("DELETE FROM student_fee WHERE Regno=%s", (regno,))
        c.execute("DELETE FROM students WHERE Regno=%s AND college_id=%s", (regno, col["id"]))
    return {"ok": True}


# ---------- teachers ----------
@app.post("/api/teachers")
def add_teacher(t: TeacherIn, col=Depends(admin)):
    with db() as c:
        tid = next_id(c, "teachers_info", "T_ID", 10)
        c.execute("INSERT INTO teachers_info (T_ID,T_Name,T_AGE,T_Gender,T_phno,salary,college_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                  (tid, t.name, t.age, t.gender.capitalize(), t.phone, t.salary, col["id"]))
    return {"id": tid}


@app.put("/api/teachers/{tid}")
def edit_teacher(tid: int, t: TeacherIn, col=Depends(admin)):
    with db() as c:
        c.execute("UPDATE teachers_info SET T_Name=%s,T_AGE=%s,T_Gender=%s,T_phno=%s,salary=%s WHERE T_ID=%s AND college_id=%s",
                  (t.name, t.age, t.gender.capitalize(), t.phone, t.salary, tid, col["id"]))
        found(c, "Teacher")
    return {"ok": True}


@app.delete("/api/teachers/{tid}")
def delete_teacher(tid: int, col=Depends(admin)):
    with db() as c:  # blocked (409) while subjects still point to this teacher
        owns(c, "teachers_info", "T_ID", tid, col["id"], "Teacher")
        c.execute("DELETE FROM salary_payments WHERE T_ID=%s", (tid,))
        c.execute("DELETE FROM teachers_info WHERE T_ID=%s AND college_id=%s", (tid, col["id"]))
    return {"ok": True}


# ---------- subjects ----------
@app.post("/api/subjects")
def add_subject(s: SubjectIn, col=Depends(admin)):
    with db() as c:
        owns(c, "teachers_info", "T_ID", s.tid, col["id"], "Teacher")
        sid = next_id(c, "subjects", "subject_ID", 300)
        c.execute("INSERT INTO subjects (subject_ID,T_subject,T_ID,college_id) VALUES (%s,%s,%s,%s)", (sid, s.name, s.tid, col["id"]))
    return {"id": sid}


@app.put("/api/subjects/{sid}")
def edit_subject(sid: int, s: SubjectIn, col=Depends(admin)):
    with db() as c:
        owns(c, "teachers_info", "T_ID", s.tid, col["id"], "Teacher")
        c.execute("UPDATE subjects SET T_subject=%s, T_ID=%s WHERE subject_ID=%s AND college_id=%s", (s.name, s.tid, sid, col["id"]))
        found(c, "Subject")
    return {"ok": True}


@app.delete("/api/subjects/{sid}")
def delete_subject(sid: int, col=Depends(admin)):
    with db() as c:
        owns(c, "subjects", "subject_ID", sid, col["id"], "Subject")
        c.execute("DELETE FROM class_subjects WHERE S_ID=%s AND college_id=%s", (sid, col["id"]))
        c.execute("DELETE FROM subjects WHERE subject_ID=%s AND college_id=%s", (sid, col["id"]))
    return {"ok": True}


# ---------- classes (table `classes`; class_subjects links a class to its subjects) ----------
@app.put("/api/classes/{cid}")
def save_class(cid: int, b: ClassIn, col=Depends(admin)):
    k = col["id"]
    ids = list(dict.fromkeys(b.subjects))
    with db() as c:
        c.execute("SELECT COUNT(*) n FROM subjects WHERE college_id=%s AND subject_ID IN (%s)" % ("%s", ",".join(["%s"] * len(ids))), (k, *ids))
        if c.fetchone()["n"] != len(ids):
            raise HTTPException(422, "One of the chosen subjects was not found")
        c.execute("SELECT 1 FROM classes WHERE C_ID=%s AND college_id=%s LIMIT 1", (cid, k))
        if c.fetchone():  # existing class: rename it and rebuild its subject links
            c.execute("UPDATE classes SET C_name=%s WHERE C_ID=%s AND college_id=%s", (b.name, cid, k))
            c.execute("DELETE FROM class_subjects WHERE C_ID=%s AND college_id=%s", (cid, k))
        else:  # new class: MySQL AUTO_INCREMENT picks an id no other college uses
            c.execute("INSERT INTO classes (C_name,college_id) VALUES (%s,%s)", (b.name, k))
            cid = c.lastrowid
        c.executemany("INSERT INTO class_subjects (C_ID,S_ID,college_id) VALUES (%s,%s,%s)", [(cid, i, k) for i in ids])
    return {"ok": True, "id": cid}


@app.delete("/api/classes/{cid}")
def delete_class(cid: int, col=Depends(admin)):
    k = col["id"]
    with db() as c:
        c.execute("SELECT COUNT(*) n FROM students WHERE C_ID=%s AND college_id=%s", (cid, k))
        if c.fetchone()["n"]:
            raise HTTPException(409, "This class still has students. Move or delete them first.")
        c.execute("DELETE FROM classes WHERE C_ID=%s AND college_id=%s", (cid, k))  # its class_subjects links go with it
        found(c, "Class")
    return {"ok": True}


# ---------- teacher salary record (one row per teacher per month) ----------
def check_month(m):
    if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", m):
        raise HTTPException(422, "Month must look like 2026-10")


@app.get("/api/salaries/teacher/{tid}")
def salary_history(tid: int, col=Depends(admin)):
    with db() as c:
        owns(c, "teachers_info", "T_ID", tid, col["id"], "Teacher")
        c.execute("SELECT pay_month month, amount, paid, paid_on, note FROM salary_payments WHERE T_ID=%s ORDER BY pay_month DESC", (tid,))
        rows = c.fetchall()
    for r in rows:
        r["paid"] = bool(r["paid"])
    return rows


@app.get("/api/salaries/{month}")
def salaries(month: str, col=Depends(admin)):
    check_month(month)
    with db() as c:
        c.execute(
            "SELECT t.T_ID tid, t.T_Name name, COALESCE(p.amount, t.salary) amount, COALESCE(p.paid,0) paid, "
            "p.paid_on, COALESCE(p.note,'') note FROM teachers_info t "
            "LEFT JOIN salary_payments p ON p.T_ID=t.T_ID AND p.pay_month=%s WHERE t.college_id=%s ORDER BY t.T_ID", (month, col["id"]))
        rows = c.fetchall()
    for r in rows:
        r["paid"] = bool(r["paid"])
    return rows


@app.put("/api/salaries/{tid}/{month}")
def save_salary(tid: int, month: str, b: SalaryIn, col=Depends(admin)):
    check_month(month)
    with db() as c:
        owns(c, "teachers_info", "T_ID", tid, col["id"], "Teacher")
        c.execute(
            "INSERT INTO salary_payments (T_ID,pay_month,amount,paid,paid_on,note) VALUES (%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE amount=VALUES(amount), "
            "paid_on=IF(VALUES(paid)=1, COALESCE(paid_on, CURDATE()), NULL), paid=VALUES(paid), note=VALUES(note)",
            (tid, month, b.amount, int(b.paid), date.today() if b.paid else None, b.note))
    return {"ok": True}
