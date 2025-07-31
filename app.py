import sqlite3
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from datetime import datetime
import json
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)
CORS(app)  # Enable CORS for all origins (adjust as needed)

DATABASE = 'events.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        with open('schema.sql') as f:
            db.executescript(f.read())
        db.commit()

def event_rings_today(freq_json):
    """Check if event rings today based on frequency array of weekdays (JSON string)."""
    weekdays = json.loads(freq_json)
    today = datetime.now().strftime('%A').lower()
    return today in weekdays

# -------------------------
# Normal Events REST APIs
# ------------------------

@app.route('/api/normalEvents', methods=['GET', 'POST'])
def normal_events():
    db = get_db()
    cursor = db.cursor()

    if request.method == 'GET':
        cursor.execute("SELECT * FROM normalEvents")
        rows = cursor.fetchall()
        events = [dict(row) for row in rows]
        for ev in events:
            ev['frequency'] = json.loads(ev['frequency'])
            ev['active'] = bool(ev['active'])
        return jsonify(events)

    if request.method == 'POST':
        data = request.json
        required_fields = ['title', 'time', 'delay', 'tone', 'active', 'frequency']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return jsonify({'error': f'Missing fields: {", ".join(missing)}'}), 400
        try:
            freq_json = json.dumps(data['frequency'])
            cursor.execute("""
                INSERT INTO normalEvents (title, time, delay, tone, active, frequency)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (data['title'], data['time'], data['delay'], data['tone'], int(data['active']), freq_json))
            db.commit()
            return jsonify({'message': 'normalEvent created', 'id': cursor.lastrowid}), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/normalEvents/<int:event_id>', methods=['GET', 'PUT', 'DELETE'])
def normal_event_detail(event_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM normalEvents WHERE id = ?", (event_id,))
    event = cursor.fetchone()
    if not event:
        return jsonify({'error': 'Event not found'}), 404

    if request.method == 'GET':
        ev = dict(event)
        ev['frequency'] = json.loads(ev['frequency'])
        ev['active'] = bool(ev['active'])
        return jsonify(ev)

    if request.method == 'PUT':
        data = request.json
        fields = []
        values = []
        for field in ['title', 'time', 'delay', 'tone', 'active', 'frequency']:
            if field in data:
                if field == 'frequency':
                    fields.append(f"{field} = ?")
                    values.append(json.dumps(data[field]))
                elif field == 'active':
                    fields.append(f"{field} = ?")
                    values.append(int(data[field]))
                else:
                    fields.append(f"{field} = ?")
                    values.append(data[field])
        if not fields:
            return jsonify({'error': 'No fields to update'}), 400
        values.append(event_id)

        query = f"UPDATE normalEvents SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(query, values)
        db.commit()
        return jsonify({'message': 'normalEvent updated'})

    if request.method == 'DELETE':
        cursor.execute("DELETE FROM normalEvents WHERE id = ?", (event_id,))
        db.commit()
        return jsonify({'message': 'normalEvent deleted'})

# -------------------------
# Special Events REST APIs
# -------------------------

@app.route('/api/specialEvents', methods=['GET', 'POST'])
def special_events():
    db = get_db()
    cursor = db.cursor()

    if request.method == 'GET':
        cursor.execute("SELECT * FROM specialEvents")
        rows = cursor.fetchall()
        events = [dict(row) for row in rows]
        for ev in events:
            ev['completed'] = bool(ev['completed'])
        return jsonify(events)

    if request.method == 'POST':
        data = request.json
        required_fields = ['date', 'time', 'description', 'tone', 'completed']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return jsonify({'error': f'Missing fields: {", ".join(missing)}'}), 400
        try:
            cursor.execute("""
                INSERT INTO specialEvents (date, time, description, tone, completed)
                VALUES (?, ?, ?, ?, ?)
            """, (data['date'], data['time'], data['description'], data['tone'], int(data['completed'])))
            db.commit()
            return jsonify({'message': 'specialEvent created', 'id': cursor.lastrowid}), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/specialEvents/<int:event_id>', methods=['GET', 'PUT', 'DELETE'])
def special_event_detail(event_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM specialEvents WHERE id = ?", (event_id,))
    event = cursor.fetchone()
    if not event:
        return jsonify({'error': 'Event not found'}), 404

    if request.method == 'GET':
        ev = dict(event)
        ev['completed'] = bool(ev['completed'])
        return jsonify(ev)

    if request.method == 'PUT':
        data = request.json
        fields = []
        values = []
        for field in ['date', 'time', 'description', 'tone', 'completed']:
            if field in data:
                if field == 'completed':
                    fields.append(f"{field} = ?")
                    values.append(int(data[field]))
                else:
                    fields.append(f"{field} = ?")
                    values.append(data[field])
        if not fields:
            return jsonify({'error': 'No fields to update'}), 400
        values.append(event_id)

        query = f"UPDATE specialEvents SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(query, values)
        db.commit()
        return jsonify({'message': 'specialEvent updated'})

    if request.method == 'DELETE':
        cursor.execute("DELETE FROM specialEvents WHERE id = ?", (event_id,))
        db.commit()
        return jsonify({'message': 'specialEvent deleted'})

# -------------------------
# ESP32 Table API
# -------------------------

@app.route('/api/esp32', methods=['GET'])
def get_esp32_events():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM esp32 ORDER BY time")
    events = [dict(row) for row in cursor.fetchall()]
    return jsonify(events)

def update_esp32_table():
    """Update esp32 table with today's active events from normalEvents and specialEvents."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        today_str = datetime.now().strftime('%Y-%m-%d')

        # Clear esp32 table
        cursor.execute("DELETE FROM esp32")

        # Select active normalEvents that ring today
        cursor.execute("SELECT * FROM normalEvents WHERE active = 1")
        normal_events = [row for row in cursor.fetchall() if event_rings_today(row['frequency'])]

        for ev in normal_events:
            cursor.execute(
                "INSERT INTO esp32 (title, time, delay, source) VALUES (?, ?, ?, 'normal')",
                (ev['title'], ev['time'], ev['delay'])
            )

        # Select specialEvents for today that are not completed
        cursor.execute("SELECT * FROM specialEvents WHERE date = ? AND completed = 0", (today_str,))
        special_events = cursor.fetchall()

        for ev in special_events:
            cursor.execute(
                "INSERT INTO esp32 (title, time, delay, source) VALUES (?, ?, ?, 'special')",
                (ev['description'], ev['time'], 0)
            )

        db.commit()

@app.route('/api/update_esp32', methods=['POST'])
def update_esp32():
    update_esp32_table()
    return jsonify({'message': 'esp32 table updated automatically'})

# -------------------------
# URL GET routes to add events
# -------------------------

@app.route('/api/normalEvents/add', methods=['GET'])
def add_normal_event_via_url():
    db = get_db()
    cursor = db.cursor()

    title = request.args.get('title')
    time = request.args.get('time')
    delay = request.args.get('delay')
    tone = request.args.get('tone')
    active = request.args.get('active')
    frequency = request.args.get('frequency')

    missing = [f for f in ['title', 'time', 'delay', 'tone', 'active', 'frequency']
               if request.args.get(f) is None]
    if missing:
        return jsonify({'error': f'Missing parameters: {", ".join(missing)}'}), 400

    try:
        delay_int = int(delay)
        active_int = 1 if active.lower() in ['true', '1'] else 0

        try:
            freq_list = json.loads(frequency)
            if not isinstance(freq_list, list):
                raise ValueError()
        except Exception:
            freq_list = [d.strip().lower() for d in frequency.split(',')]

        freq_json = json.dumps(freq_list)

        cursor.execute("""
            INSERT INTO normalEvents (title, time, delay, tone, active, frequency)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, time, delay_int, tone, active_int, freq_json))

        db.commit()
        return jsonify({'message': 'normalEvent added', 'id': cursor.lastrowid}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/specialEvents/add', methods=['GET'])
def add_special_event_via_url():
    db = get_db()
    cursor = db.cursor()

    date = request.args.get('date')
    time = request.args.get('time')
    description = request.args.get('description')
    tone = request.args.get('tone')
    completed = request.args.get('completed')

    missing = [f for f in ['date', 'time', 'description', 'tone', 'completed']
               if request.args.get(f) is None]
    if missing:
        return jsonify({'error': f'Missing parameters: {", ".join(missing)}'}), 400

    try:
        completed_int = 1 if completed.lower() in ['true', '1'] else 0

        cursor.execute("""
            INSERT INTO specialEvents (date, time, description, tone, completed)
            VALUES (?, ?, ?, ?, ?)
        """, (date, time, description, tone, completed_int))

        db.commit()
        return jsonify({'message': 'specialEvent added', 'id': cursor.lastrowid}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# -------------------------
# URL GET route to update normalEvent via query params
# -------------------------

@app.route('/api/normalEvents/update', methods=['GET'])
def update_normal_event_via_url():
    db = get_db()
    cursor = db.cursor()

    event_id = request.args.get('id')
    if not event_id:
        return jsonify({'error': 'Event id is required'}), 400

    fields = {}
    for field in ['title', 'time', 'delay', 'tone', 'active', 'frequency']:
        val = request.args.get(field)
        if val is not None:
            if field == 'active':
                val = 1 if val.lower() in ['true', '1'] else 0
            elif field == 'delay':
                val = int(val)
            elif field == 'frequency':
                try:
                    val_json = json.loads(val)
                    val = json.dumps(val_json)
                except Exception:
                    freq_list = [d.strip().lower() for d in val.split(',')]
                    val = json.dumps(freq_list)
            fields[field] = val

    if not fields:
        return jsonify({'error': 'No valid fields to update provided'}), 400

    set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
    values = list(fields.values()) + [event_id]

    try:
        cursor.execute(f"UPDATE normalEvents SET {set_clause} WHERE id = ?", values)
        db.commit()
        if cursor.rowcount == 0:
            return jsonify({'error': 'Event not found'}), 404
        return jsonify({'message': 'normalEvent updated', 'updated_fields': list(fields.keys())})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# -------------------------
# Run app and start scheduler
# -------------------------

if __name__ == "__main__":
    init_db()

    # Setup APScheduler to update esp32 table every 5 minutes
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=update_esp32_table, trigger="interval", minutes=5)
    scheduler.start()

    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())

    app.run(host='0.0.0.0', debug=True)
