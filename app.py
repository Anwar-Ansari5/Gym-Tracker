from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from functools import wraps
from datetime import date
import database as db_module

app = Flask(__name__)
app.secret_key = 'gym-tracker-secret-key-change-in-prod'

db_module.init_db()


# ─── Auth decorator ──────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ─── Register ────────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm', '')
        if not username or not password:
            flash('Username and password are required.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        else:
            db = db_module.get_db()
            ok, err = db_module.create_user(db, username, password)
            db.close()
            if ok:
                flash('Account created! Please log in.', 'success')
                return redirect(url_for('login'))
            else:
                flash(err, 'error')
    return render_template('register.html')


# ─── Login ───────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db   = db_module.get_db()
        user = db_module.get_user_by_username(db, username)
        db.close()
        if user and db_module.verify_password(user, password):
            session['user_id']  = user['id']
            session['username'] = user['username']
            flash(f"Welcome back, {user['username']}!", 'success')
            return redirect(url_for('index'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')


# ─── Logout ──────────────────────────────────────────────────────────────────

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


# ─── Dashboard ───────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    db = db_module.get_db()
    uid = session['user_id']
    recent_logs    = db_module.get_recent_logs(db, uid, limit=10)
    exercises      = db_module.get_all_exercises(db)
    prs            = db_module.get_personal_records(db, uid)
    total_sessions = db.execute(
        "SELECT COUNT(DISTINCT date || exercise_id) FROM logs WHERE user_id=?", (uid,)
    ).fetchone()[0]
    total_logs = db.execute(
        "SELECT COUNT(*) FROM logs WHERE user_id=?", (uid,)
    ).fetchone()[0]
    db.close()
    return render_template('index.html', recent_logs=recent_logs, exercises=exercises,
                           prs=prs, total_sessions=total_sessions, total_logs=total_logs,
                           today=date.today().isoformat())


# ─── Log workout ─────────────────────────────────────────────────────────────

@app.route('/log', methods=['GET', 'POST'])
@login_required
def log_workout():
    db = db_module.get_db()
    exercises = db_module.get_all_exercises(db)
    if request.method == 'POST':
        exercise_id  = request.form.get('exercise_id')
        new_exercise = request.form.get('new_exercise', '').strip()
        workout_date = request.form.get('date')
        sets         = request.form.get('sets')
        reps         = request.form.get('reps')
        weight       = request.form.get('weight')
        notes        = request.form.get('notes', '')
        if new_exercise:
            exercise_id = db_module.add_exercise(db, new_exercise)
        if not exercise_id or not workout_date or not sets or not reps or not weight:
            flash('Please fill in all required fields.', 'error')
        else:
            try:
                db_module.add_log(db, session['user_id'], int(exercise_id),
                                  workout_date, int(sets), int(reps), float(weight), notes)
                flash('Workout logged!', 'success')
                db.close()
                return redirect(url_for('index'))
            except ValueError:
                flash('Sets, reps and weight must be numbers.', 'error')
    db.close()
    return render_template('log.html', exercises=exercises, today=date.today().isoformat())


# ─── History ─────────────────────────────────────────────────────────────────

@app.route('/history')
@login_required
def history():
    db = db_module.get_db()
    uid = session['user_id']
    exercise_id = request.args.get('exercise_id', type=int)
    exercises   = db_module.get_all_exercises(db)
    logs = db_module.get_logs_by_exercise(db, uid, exercise_id) if exercise_id else db_module.get_all_logs(db, uid)
    db.close()
    return render_template('history.html', logs=logs, exercises=exercises, selected_exercise=exercise_id)


# ─── Delete log ──────────────────────────────────────────────────────────────

@app.route('/delete/<int:log_id>', methods=['POST'])
@login_required
def delete_log(log_id):
    db = db_module.get_db()
    db_module.delete_log(db, log_id, session['user_id'])
    db.close()
    flash('Log entry deleted.', 'success')
    return redirect(request.referrer or url_for('history'))


# ─── Exercise Library ────────────────────────────────────────────────────────

@app.route('/exercises')
@login_required
def exercises():
    return render_template('exercises.html')


# ─── Progress API ─────────────────────────────────────────────────────────────

@app.route('/api/progress/<int:exercise_id>')
@login_required
def progress(exercise_id):
    db   = db_module.get_db()
    rows = db_module.get_progress_data(db, session['user_id'], exercise_id)
    db.close()
    return jsonify({'labels': [r['date'] for r in rows], 'data': [r['max_weight'] for r in rows]})


if __name__ == '__main__':
    app.run(debug=True)
