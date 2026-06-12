import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'gym.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS exercises (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            exercise_id INTEGER NOT NULL REFERENCES exercises(id),
            date        TEXT    NOT NULL,
            sets        INTEGER NOT NULL,
            reps        INTEGER NOT NULL,
            weight      REAL    NOT NULL,
            notes       TEXT    DEFAULT ''
        );
    ''')
    db.commit()

    seed = [
        'Bench press', 'Squat', 'Deadlift', 'Overhead press',
        'Barbell row', 'Pull-ups', 'Incline DB press', 'Leg press',
        'Bicep curl', 'Tricep pushdown'
    ]
    for name in seed:
        try:
            db.execute('INSERT INTO exercises (name) VALUES (?)', (name,))
        except sqlite3.IntegrityError:
            pass
    db.commit()
    db.close()


# ---------- User helpers ----------

def create_user(db, username, password):
    try:
        db.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            (username.strip(), generate_password_hash(password))
        )
        db.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, 'Username already taken.'


def get_user_by_username(db, username):
    return db.execute(
        'SELECT * FROM users WHERE username = ?', (username.strip(),)
    ).fetchone()


def verify_password(user, password):
    return check_password_hash(user['password_hash'], password)


# ---------- Exercise helpers ----------

def get_all_exercises(db):
    return db.execute('SELECT * FROM exercises ORDER BY name').fetchall()


def add_exercise(db, name):
    db.execute('INSERT OR IGNORE INTO exercises (name) VALUES (?)', (name.strip(),))
    db.commit()
    return db.execute('SELECT id FROM exercises WHERE name = ?', (name.strip(),)).fetchone()['id']


# ---------- Log helpers ----------

def add_log(db, user_id, exercise_id, date, sets, reps, weight, notes=''):
    db.execute(
        'INSERT INTO logs (user_id, exercise_id, date, sets, reps, weight, notes) VALUES (?,?,?,?,?,?,?)',
        (user_id, exercise_id, date, sets, reps, weight, notes)
    )
    db.commit()


def get_recent_logs(db, user_id, limit=10):
    return db.execute('''
        SELECT l.*, e.name AS exercise_name
        FROM logs l JOIN exercises e ON e.id = l.exercise_id
        WHERE l.user_id = ?
        ORDER BY l.date DESC, l.id DESC LIMIT ?
    ''', (user_id, limit)).fetchall()


def get_logs_by_exercise(db, user_id, exercise_id):
    return db.execute('''
        SELECT l.*, e.name AS exercise_name
        FROM logs l JOIN exercises e ON e.id = l.exercise_id
        WHERE l.user_id = ? AND l.exercise_id = ?
        ORDER BY l.date DESC, l.id DESC
    ''', (user_id, exercise_id)).fetchall()


def get_all_logs(db, user_id):
    return db.execute('''
        SELECT l.*, e.name AS exercise_name
        FROM logs l JOIN exercises e ON e.id = l.exercise_id
        WHERE l.user_id = ?
        ORDER BY l.date DESC, l.id DESC
    ''', (user_id,)).fetchall()


def get_progress_data(db, user_id, exercise_id):
    return db.execute('''
        SELECT date, MAX(weight) AS max_weight
        FROM logs WHERE user_id = ? AND exercise_id = ?
        GROUP BY date ORDER BY date ASC
    ''', (user_id, exercise_id)).fetchall()


def get_personal_records(db, user_id):
    return db.execute('''
        SELECT e.name AS exercise_name, MAX(l.weight) AS max_weight, l.date, l.sets, l.reps
        FROM logs l JOIN exercises e ON e.id = l.exercise_id
        WHERE l.user_id = ?
        GROUP BY l.exercise_id ORDER BY e.name
    ''', (user_id,)).fetchall()


def delete_log(db, log_id, user_id):
    # user_id check prevents deleting another user's log
    db.execute('DELETE FROM logs WHERE id = ? AND user_id = ?', (log_id, user_id))
    db.commit()
