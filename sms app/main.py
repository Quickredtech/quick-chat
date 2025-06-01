from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit, join_room, leave_room
from db import get_db_connection, init_db
from werkzeug.security import generate_password_hash, check_password_hash
import os
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
socketio = SocketIO(app)

init_db()

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        # Check for duplicate phone number (country code + number) if phone is provided in form
        phone = request.form.get('phone')
        if phone:
            user_by_phone = conn.execute('SELECT * FROM users WHERE phone = ?', (phone,)).fetchone()
            if user_by_phone and user_by_phone['username'] != username:
                conn.close()
                error = 'This phone number is already logged in with another account.'
                return render_template('login.html', error=error)
        conn.close()
        if user and check_password_hash(user['password'], password):
            # Check if user has a phone number
            if not user['phone'] or user['phone'].strip() == '':
                error = 'Your account does not have a phone number. Please register again.'
                return render_template('login.html', error=error)
            session['username'] = username
            return redirect(url_for('index'))
        else:
            error = 'Invalid username or password.'
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        phone = request.form['phone']
        conn = get_db_connection()
        try:
            conn.execute('ALTER TABLE users ADD COLUMN phone TEXT')
        except Exception:
            pass  # Ignore if column already exists
        try:
            conn.execute('INSERT INTO users (username, password, phone) VALUES (?, ?, ?)',
                         (username, generate_password_hash(password), phone))
            conn.commit()
            conn.close()
            # Send feedback to GitHub (replace with your repo details and token)
            github_token = os.environ.get('GITHUB_TOKEN')  # Use environment variable instead of hardcoding
            repo = 'https://github.com/Quickredtech/quick-chat'
            issue_title = f'New user registered: {username}'
            issue_body = f'User {username} (Phone: {phone}) registered on {request.host}.'
            headers = {'Authorization': f'token {github_token}'}
            if github_token:
                requests.post(
                    f'https://api.github.com/repos/{repo}/issues',
                    json={'title': issue_title, 'body': issue_body},
                    headers=headers
                )
            return redirect(url_for('login'))
        except Exception as e:
            error = 'Username or phone already exists.'
            conn.close()
    return render_template('login.html', error=error)

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (session['username'],)).fetchone()
    if not user or not user['phone'] or user['phone'].strip() == '':
        session.pop('username', None)
        return redirect(url_for('login'))
    # Load user's contacts
    contacts = conn.execute('SELECT friend_name, friend_mobile FROM contacts WHERE owner_username = ?', (session['username'],)).fetchall()
    # Load previous messages from DB (all messages for now)
    db_messages = conn.execute('SELECT username, message FROM messages ORDER BY timestamp ASC').fetchall()
    conn.close()
    messages = [{'user': m['username'], 'msg': m['message']} for m in db_messages]
    return render_template('chat.html', messages=messages, contacts=contacts, selected_friend=None)

@app.route('/contacts', methods=['GET', 'POST'])
def contacts():
    if 'username' not in session:
        return redirect(url_for('login'))
    error = None
    conn = get_db_connection()
    if request.method == 'POST':
        friend_name = request.form['friend_name']
        country_code = request.form['country_code']
        friend_mobile = request.form['friend_mobile']
        country_code = ''.join(filter(str.isdigit, country_code))
        friend_mobile = ''.join(filter(str.isdigit, friend_mobile))
        full_mobile = f"+{country_code}{friend_mobile}" if country_code and friend_mobile else ''
        friend_username = None
        if not friend_name or not country_code or not friend_mobile:
            error = 'Name, country code, and mobile number are required.'
        else:
            # Check if this phone is registered
            user_row = conn.execute('SELECT username FROM users WHERE phone = ?', (full_mobile,)).fetchone()
            if user_row:
                friend_username = user_row['username']
            try:
                conn.execute('INSERT INTO contacts (owner_username, friend_name, friend_mobile, friend_username) VALUES (?, ?, ?, ?)',
                             (session['username'], friend_name, full_mobile, friend_username))
                conn.commit()
            except Exception as e:
                error = 'Could not add contact. (Maybe already exists)'
    contacts = conn.execute('SELECT friend_name, friend_mobile, friend_username FROM contacts WHERE owner_username = ?', (session['username'],)).fetchall()
    conn.close()
    return render_template('contacts.html', contacts=contacts, error=error)

@app.route('/calls')
def calls():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('calls.html')

@app.route('/updates')
def updates():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    # Count messages grouped by sender for the logged-in user
    updates = conn.execute('''
        SELECT username as sender, COUNT(*) as count
        FROM messages
        WHERE username != ?
        GROUP BY username
        ORDER BY count DESC
    ''', (session['username'],)).fetchall()
    conn.close()
    return render_template('updates.html', updates=updates)

@app.route('/chat/<friend_name>', methods=['GET'])
def chat_with_friend(friend_name):
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    # Check if this friend is in user's contacts
    friend = conn.execute('SELECT * FROM contacts WHERE owner_username = ? AND friend_name = ?', (session['username'], friend_name)).fetchone()
    if not friend:
        conn.close()
        return redirect(url_for('index'))
    # Use friend_username if available for registered users
    chat_username = friend['friend_username'] if friend['friend_username'] else friend['friend_name']
    # Only allow chat if the logged-in user is either the owner or the friend
    if session['username'] != chat_username and session['username'] != friend['owner_username']:
        conn.close()
        return redirect(url_for('index'))
    # Load messages between the logged-in user and this friend (by username)
    db_messages = conn.execute('SELECT username, message FROM messages WHERE (username = ? OR username = ?) ORDER BY timestamp ASC', (session['username'], chat_username)).fetchall()
    # Also load undelivered messages if any (for this user as recipient)
    undelivered = conn.execute('SELECT sender, message FROM undelivered_messages WHERE recipient = ?', (session['username'],)).fetchall()
    messages = [{'user': m['username'], 'msg': m['message']} for m in db_messages]
    for u in undelivered:
        messages.append({'user': u['sender'], 'msg': f"(Undelivered): {u['message']}"})
    # Optionally, delete undelivered messages after showing
    conn.execute('DELETE FROM undelivered_messages WHERE recipient = ?', (session['username'],))
    conn.commit()
    conn.close()
    contacts = []  # Optionally pass contacts if needed for sidebar
    return render_template('chat.html', messages=messages, contacts=contacts, selected_friend=friend['friend_name'])

@socketio.on('join')
def on_join(username):
    # No need to store users in memory
    # Send chat history from DB
    conn = get_db_connection()
    db_messages = conn.execute('SELECT username, message FROM messages ORDER BY timestamp ASC').fetchall()
    conn.close()
    messages = [{'user': m['username'], 'msg': m['message']} for m in db_messages]
    emit('history', messages)

@socketio.on('message')
def handle_message(data):
    # Save message to DB
    conn = get_db_connection()
    recipient = data.get('to')
    sender = data['user']
    msg = data['msg']
    # Check if recipient is registered
    user_row = conn.execute('SELECT * FROM users WHERE username = ?', (recipient,)).fetchone()
    if user_row:
        # Check if recipient is online (simple: check if in session, for demo)
        # In production, track online users with SocketIO events
        # For now, always deliver and store
        conn.execute('INSERT INTO messages (username, message) VALUES (?, ?)', (sender, msg))
        conn.commit()
        conn.close()
        emit('message', data, broadcast=True)
    else:
        # Store as undelivered
        conn.execute('INSERT INTO undelivered_messages (sender, recipient, message) VALUES (?, ?, ?)', (sender, recipient, msg))
        conn.commit()
        conn.close()
        # Optionally, notify sender that message is stored for later delivery
        emit('message', {'user': sender, 'msg': f"(Saved for {recipient} until they register/login): {msg}"}, room=request.sid)

@socketio.on('typing')
def handle_typing(data):
    to = data.get('to')
    user = data.get('user')
    emit('typing', {'user': user}, room=request.sid, broadcast=True)

@socketio.on('stop_typing')
def handle_stop_typing(data):
    to = data.get('to')
    user = data.get('user')
    emit('stop_typing', {'user': user}, room=request.sid, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
