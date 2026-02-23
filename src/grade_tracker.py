#!/usr/bin/env python3
"""BlackRoad Grade Tracker - Student grade tracking and analytics."""
from __future__ import annotations
import argparse, json, sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

GREEN = "\033[0;32m"; RED = "\033[0;31m"; YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"; BLUE = "\033[0;34m"; BOLD = "\033[1m"; NC = "\033[0m"
DB_PATH = Path.home() / ".blackroad" / "grade_tracker.db"


def letter_grade(score: float) -> str:
    if score >= 93: return "A"
    if score >= 90: return "A-"
    if score >= 87: return "B+"
    if score >= 83: return "B"
    if score >= 80: return "B-"
    if score >= 77: return "C+"
    if score >= 73: return "C"
    if score >= 70: return "C-"
    if score >= 60: return "D"
    return "F"


def grade_color(score: float) -> str:
    if score >= 90: return GREEN
    if score >= 80: return CYAN
    if score >= 70: return YELLOW
    if score >= 60: return "\033[0;91m"
    return RED


@dataclass
class Student:
    id: Optional[int]; name: str; student_id: str; email: str = ""; cohort: str = "default"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Assignment:
    id: Optional[int]; title: str; subject: str; max_score: float
    weight: float = 1.0; due_date: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Grade:
    id: Optional[int]; student_id: int; assignment_id: int; score: float
    feedback: str = ""
    graded_at: str = field(default_factory=lambda: datetime.now().isoformat())


class GradeTrackerDB:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                student_id TEXT NOT NULL UNIQUE, email TEXT DEFAULT '',
                cohort TEXT DEFAULT 'default', created_at TEXT)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                subject TEXT NOT NULL, max_score REAL NOT NULL,
                weight REAL DEFAULT 1.0, due_date TEXT DEFAULT '', created_at TEXT)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL,
                assignment_id INTEGER NOT NULL, score REAL NOT NULL,
                feedback TEXT DEFAULT '', graded_at TEXT,
                FOREIGN KEY (student_id) REFERENCES students(id),
                FOREIGN KEY (assignment_id) REFERENCES assignments(id))""")
            conn.commit()

    def add_student(self, s: Student) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO students (name,student_id,email,cohort,created_at) VALUES (?,?,?,?,?)",
                (s.name, s.student_id, s.email, s.cohort, s.created_at))
            conn.commit(); return cur.lastrowid

    def add_assignment(self, a: Assignment) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO assignments (title,subject,max_score,weight,due_date,created_at)"
                " VALUES (?,?,?,?,?,?)",
                (a.title, a.subject, a.max_score, a.weight, a.due_date, a.created_at))
            conn.commit(); return cur.lastrowid

    def record_grade(self, g: Grade) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO grades (student_id,assignment_id,score,feedback,graded_at)"
                " VALUES (?,?,?,?,?)",
                (g.student_id, g.assignment_id, g.score, g.feedback, g.graded_at))
            conn.commit(); return cur.lastrowid

    def student_average(self, sid: int) -> Optional[float]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT AVG(g.score*100.0/a.max_score) FROM grades g"
                " JOIN assignments a ON a.id=g.assignment_id WHERE g.student_id=?", (sid,)).fetchone()
            return round(row[0], 2) if row[0] is not None else None

    def list_students(self, cohort: Optional[str] = None) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            q, p = "SELECT * FROM students", ()
            if cohort: q += " WHERE cohort=?"; p = (cohort,)
            rows = [dict(r) for r in conn.execute(q + " ORDER BY name", p).fetchall()]
            for r in rows:
                r["average"] = self.student_average(r["id"])
                r["letter"] = letter_grade(r["average"]) if r["average"] is not None else "N/A"
            return rows

    def list_assignments(self, subject: Optional[str] = None) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            q, p = "SELECT * FROM assignments", ()
            if subject: q += " WHERE subject=?"; p = (subject,)
            return [dict(r) for r in conn.execute(q + " ORDER BY created_at DESC", p).fetchall()]

    def get_stats(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            ns = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
            na = conn.execute("SELECT COUNT(*) FROM assignments").fetchone()[0]
            ng = conn.execute("SELECT COUNT(*) FROM grades").fetchone()[0]
            avg = conn.execute("SELECT AVG(g.score*100.0/a.max_score) FROM grades g"
                               " JOIN assignments a ON a.id=g.assignment_id").fetchone()[0]
            return {"students": ns, "assignments": na, "grades": ng,
                    "class_average": round(avg, 2) if avg else 0}

    def export_json(self) -> str:
        return json.dumps({"students": self.list_students(),
                           "assignments": self.list_assignments(),
                           "stats": self.get_stats(),
                           "exported_at": datetime.now().isoformat()}, indent=2)


def cmd_list(args, db):
    if args.type == "students":
        students = db.list_students(getattr(args, "cohort", None))
        print(f"\n{BOLD}{CYAN}{'ID':<5} {'Name':<25} {'SID':<12} {'Cohort':<12} {'Avg%':<8} {'Grade'}{NC}")
        print("-" * 72)
        for s in students:
            avg = s["average"]; gc = grade_color(avg) if avg else NC
            print(f"{s['id']:<5} {s['name'][:24]:<25} {s['student_id']:<12} {s['cohort']:<12} "
                  f"{gc}{(f'{avg:.1f}' if avg else 'N/A'):<8}{NC} {gc}{s['letter']}{NC}")
        print(f"\n{CYAN}Total: {len(students)}{NC}\n")
    else:
        assignments = db.list_assignments(getattr(args, "subject", None))
        print(f"\n{BOLD}{CYAN}{'ID':<5} {'Title':<28} {'Subject':<15} {'Max':<8} {'Weight':<8} {'Due'}{NC}")
        print("-" * 78)
        for a in assignments:
            print(f"{a['id']:<5} {a['title'][:27]:<28} {a['subject']:<15}"
                  f" {a['max_score']:<8} {a['weight']:<8} {a['due_date']}")
        print(f"\n{CYAN}Total: {len(assignments)}{NC}\n")


def cmd_add(args, db):
    if args.type == "student":
        sid = db.add_student(Student(id=None, name=args.name, student_id=args.sid,
                                     email=args.email, cohort=args.cohort))
        print(f"{GREEN}Added student #{sid}: {args.name} ({args.sid}){NC}")
    elif args.type == "assignment":
        aid = db.add_assignment(Assignment(id=None, title=args.title, subject=args.subject,
                                           max_score=args.max_score, weight=args.weight,
                                           due_date=args.due_date))
        print(f"{CYAN}Added assignment #{aid}: {args.title} ({args.subject}){NC}")
    else:
        gid = db.record_grade(Grade(id=None, student_id=args.student_db_id,
                                    assignment_id=args.assignment_db_id,
                                    score=args.score, feedback=args.feedback))
        print(f"{YELLOW}Recorded grade #{gid}: {args.score} for student #{args.student_db_id}{NC}")


def cmd_status(args, db):
    stats = db.get_stats(); avg = stats["class_average"]
    print(f"\n{BOLD}{CYAN}=== Grade Tracker Dashboard ==={NC}\n")
    print(f"  {BOLD}Students:{NC}        {stats['students']}")
    print(f"  {BOLD}Assignments:{NC}     {stats['assignments']}")
    print(f"  {BOLD}Grades recorded:{NC} {stats['grades']}")
    print(f"  {BOLD}Class average:{NC}   {grade_color(avg)}{avg:.1f}% ({letter_grade(avg)}){NC}\n")


def cmd_export(args, db):
    out = db.export_json()
    if args.output:
        Path(args.output).write_text(out); print(f"{GREEN}Exported to {args.output}{NC}")
    else:
        print(out)


def build_parser():
    p = argparse.ArgumentParser(prog="grade-tracker", description="BlackRoad Grade Tracker")
    sub = p.add_subparsers(dest="command", required=True)
    lp = sub.add_parser("list"); lp.add_argument("type", choices=["students", "assignments"])
    lp.add_argument("--cohort"); lp.add_argument("--subject")
    ap = sub.add_parser("add"); ap.add_argument("type", choices=["student", "assignment", "grade"])
    ap.add_argument("--name", default=""); ap.add_argument("--sid", default="")
    ap.add_argument("--email", default=""); ap.add_argument("--cohort", default="default")
    ap.add_argument("--title", default=""); ap.add_argument("--subject", default="")
    ap.add_argument("--max-score", dest="max_score", type=float, default=100.0)
    ap.add_argument("--weight", type=float, default=1.0)
    ap.add_argument("--due-date", dest="due_date", default="")
    ap.add_argument("--student-db-id", dest="student_db_id", type=int)
    ap.add_argument("--assignment-db-id", dest="assignment_db_id", type=int)
    ap.add_argument("--score", type=float); ap.add_argument("--feedback", default="")
    sub.add_parser("status")
    ep = sub.add_parser("export"); ep.add_argument("--output", "-o")
    return p


def main():
    args = build_parser().parse_args()
    db = GradeTrackerDB()
    {"list": cmd_list, "add": cmd_add, "status": cmd_status, "export": cmd_export}[args.command](args, db)


if __name__ == "__main__":
    main()
