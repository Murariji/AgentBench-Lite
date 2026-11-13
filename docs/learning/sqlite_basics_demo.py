"""Phase 7 warm-up: SQLite basics with students and marks. Runs in memory: no file is created.

    python docs/learning/sqlite_basics_demo.py
"""

import sqlite3

db = sqlite3.connect(":memory:", isolation_level=None)  # we control transactions ourselves
db.execute("PRAGMA foreign_keys = ON")                    # OFF by default - always switch it on

# 1. TABLES: fixed columns with types. PRIMARY KEY = unique id. FOREIGN KEY = link to a parent row.
db.execute("""CREATE TABLE students (
                  roll_no INTEGER PRIMARY KEY,
                  name    TEXT NOT NULL,
                  class   INTEGER NOT NULL CHECK (class BETWEEN 1 AND 10))""")
db.execute("""CREATE TABLE marks (
                  roll_no INTEGER NOT NULL REFERENCES students (roll_no),
                  subject TEXT NOT NULL,
                  score   INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
                  PRIMARY KEY (roll_no, subject))""")       # one mark per student per subject
db.execute("CREATE INDEX idx_marks_subject ON marks (subject)")  # 7. fast lookups by subject

# 2. INSERT with "?" placeholders: values travel separately from the SQL text.
db.executemany("INSERT INTO students VALUES (?, ?, ?)",
               [(1, "Asha", 8), (2, "Ravi", 8), (3, "Meera", 9)])
db.executemany("INSERT INTO marks VALUES (?, ?, ?)",
               [(1, "maths", 91), (1, "science", 84), (2, "maths", 67), (3, "maths", 78)])

print("--- 3. Query: maths marks, best first")
for row in db.execute("SELECT roll_no, score FROM marks WHERE subject = ? ORDER BY score DESC", ("maths",)):
    print(row)

print("\n--- 4. JOIN: put the name next to each mark (one student -> many marks)")
for row in db.execute("""SELECT s.name, m.subject, m.score
                         FROM students s JOIN marks m ON m.roll_no = s.roll_no
                         ORDER BY s.name, m.subject"""):
    print(row)

print("\n--- 5. Aggregation: average per student (GROUP BY) - LEFT JOIN keeps students without marks")
db.execute("INSERT INTO students VALUES (?, ?, ?)", (4, "Kabir", 9))   # no marks yet
for row in db.execute("""SELECT s.name, COUNT(m.score), ROUND(AVG(m.score), 1)
                         FROM students s LEFT JOIN marks m ON m.roll_no = s.roll_no
                         GROUP BY s.roll_no ORDER BY s.roll_no"""):
    print(row)

print("\n--- 6. Foreign key: a mark for a student who doesn't exist (an orphan)")
try:
    db.execute("INSERT INTO marks VALUES (?, ?, ?)", (99, "maths", 50))
except sqlite3.IntegrityError as error:
    print("refused:", error)

print("\n--- 7. Transaction: enrol a student AND their marks - all or nothing")
db.execute("BEGIN")
try:
    db.execute("INSERT INTO students VALUES (?, ?, ?)", (5, "Zoya", 10))
    db.execute("INSERT INTO marks VALUES (?, ?, ?)", (5, "maths", 88))
    db.execute("INSERT INTO marks VALUES (?, ?, ?)", (5, "science", 150))   # breaks the CHECK rule
    db.execute("COMMIT")
except sqlite3.IntegrityError as error:
    db.execute("ROLLBACK")
    print("rolled back because:", error)
print("Zoya in students?", db.execute("SELECT COUNT(*) FROM students WHERE roll_no = 5").fetchone()[0])
print("Zoya's marks?    ", db.execute("SELECT COUNT(*) FROM marks WHERE roll_no = 5").fetchone()[0])

print("\n--- 8. SQL injection: why values must NEVER be pasted into SQL text")
evil = "nobody' OR '1'='1"
pasted = f"SELECT name FROM students WHERE name = '{evil}'"   # DON'T: the value becomes SQL code
print("pasted into SQL ->", [r[0] for r in db.execute(pasted)], " (matched EVERY student!)")
print("as a ? parameter ->", [r[0] for r in db.execute("SELECT name FROM students WHERE name = ?", (evil,))],
      " (just text: no student has that name)")

print("\n--- 9. Schema version: a number stored inside the file")
db.execute("PRAGMA user_version = 1")
print("user_version =", db.execute("PRAGMA user_version").fetchone()[0])
