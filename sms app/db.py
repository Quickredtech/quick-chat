import sqlite3

def get_db_connection():
    conn = sqlite3.connect('chatapp.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_username TEXT NOT NULL,
                friend_name TEXT NOT NULL,
                friend_mobile TEXT NOT NULL,
                friend_username TEXT
            )
        ''')
        # Ensure 'phone' column exists in users table
        user_cols = conn.execute("PRAGMA table_info(users)").fetchall()
        if not any(col['name'] == 'phone' for col in user_cols):
            conn.execute('ALTER TABLE users ADD COLUMN phone TEXT')
            conn.commit()
        # Ensure 'friend_username' column exists in contacts table
        contact_cols = conn.execute("PRAGMA table_info(contacts)").fetchall()
        if not any(col['name'] == 'friend_username' for col in contact_cols):
            conn.execute('ALTER TABLE contacts ADD COLUMN friend_username TEXT')
            conn.commit()
        # Add a new table for undelivered messages
        conn.execute('''
            CREATE TABLE IF NOT EXISTS undelivered_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    conn.close()
