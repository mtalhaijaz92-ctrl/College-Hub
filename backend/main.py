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
# First-time login (shown on the login page until the admin sets their own password)
DEFAULT_USER = os.getenv("ADMIN_USER", "admin")
DEFAULT_PASS = os.getenv("ADMIN_PASS", "admin123")
ORIGINS = [o.strip().rstrip("/") for o in os.getenv("FRONTEND_ORIGIN", "http://localhost:5500").split(",")]

DDL = [
    """CREATE TABLE IF NOT EXISTS admin_account (id TINYINT PRIMARY KEY, username VARCHAR(40) NOT NULL,
       pw_hash VARCHAR(200) NOT NULL, must_change TINYINT NOT NULL DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS salary_payments (id INT AUTO_INCREMENT PRIMARY KEY, T_ID INT NOT NULL,
       pay_month CHAR(7) NOT NULL, amount INT NOT NULL, paid TINYINT NOT NULL DEFAULT 0, paid_on DATE NULL,
       note VARCHAR(100) NOT NULL DEFAULT '', UNIQUE KEY uq_teacher_month (T_ID, pay_month))""",
]


@asynccontextmanager
async def lifespan(_app):
    """Creates the two new tables and the default admin the first time the API starts."""
    with db() as c:
        for q in DDL:
            c.execute(q)
        c.execute("SELECT id FROM admin_account WHERE id=1")
        if not c.fetchone() or os.getenv("RESET_ADMIN") == "1":  # RESET_ADMIN=1 = forgot-password rescue
            c.execute("REPLACE INTO admin_account (id,username,pw_hash,must_change) VALUES (1,%s,%s,1)",
                      (DEFAULT_USER, hash_pw(DEFAULT_PASS)))
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


def hash_pw(p, salt=None):
    salt = salt or os.urandom(16).hex()
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", p.encode(), bytes.fromhex(salt), 200_000).hex()


def check_pw(p, stored):
    return hmac.compare_digest(hash_pw(p, stored.split("$")[0]), stored)


def fingerprint(row):  # a token stops working the moment the password changes
    return hashlib.sha256(row["pw_hash"].encode()).hexdigest()[:16]


def make_token(row):
    return jwt.encode({"sub": row["username"], "v": fingerprint(row), "exp": int(time.time()) + 8 * 3600},
                      SECRET, algorithm="HS256")


def admin_any(cred: Optional[HTTPAuthorizationCredentials] = Depends(bearer)):
    expired = HTTPException(401, "Session expired. Please sign in again.")
    if not cred:
        raise expired
    try:
        claims = jwt.decode(cred.credentials, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise expired
    with db() as c:
        c.execute("SELECT * FROM admin_account WHERE id=1")
        row = c.fetchone()
    if not row or claims.get("v") != fingerprint(row):
        raise expired
    return row


def admin(row=Depends(admin_any)):
    if row["must_change"]:
        raise HTTPException(403, "Please change the default password first.")
    return row


def next_id(c, table, col, base):
    c.execute(f"SELECT COALESCE(MAX({col}), %s) + 1 AS n FROM {table}", (base,))
    return c.fetchone()["n"]


def found(c, what):
    if c.rowcount == 0:
        raise HTTPException(404, f"{what} not found")


paid_text = lambda p: "paid" if p else "Pending"


# ---------- models ----------
class Login(BaseModel):
    username: str
    password: str


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
    gender: str = Field(max_length=10)
    phone: str = Field(pattern=r"^\d{10,13}$")
    age: int = Field(ge=5, le=80)
    cid: int
    fee: int = Field(ge=0)
    paid: bool


class TeacherIn(BaseModel):
    name: str = Field(min_length=1, max_length=25)
    age: int = Field(ge=18, le=80)
    gender: str = Field(max_length=10)
    salary: int = Field(ge=0)


class SubjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=25)
    tid: int


class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=10)
    subjects: List[int] = Field(min_length=1)


# ---------- auth + read ----------
@app.get("/")
def health():
    return {"status": "College Hub API is running"}


FAILS = defaultdict(list)


@app.get("/api/status")
def status():
    """Public. Reveals the default login ONLY until the admin has set their own password."""
    with db() as c:
        c.execute("SELECT * FROM admin_account WHERE id=1")
        row = c.fetchone()
    if row and row["must_change"] and check_pw(DEFAULT_PASS, row["pw_hash"]):
        return {"first_run": True, "username": row["username"], "password": DEFAULT_PASS}
    return {"first_run": False}


@app.post("/api/login")
def login(b: Login, request: Request):
    ip = request.client.host if request.client else "?"
    now = time.time()
    FAILS[ip] = [t for t in FAILS[ip] if now - t < 300]
    if len(FAILS[ip]) >= 10:
        raise HTTPException(429, "Too many wrong attempts. Please wait a few minutes.")
    with db() as c:
        c.execute("SELECT * FROM admin_account WHERE id=1")
        row = c.fetchone()
    ok = row and hmac.compare_digest(b.username.encode(), row["username"].encode()) and check_pw(b.password, row["pw_hash"])
    if not ok:
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
        c.execute("UPDATE admin_account SET username=%s, pw_hash=%s, must_change=0 WHERE id=1", (b.username, hash_pw(b.password)))
        c.execute("SELECT * FROM admin_account WHERE id=1")
        new = c.fetchone()
    return {"token": make_token(new), "username": new["username"]}


@app.get("/api/data")
def all_data(_=Depends(admin)):
    with db() as c:
        c.execute(
            "SELECT s.Regno regno, s.NAME name, s.email, s.GENDER gender, s.phno, s.AGE age, s.C_ID cid, "
            "COALESCE(f.FEE,0) fee, COALESCE(LOWER(f.Paid)='paid',0) paid "
            "FROM students s LEFT JOIN student_fee f ON f.Regno = s.Regno ORDER BY s.Regno"
        )
        students = c.fetchall()
        for s in students:
            p = s.pop("phno")
            s["phone"] = "0" + str(p) if p else ""
            s["paid"] = bool(s["paid"])
        c.execute("SELECT T_ID id, T_Name name, T_AGE age, T_Gender gender, salary FROM teachers_info ORDER BY T_ID")
        teachers = c.fetchall()
        c.execute("SELECT subject_ID id, T_subject name, T_ID tid FROM subjects ORDER BY subject_ID")
        subjects = c.fetchall()
        c.execute("SELECT C_ID id, C_name name, S_ID FROM class_subjects ORDER BY C_ID")
        classes = {}
        for r in c.fetchall():
            k = classes.setdefault(r["id"], {"id": r["id"], "name": r["name"], "subjects": []})
            if r["S_ID"] not in k["subjects"]:
                k["subjects"].append(r["S_ID"])
    return {"students": students, "teachers": teachers, "subjects": subjects, "classes": list(classes.values())}


# ---------- students (+ their fee row) ----------
@app.post("/api/students")
def add_student(s: StudentIn, _=Depends(admin)):
    with db() as c:
        no = next_id(c, "students", "Regno", 1000)
        c.execute("INSERT INTO students (Regno,NAME,email,GENDER,phno,AGE,C_ID) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                  (no, s.name, s.email, s.gender, int(s.phone), s.age, s.cid))
        c.execute("INSERT INTO student_fee (Regno,FEE,Paid) VALUES (%s,%s,%s)", (no, s.fee, paid_text(s.paid)))
    return {"regno": no}


@app.put("/api/students/{regno}")
def edit_student(regno: int, s: StudentIn, _=Depends(admin)):
    with db() as c:
        c.execute("UPDATE students SET NAME=%s,email=%s,GENDER=%s,phno=%s,AGE=%s,C_ID=%s WHERE Regno=%s",
                  (s.name, s.email, s.gender, int(s.phone), s.age, s.cid, regno))
        found(c, "Student")
        c.execute("UPDATE student_fee SET FEE=%s, Paid=%s WHERE Regno=%s", (s.fee, paid_text(s.paid), regno))
        if c.rowcount == 0:
            c.execute("INSERT INTO student_fee (Regno,FEE,Paid) VALUES (%s,%s,%s)", (regno, s.fee, paid_text(s.paid)))
    return {"ok": True}


@app.delete("/api/students/{regno}")
def delete_student(regno: int, _=Depends(admin)):
    with db() as c:
        c.execute("DELETE FROM student_fee WHERE Regno=%s", (regno,))
        c.execute("DELETE FROM students WHERE Regno=%s", (regno,))
        found(c, "Student")
    return {"ok": True}


# ---------- teachers ----------
@app.post("/api/teachers")
def add_teacher(t: TeacherIn, _=Depends(admin)):
    with db() as c:
        tid = next_id(c, "teachers_info", "T_ID", 10)
        c.execute("INSERT INTO teachers_info (T_ID,T_Name,T_AGE,T_Gender,salary) VALUES (%s,%s,%s,%s,%s)",
                  (tid, t.name, t.age, t.gender, t.salary))
    return {"id": tid}


@app.put("/api/teachers/{tid}")
def edit_teacher(tid: int, t: TeacherIn, _=Depends(admin)):
    with db() as c:
        c.execute("UPDATE teachers_info SET T_Name=%s,T_AGE=%s,T_Gender=%s,salary=%s WHERE T_ID=%s",
                  (t.name, t.age, t.gender, t.salary, tid))
        found(c, "Teacher")
    return {"ok": True}


@app.delete("/api/teachers/{tid}")
def delete_teacher(tid: int, _=Depends(admin)):
    with db() as c:  # blocked (409) while subjects still point to this teacher
        c.execute("DELETE FROM salary_payments WHERE T_ID=%s", (tid,))
        c.execute("DELETE FROM teachers_info WHERE T_ID=%s", (tid,))
        found(c, "Teacher")
    return {"ok": True}


# ---------- subjects ----------
@app.post("/api/subjects")
def add_subject(s: SubjectIn, _=Depends(admin)):
    with db() as c:
        sid = next_id(c, "subjects", "subject_ID", 300)
        c.execute("INSERT INTO subjects (subject_ID,T_subject,T_ID) VALUES (%s,%s,%s)", (sid, s.name, s.tid))
    return {"id": sid}


@app.put("/api/subjects/{sid}")
def edit_subject(sid: int, s: SubjectIn, _=Depends(admin)):
    with db() as c:
        c.execute("UPDATE subjects SET T_subject=%s, T_ID=%s WHERE subject_ID=%s", (s.name, s.tid, sid))
        found(c, "Subject")
    return {"ok": True}


@app.delete("/api/subjects/{sid}")
def delete_subject(sid: int, _=Depends(admin)):
    with db() as c:
        c.execute("DELETE FROM class_subjects WHERE S_ID=%s", (sid,))
        c.execute("DELETE FROM subjects WHERE subject_ID=%s", (sid,))
        found(c, "Subject")
    return {"ok": True}


# ---------- classes (a class = rows in class_subjects) ----------
@app.put("/api/classes/{cid}")
def save_class(cid: int, b: ClassIn, _=Depends(admin)):
    ids = list(dict.fromkeys(b.subjects))  # also removes the duplicate rows in the old data
    with db() as c:
        c.execute("DELETE FROM class_subjects WHERE C_ID=%s", (cid,))
        c.executemany("INSERT INTO class_subjects (C_ID,S_ID,C_name) VALUES (%s,%s,%s)", [(cid, i, b.name) for i in ids])
    return {"ok": True}


@app.delete("/api/classes/{cid}")
def delete_class(cid: int, _=Depends(admin)):
    with db() as c:
        c.execute("SELECT COUNT(*) n FROM students WHERE C_ID=%s", (cid,))
        if c.fetchone()["n"]:
            raise HTTPException(409, "This class still has students. Move or delete them first.")
        c.execute("DELETE FROM class_subjects WHERE C_ID=%s", (cid,))
    return {"ok": True}


# ---------- teacher salary record (one row per teacher per month) ----------
def check_month(m):
    if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", m):
        raise HTTPException(422, "Month must look like 2026-10")


@app.get("/api/salaries/teacher/{tid}")
def salary_history(tid: int, _=Depends(admin)):
    with db() as c:
        c.execute("SELECT pay_month month, amount, paid, paid_on, note FROM salary_payments WHERE T_ID=%s ORDER BY pay_month DESC", (tid,))
        rows = c.fetchall()
    for r in rows:
        r["paid"] = bool(r["paid"])
    return rows


@app.get("/api/salaries/{month}")
def salaries(month: str, _=Depends(admin)):
    check_month(month)
    with db() as c:
        c.execute(
            "SELECT t.T_ID tid, t.T_Name name, COALESCE(p.amount, t.salary) amount, COALESCE(p.paid,0) paid, "
            "p.paid_on, COALESCE(p.note,'') note FROM teachers_info t "
            "LEFT JOIN salary_payments p ON p.T_ID=t.T_ID AND p.pay_month=%s ORDER BY t.T_ID", (month,))
        rows = c.fetchall()
    for r in rows:
        r["paid"] = bool(r["paid"])
    return rows


@app.put("/api/salaries/{tid}/{month}")
def save_salary(tid: int, month: str, b: SalaryIn, _=Depends(admin)):
    check_month(month)
    with db() as c:
        c.execute("SELECT 1 FROM teachers_info WHERE T_ID=%s", (tid,))
        if not c.fetchone():
            raise HTTPException(404, "Teacher not found")
        c.execute(
            "INSERT INTO salary_payments (T_ID,pay_month,amount,paid,paid_on,note) VALUES (%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE amount=VALUES(amount), "
            "paid_on=IF(VALUES(paid)=1, COALESCE(paid_on, CURDATE()), NULL), paid=VALUES(paid), note=VALUES(note)",
            (tid, month, b.amount, int(b.paid), date.today() if b.paid else None, b.note))
    return {"ok": True}
