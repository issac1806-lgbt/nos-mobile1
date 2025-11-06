from flask import Flask, render_template_string, request, jsonify, session, send_file, send_from_directory
import uuid
from datetime import datetime, timedelta
import threading
import time
import json
import os
import base64
import re
import logging
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
from PIL import Image
import sqlite3
import io
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('NOSComplete')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nos-complete-secure-2024'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

# Create directories
for folder in ['voice', 'images', 'videos', 'documents', 'avatars', 'group_icons', 'status', 'profiles']:
    os.makedirs(f'uploads/{folder}', exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', ping_timeout=60, ping_interval=25)

class CompleteDatabase:
    def __init__(self):
        self.conn = sqlite3.connect('nos_complete.db', check_same_thread=False)
        self.init_complete_tables()
    
    def init_complete_tables(self):
        cursor = self.conn.cursor()
        
        # Enhanced users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            phone_number TEXT UNIQUE,
            display_name TEXT,
            avatar_path TEXT,
            status_text TEXT DEFAULT 'Hey there! I am using NOS',
            online BOOLEAN DEFAULT FALSE,
            last_seen DATETIME,
            created_at DATETIME,
            privacy_settings TEXT,
            blocked_users TEXT,
            theme TEXT DEFAULT 'light',
            language TEXT DEFAULT 'en'
        )
        ''')
        
        # Enhanced messages table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT,
            user_id TEXT,
            message_type TEXT,
            content TEXT,
            file_path TEXT,
            file_size INTEGER,
            duration INTEGER,
            thumbnail TEXT,
            replied_to TEXT,
            forwarded_from TEXT,
            timestamp DATETIME,
            status TEXT,
            read_by TEXT,
            disappearing BOOLEAN DEFAULT FALSE,
            encryption_level INTEGER DEFAULT 0,
            starred BOOLEAN DEFAULT FALSE,
            reactions TEXT
        )
        ''')
        
        # Enhanced groups table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id TEXT PRIMARY KEY,
            name TEXT,
            description TEXT,
            created_by TEXT,
            avatar_path TEXT,
            created_at DATETIME,
            settings TEXT,
            invite_link TEXT,
            admin_only_messages BOOLEAN DEFAULT FALSE,
            disappearing_messages BOOLEAN DEFAULT FALSE
        )
        ''')
        
        # Group members with roles
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_members (
            group_id TEXT,
            user_id TEXT,
            role TEXT DEFAULT 'member',
            joined_at DATETIME,
            added_by TEXT,
            PRIMARY KEY (group_id, user_id)
        )
        ''')
        
        # Contacts
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            user_id TEXT,
            contact_id TEXT,
            name TEXT,
            created_at DATETIME,
            PRIMARY KEY (user_id, contact_id)
        )
        ''')
        
        # Status updates (24-hour stories)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS status_updates (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            type TEXT,
            file_path TEXT,
            text_content TEXT,
            background_color TEXT,
            created_at DATETIME,
            expires_at DATETIME,
            views_count INTEGER DEFAULT 0,
            viewers TEXT
        )
        ''')
        
        # Starred messages
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS starred_messages (
            user_id TEXT,
            message_id TEXT,
            timestamp DATETIME,
            PRIMARY KEY (user_id, message_id)
        )
        ''')
        
        # Broadcast lists
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS broadcast_lists (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            name TEXT,
            recipients TEXT,
            created_at DATETIME
        )
        ''')
        
        # Calls history
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS calls (
            id TEXT PRIMARY KEY,
            call_type TEXT,
            participants TEXT,
            duration INTEGER,
            timestamp DATETIME,
            status TEXT
        )
        ''')
        
        # Message reactions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_reactions (
            message_id TEXT,
            user_id TEXT,
            reaction TEXT,
            timestamp DATETIME,
            PRIMARY KEY (message_id, user_id)
        )
        ''')
        
        self.conn.commit()
    
    def save_user(self, user_data):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO users 
        (id, username, phone_number, display_name, avatar_path, status_text, online, last_seen, created_at, privacy_settings, blocked_users, theme, language)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_data['id'],
            user_data['username'],
            user_data.get('phone_number'),
            user_data.get('display_name'),
            user_data.get('avatar_path'),
            user_data.get('status_text', 'Hey there! I am using NOS'),
            user_data.get('online', False),
            user_data.get('last_seen'),
            user_data.get('created_at'),
            json.dumps(user_data.get('privacy_settings', {})),
            json.dumps(user_data.get('blocked_users', [])),
            user_data.get('theme', 'light'),
            user_data.get('language', 'en')
        ))
        self.conn.commit()
    
    def get_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'username': row[1],
                'phone_number': row[2],
                'display_name': row[3],
                'avatar_path': row[4],
                'status_text': row[5],
                'online': bool(row[6]),
                'last_seen': row[7],
                'created_at': row[8],
                'privacy_settings': json.loads(row[9]) if row[9] else {},
                'blocked_users': json.loads(row[10]) if row[10] else [],
                'theme': row[11],
                'language': row[12]
            }
        return None
    
    def get_user_by_username(self, username):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'username': row[1],
                'phone_number': row[2],
                'display_name': row[3],
                'avatar_path': row[4],
                'status_text': row[5],
                'online': bool(row[6]),
                'last_seen': row[7],
                'created_at': row[8],
                'privacy_settings': json.loads(row[9]) if row[9] else {},
                'blocked_users': json.loads(row[10]) if row[10] else []
            }
        return None
    
    def save_message(self, message_data):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO messages 
        (id, conversation_id, user_id, message_type, content, file_path, file_size, duration, thumbnail, replied_to, forwarded_from, timestamp, status, read_by, disappearing, encryption_level, reactions)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            message_data['id'],
            message_data['conversation_id'],
            message_data['user_id'],
            message_data.get('message_type', 'text'),
            message_data.get('content', ''),
            message_data.get('file_path'),
            message_data.get('file_size'),
            message_data.get('duration'),
            message_data.get('thumbnail'),
            message_data.get('replied_to'),
            message_data.get('forwarded_from'),
            message_data.get('timestamp'),
            message_data.get('status', 'sent'),
            json.dumps(message_data.get('read_by', [])),
            message_data.get('disappearing', False),
            message_data.get('encryption_level', 0),
            json.dumps(message_data.get('reactions', {}))
        ))
        self.conn.commit()
    
    def get_conversation_messages(self, conversation_id, limit=100):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT * FROM messages 
        WHERE conversation_id = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
        ''', (conversation_id, limit))
        rows = cursor.fetchall()
        messages = []
        for row in rows:
            messages.append({
                'id': row[0],
                'conversation_id': row[1],
                'user_id': row[2],
                'message_type': row[3],
                'content': row[4],
                'file_path': row[5],
                'file_size': row[6],
                'duration': row[7],
                'thumbnail': row[8],
                'replied_to': row[9],
                'forwarded_from': row[10],
                'timestamp': row[11],
                'status': row[12],
                'read_by': json.loads(row[13]) if row[13] else [],
                'disappearing': bool(row[14]),
                'encryption_level': row[15],
                'starred': bool(row[16]),
                'reactions': json.loads(row[17]) if row[17] else {}
            })
        return messages[::-1]  # Reverse to get chronological order
    
    def create_group(self, group_data):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO groups 
        (id, name, description, created_by, avatar_path, created_at, settings, invite_link, admin_only_messages, disappearing_messages)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            group_data['id'],
            group_data['name'],
            group_data.get('description', ''),
            group_data['created_by'],
            group_data.get('avatar_path'),
            group_data.get('created_at'),
            json.dumps(group_data.get('settings', {})),
            group_data.get('invite_link'),
            group_data.get('admin_only_messages', False),
            group_data.get('disappearing_messages', False)
        ))
        self.conn.commit()
    
    def add_group_member(self, group_id, user_id, role='member', added_by=None):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO group_members 
        (group_id, user_id, role, joined_at, added_by)
        VALUES (?, ?, ?, ?, ?)
        ''', (group_id, user_id, role, datetime.now().isoformat(), added_by))
        self.conn.commit()
    
    def get_user_groups(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT g.* FROM groups g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE gm.user_id = ?
        ''', (user_id,))
        rows = cursor.fetchall()
        groups = []
        for row in rows:
            groups.append({
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'created_by': row[3],
                'avatar_path': row[4],
                'created_at': row[5],
                'settings': json.loads(row[6]) if row[6] else {},
                'invite_link': row[7],
                'admin_only_messages': bool(row[8]),
                'disappearing_messages': bool(row[9])
            })
        return groups
    
    def add_contact(self, user_id, contact_id, name=None):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO contacts 
        (user_id, contact_id, name, created_at)
        VALUES (?, ?, ?, ?)
        ''', (user_id, contact_id, name, datetime.now().isoformat()))
        self.conn.commit()
    
    def get_user_contacts(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT c.contact_id, u.username, u.display_name, u.avatar_path, u.status_text, u.online, u.last_seen
        FROM contacts c
        JOIN users u ON c.contact_id = u.id
        WHERE c.user_id = ?
        ''', (user_id,))
        rows = cursor.fetchall()
        contacts = []
        for row in rows:
            contacts.append({
                'id': row[0],
                'username': row[1],
                'display_name': row[2],
                'avatar_path': row[3],
                'status_text': row[4],
                'online': bool(row[5]),
                'last_seen': row[6]
            })
        return contacts
    
    def star_message(self, user_id, message_id):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO starred_messages 
        (user_id, message_id, timestamp)
        VALUES (?, ?, ?)
        ''', (user_id, message_id, datetime.now().isoformat()))
        self.conn.commit()
    
    def get_starred_messages(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT m.* FROM messages m
        JOIN starred_messages sm ON m.id = sm.message_id
        WHERE sm.user_id = ?
        ORDER BY sm.timestamp DESC
        ''', (user_id,))
        rows = cursor.fetchall()
        messages = []
        for row in rows:
            messages.append({
                'id': row[0],
                'conversation_id': row[1],
                'user_id': row[2],
                'message_type': row[3],
                'content': row[4],
                'file_path': row[5],
                'file_size': row[6],
                'duration': row[7],
                'thumbnail': row[8],
                'replied_to': row[9],
                'forwarded_from': row[10],
                'timestamp': row[11],
                'status': row[12],
                'read_by': json.loads(row[13]) if row[13] else [],
                'disappearing': bool(row[14]),
                'encryption_level': row[15],
                'starred': bool(row[16]),
                'reactions': json.loads(row[17]) if row[17] else {}
            })
        return messages

db = CompleteDatabase()

# Sample data for demo
def initialize_sample_data():
    # Create sample users if they don't exist
    sample_users = [
        {
            'id': 'user1',
            'username': 'john_doe',
            'display_name': 'John Doe',
            'status_text': 'Available for calls',
            'online': True
        },
        {
            'id': 'user2', 
            'username': 'jane_smith',
            'display_name': 'Jane Smith',
            'status_text': 'Busy right now',
            'online': True
        },
        {
            'id': 'user3',
            'username': 'support',
            'display_name': 'NOS Support',
            'status_text': 'We are here to help!',
            'online': True
        }
    ]
    
    for user_data in sample_users:
        if not db.get_user(user_data['id']):
            user_data.update({
                'created_at': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat(),
                'privacy_settings': {'last_seen': 'everyone', 'profile_photo': 'everyone', 'status': 'everyone'},
                'blocked_users': []
            })
            db.save_user(user_data)
    
    # Create sample group
    sample_group = {
        'id': 'group1',
        'name': 'General Chat',
        'description': 'Welcome to the general chat room',
        'created_by': 'user1',
        'created_at': datetime.now().isoformat(),
        'settings': {},
        'invite_link': f"https://nos.chat/join/{uuid.uuid4()}"
    }
    
    # Check if group exists and create if not
    cursor = db.conn.cursor()
    cursor.execute('SELECT id FROM groups WHERE id = ?', ('group1',))
    if not cursor.fetchone():
        db.create_group(sample_group)
        db.add_group_member('group1', 'user1', 'admin')
        db.add_group_member('group1', 'user2', 'member')
        db.add_group_member('group1', 'user3', 'member')

# Initialize sample data
initialize_sample_data()

@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NOS - Complete Messenger</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
        <style>
            /* Complete WhatsApp-like CSS styles */
            :root {
                --primary-dark: #075E54;
                --primary-main: #128C7E;
                --primary-light: #25D366;
                --accent-main: #34B7F1;
                --background-main: #f0f0f0;
                --surface-main: #ffffff;
                --text-primary: #333333;
                --text-secondary: #666666;
                --border-light: #e0e0e0;
                --status-online: #25D366;
                --status-away: #FFC107;
                --status-busy: #FF4444;
            }

            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }

            body {
                background: var(--background-main);
                color: var(--text-primary);
                height: 100vh;
                overflow: hidden;
            }

            .app-container {
                display: flex;
                height: 100vh;
                max-width: 1400px;
                margin: 0 auto;
                background: var(--surface-main);
                box-shadow: 0 0 20px rgba(0,0,0,0.1);
            }

            /* Sidebar Styles */
            .sidebar {
                width: 380px;
                background: var(--surface-main);
                border-right: 1px solid var(--border-light);
                display: flex;
                flex-direction: column;
            }

            .sidebar-header {
                padding: 20px;
                background: var(--primary-main);
                color: white;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }

            .user-profile {
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .user-avatar {
                width: 50px;
                height: 50px;
                border-radius: 50%;
                background: var(--primary-light);
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: 600;
                font-size: 18px;
                cursor: pointer;
                position: relative;
            }

            .avatar-upload {
                position: absolute;
                bottom: -5px;
                right: -5px;
                background: var(--accent-main);
                width: 20px;
                height: 20px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 12px;
                cursor: pointer;
            }

            .user-info {
                flex: 1;
            }

            .user-name {
                font-weight: 600;
                font-size: 16px;
            }

            .user-status {
                font-size: 13px;
                opacity: 0.9;
            }

            .sidebar-tabs {
                display: flex;
                background: var(--primary-main);
            }

            .sidebar-tab {
                flex: 1;
                padding: 15px;
                text-align: center;
                color: white;
                cursor: pointer;
                border-bottom: 3px solid transparent;
                transition: all 0.2s;
            }

            .sidebar-tab.active {
                background: rgba(255,255,255,0.1);
                border-bottom-color: white;
            }

            .search-container {
                padding: 15px;
                border-bottom: 1px solid var(--border-light);
            }

            .search-input {
                width: 100%;
                padding: 12px 20px;
                border: 1px solid var(--border-light);
                border-radius: 25px;
                font-size: 14px;
                background: var(--background-main);
            }

            .conversation-list {
                flex: 1;
                overflow-y: auto;
            }

            .conversation-item {
                padding: 15px;
                border-bottom: 1px solid var(--border-light);
                cursor: pointer;
                transition: background 0.2s;
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .conversation-item:hover {
                background: var(--background-main);
            }

            .conversation-item.active {
                background: #e8f4fd;
            }

            .conversation-avatar {
                width: 50px;
                height: 50px;
                border-radius: 50%;
                background: var(--primary-main);
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: 600;
                position: relative;
            }

            .online-indicator {
                position: absolute;
                bottom: 2px;
                right: 2px;
                width: 12px;
                height: 12px;
                background: var(--status-online);
                border: 2px solid white;
                border-radius: 50%;
            }

            .conversation-info {
                flex: 1;
            }

            .conversation-header {
                display: flex;
                justify-content: space-between;
                margin-bottom: 4px;
            }

            .conversation-name {
                font-weight: 600;
                font-size: 15px;
            }

            .conversation-time {
                font-size: 12px;
                color: var(--text-secondary);
            }

            .conversation-preview {
                font-size: 13px;
                color: var(--text-secondary);
                display: flex;
                align-items: center;
                gap: 5px;
            }

            /* Chat Area Styles */
            .chat-area {
                flex: 1;
                display: flex;
                flex-direction: column;
            }

            .chat-header {
                padding: 15px 20px;
                background: var(--surface-main);
                border-bottom: 1px solid var(--border-light);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .chat-participant {
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .participant-name {
                font-weight: 600;
                font-size: 16px;
            }

            .participant-status {
                font-size: 13px;
                color: var(--text-secondary);
            }

            .chat-actions {
                display: flex;
                gap: 10px;
            }

            .action-button {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                border: none;
                background: var(--background-main);
                color: var(--text-primary);
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: background 0.2s;
            }

            .action-button:hover {
                background: var(--border-light);
            }

            .call-button {
                background: var(--primary-light);
                color: white;
            }

            .video-call-button {
                background: var(--accent-main);
                color: white;
            }

            .chat-messages {
                flex: 1;
                padding: 20px;
                overflow-y: auto;
                background: var(--background-main);
                display: flex;
                flex-direction: column;
            }

            .message {
                max-width: 65%;
                margin-bottom: 15px;
                padding: 12px 16px;
                border-radius: 18px;
                position: relative;
                animation: messageAppear 0.3s ease-out;
            }

            @keyframes messageAppear {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }

            .message.sent {
                background: var(--primary-light);
                color: white;
                align-self: flex-end;
                border-bottom-right-radius: 5px;
            }

            .message.received {
                background: var(--surface-main);
                color: var(--text-primary);
                border: 1px solid var(--border-light);
                align-self: flex-start;
                border-bottom-left-radius: 5px;
            }

            .message-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 5px;
            }

            .message-sender {
                font-weight: 600;
                font-size: 13px;
            }

            .message-time {
                font-size: 11px;
                opacity: 0.8;
            }

            .message-content {
                line-height: 1.4;
            }

            .message-status {
                display: flex;
                justify-content: flex-end;
                margin-top: 5px;
                font-size: 12px;
            }

            .voice-message {
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 10px;
                background: rgba(255,255,255,0.1);
                border-radius: 10px;
            }

            .voice-play-button {
                width: 30px;
                height: 30px;
                border-radius: 50%;
                background: white;
                color: var(--primary-main);
                border: none;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .voice-duration {
                font-size: 12px;
                color: inherit;
            }

            /* Input Area Styles */
            .input-container {
                padding: 15px 20px;
                background: var(--surface-main);
                border-top: 1px solid var(--border-light);
            }

            .input-wrapper {
                display: flex;
                align-items: flex-end;
                gap: 10px;
            }

            .input-actions {
                display: flex;
                gap: 5px;
            }

            .input-action-button {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                border: none;
                background: var(--background-main);
                color: var(--text-primary);
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: background 0.2s;
            }

            .input-action-button:hover {
                background: var(--border-light);
            }

            .message-input {
                flex: 1;
                padding: 12px 16px;
                border: 1px solid var(--border-light);
                border-radius: 25px;
                font-size: 14px;
                resize: none;
                max-height: 120px;
                background: var(--background-main);
            }

            .send-button {
                width: 44px;
                height: 44px;
                background: var(--primary-main);
                color: white;
                border: none;
                border-radius: 50%;
                cursor: pointer;
                transition: background 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .send-button:hover {
                background: var(--primary-dark);
            }

            .send-button:disabled {
                background: var(--border-light);
                cursor: not-allowed;
            }

            /* Voice Recorder */
            .voice-recorder {
                display: none;
                position: fixed;
                bottom: 80px;
                left: 50%;
                transform: translateX(-50%);
                background: var(--primary-main);
                color: white;
                padding: 20px 30px;
                border-radius: 25px;
                text-align: center;
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                z-index: 1000;
            }

            .recording-indicator {
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 10px;
            }

            .recording-dot {
                width: 12px;
                height: 12px;
                background: #ff4444;
                border-radius: 50%;
                animation: pulse 1s infinite;
            }

            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }

            .recording-time {
                font-size: 14px;
                font-weight: 600;
            }

            .recording-hint {
                font-size: 12px;
                opacity: 0.9;
            }

            /* Call Interface */
            .call-interface {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: #1a1a1a;
                z-index: 2000;
                display: none;
                flex-direction: column;
            }

            .remote-video {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }

            .local-video {
                position: absolute;
                bottom: 100px;
                right: 20px;
                width: 120px;
                height: 160px;
                border-radius: 10px;
                border: 2px solid white;
            }

            .call-info {
                position: absolute;
                top: 50px;
                left: 0;
                right: 0;
                text-align: center;
                color: white;
            }

            .call-participant {
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 5px;
            }

            .call-status {
                font-size: 16px;
                opacity: 0.9;
            }

            .call-controls {
                position: absolute;
                bottom: 30px;
                left: 0;
                right: 0;
                display: flex;
                justify-content: center;
                gap: 20px;
            }

            .call-control-button {
                width: 60px;
                height: 60px;
                border-radius: 50%;
                border: none;
                background: rgba(255,255,255,0.2);
                color: white;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 20px;
                transition: background 0.2s;
            }

            .call-control-button:hover {
                background: rgba(255,255,255,0.3);
            }

            .call-control-button.end-call {
                background: #ff4444;
            }

            .call-control-button.end-call:hover {
                background: #cc0000;
            }

            /* Incoming Call */
            .incoming-call {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: var(--primary-main);
                z-index: 3000;
                display: none;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                color: white;
            }

            .caller-avatar {
                width: 100px;
                height: 100px;
                border-radius: 50%;
                background: var(--primary-light);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 36px;
                font-weight: 600;
                margin-bottom: 20px;
            }

            .caller-name {
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 10px;
            }

            .call-type {
                font-size: 16px;
                opacity: 0.9;
                margin-bottom: 30px;
            }

            .call-actions {
                display: flex;
                gap: 30px;
            }

            .call-action-button {
                width: 70px;
                height: 70px;
                border-radius: 50%;
                border: none;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                transition: transform 0.2s;
            }

            .call-action-button:hover {
                transform: scale(1.1);
            }

            .accept-call {
                background: var(--primary-light);
                color: white;
            }

            .decline-call {
                background: #ff4444;
                color: white;
            }

            /* Status View */
            .status-view {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: black;
                z-index: 4000;
                display: none;
            }

            .status-header {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                padding: 20px;
                background: linear-gradient(transparent, rgba(0,0,0,0.7));
                color: white;
                z-index: 10;
            }

            .status-progress {
                display: flex;
                gap: 2px;
                margin-bottom: 10px;
            }

            .status-progress-bar {
                flex: 1;
                height: 2px;
                background: rgba(255,255,255,0.3);
                border-radius: 1px;
            }

            .status-progress-bar.active {
                background: white;
            }

            .status-user {
                display: flex;
                align-items: center;
                gap: 10px;
            }

            .status-avatar {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: var(--primary-main);
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: 600;
            }

            .status-content {
                width: 100%;
                height: 100%;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .status-image {
                max-width: 100%;
                max-height: 100%;
                object-fit: contain;
            }

            .status-text {
                color: white;
                font-size: 24px;
                text-align: center;
                padding: 20px;
            }

            /* Modal Styles */
            .modal {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                z-index: 5000;
                display: none;
                align-items: center;
                justify-content: center;
            }

            .modal-content {
                background: white;
                border-radius: 15px;
                padding: 30px;
                max-width: 500px;
                width: 90%;
                max-height: 80vh;
                overflow-y: auto;
            }

            .modal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
            }

            .modal-title {
                font-size: 20px;
                font-weight: 600;
                color: var(--primary-main);
            }

            .close-modal {
                background: none;
                border: none;
                font-size: 24px;
                cursor: pointer;
                color: var(--text-secondary);
            }

            /* Responsive Design */
            @media (max-width: 768px) {
                .sidebar {
                    width: 100%;
                }
                
                .chat-area {
                    display: none;
                }
                
                .chat-area.active {
                    display: flex;
                }
            }
        </style>
    </head>
    <body>
        <!-- Login Screen -->
        <div id="loginScreen" style="display: flex; height: 100vh; background: linear-gradient(135deg, var(--primary-main) 0%, var(--primary-dark) 100%); align-items: center; justify-content: center;">
            <div style="background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); width: 100%; max-width: 400px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <div style="font-size: 32px; font-weight: 700; color: var(--primary-main); margin-bottom: 10px;">NOS</div>
                    <div style="font-size: 14px; color: var(--text-secondary);">Complete Messenger</div>
                </div>
                <div style="margin-bottom: 20px;">
                    <input type="text" id="usernameInput" placeholder="Your name" style="width: 100%; padding: 15px; border: 1px solid var(--border-light); border-radius: 8px; font-size: 16px; margin-bottom: 15px;">
                    <input type="tel" id="phoneInput" placeholder="Phone number (optional)" style="width: 100%; padding: 15px; border: 1px solid var(--border-light); border-radius: 8px; font-size: 16px;">
                </div>
                <button onclick="registerUser()" style="width: 100%; padding: 15px; background: var(--primary-main); color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; transition: background 0.2s;">
                    Get Started
                </button>
                <div style="margin-top: 25px; text-align: center;">
                    <div style="font-size: 12px; color: var(--text-secondary); line-height: 1.5;">
                        Voice & Video Calls • Group Chats • Voice Messages<br>
                        File Sharing • End-to-End Encryption • Status Updates
                    </div>
                </div>
            </div>
        </div>

        <!-- Main App -->
        <div id="appContainer" class="app-container" style="display: none;">
            <!-- Sidebar -->
            <div class="sidebar">
                <div class="sidebar-header">
                    <div class="user-profile">
                        <div class="user-avatar" onclick="openProfileSettings()">
                            <span id="userAvatarText">JD</span>
                            <div class="avatar-upload" onclick="event.stopPropagation(); changeAvatar()">+</div>
                        </div>
                        <div class="user-info">
                            <div class="user-name" id="userName">John Doe</div>
                            <div class="user-status" id="userStatus">Online</div>
                        </div>
                    </div>
                    <div class="header-actions">
                        <button class="action-button" onclick="showStatusView()" title="Status">●</button>
                        <button class="action-button" onclick="newChat()" title="New Chat">+</button>
                        <button class="action-button" onclick="showSettings()" title="Menu">⋮</button>
                    </div>
                </div>

                <div class="sidebar-tabs">
                    <div class="sidebar-tab active" onclick="switchTab('chats')">Chats</div>
                    <div class="sidebar-tab" onclick="switchTab('status')">Status</div>
                    <div class="sidebar-tab" onclick="switchTab('calls')">Calls</div>
                    <div class="sidebar-tab" onclick="switchTab('contacts')">Contacts</div>
                </div>

                <div class="search-container">
                    <input type="text" class="search-input" placeholder="Search..." onkeyup="searchConversations(this.value)">
                </div>

                <div class="conversation-list" id="conversationList">
                    <!-- Conversations will be loaded here -->
                </div>
            </div>

            <!-- Chat Area -->
            <div class="chat-area">
                <div class="chat-header">
                    <div class="chat-participant">
                        <div class="conversation-avatar" id="chatAvatar">
                            <span>GC</span>
                            <div class="online-indicator" id="chatOnlineIndicator"></div>
                        </div>
                        <div class="participant-info">
                            <div class="participant-name" id="chatParticipantName">Select a chat</div>
                            <div class="participant-status" id="chatParticipantStatus">Tap on a conversation to start messaging</div>
                        </div>
                    </div>
                    <div class="chat-actions" id="chatActions" style="display: none;">
                        <button class="action-button call-button" onclick="startVoiceCall()" title="Voice Call">📞</button>
                        <button class="action-button video-call-button" onclick="startVideoCall()" title="Video Call">📹</button>
                        <button class="action-button" onclick="showGroupManagement()" title="Group Info" id="groupInfoButton" style="display: none;">ⓘ</button>
                        <button class="action-button" onclick="searchInChat()" title="Search">🔍</button>
                    </div>
                </div>

                <div class="chat-messages" id="chatMessages">
                    <div style="text-align: center; color: var(--text-secondary); padding: 40px; font-size: 14px;">
                        Select a conversation to start messaging
                    </div>
                </div>

                <div class="input-container" id="inputContainer" style="display: none;">
                    <div class="input-wrapper">
                        <div class="input-actions">
                            <button class="input-action-button" onclick="toggleVoiceRecorder()" title="Voice Message">🎤</button>
                            <button class="input-action-button" onclick="attachFile()" title="Attach File">📎</button>
                            <button class="input-action-button" onclick="attachImage()" title="Attach Image">📷</button>
                            <button class="input-action-button" onclick="attachContact()" title="Share Contact">👤</button>
                            <button class="input-action-button" onclick="attachLocation()" title="Share Location">📍</button>
                        </div>
                        <textarea class="message-input" id="messageInput" placeholder="Type a message..." rows="1"></textarea>
                        <button class="send-button" onclick="sendMessage()" id="sendButton" disabled>➤</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Voice Recorder -->
        <div id="voiceRecorder" class="voice-recorder">
            <div class="recording-indicator">
                <div class="recording-dot"></div>
                <div class="recording-time" id="recordingTime">0:00</div>
            </div>
            <div class="recording-hint">Recording... Release to send</div>
        </div>

        <!-- Call Interface -->
        <div id="callInterface" class="call-interface">
            <video id="remoteVideo" class="remote-video" autoplay playsinline></video>
            <video id="localVideo" class="local-video" autoplay playsinline muted></video>
            <div class="call-info">
                <div class="call-participant" id="callParticipantName">John Doe</div>
                <div class="call-status" id="callStatus">Calling...</div>
            </div>
            <div class="call-controls">
                <button class="call-control-button" onclick="toggleMute()" id="muteButton">🎤</button>
                <button class="call-control-button" onclick="toggleVideo()" id="videoButton">📹</button>
                <button class="call-control-button" onclick="toggleSpeaker()" id="speakerButton">🔊</button>
                <button class="call-control-button end-call" onclick="endCall()">📞</button>
            </div>
        </div>

        <!-- Incoming Call -->
        <div id="incomingCall" class="incoming-call">
            <div class="caller-avatar" id="incomingCallerAvatar">JD</div>
            <div class="caller-name" id="incomingCallerName">John Doe</div>
            <div class="call-type" id="incomingCallType">Incoming Voice Call</div>
            <div class="call-actions">
                <button class="call-action-button decline-call" onclick="answerCall(false)">📞</button>
                <button class="call-action-button accept-call" onclick="answerCall(true)">📞</button>
            </div>
        </div>

        <!-- Status View -->
        <div id="statusView" class="status-view">
            <div class="status-header">
                <div class="status-progress" id="statusProgress"></div>
                <div class="status-user">
                    <div class="status-avatar" id="statusUserAvatar">JD</div>
                    <div>
                        <div class="user-name" id="statusUserName">John Doe</div>
                        <div class="status-time" id="statusTime">Just now</div>
                    </div>
                </div>
            </div>
            <div class="status-content" id="statusContent"></div>
        </div>

        <!-- Settings Modal -->
        <div id="settingsModal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <div class="modal-title">Settings</div>
                    <button class="close-modal" onclick="closeSettings()">×</button>
                </div>
                <div class="settings-options">
                    <div class="setting-item" onclick="openProfileSettings()">
                        <div class="setting-icon">👤</div>
                        <div class="setting-text">Profile</div>
                    </div>
                    <div class="setting-item" onclick="openPrivacySettings()">
                        <div class="setting-icon">🔒</div>
                        <div class="setting-text">Privacy</div>
                    </div>
                    <div class="setting-item" onclick="openChatSettings()">
                        <div class="setting-icon">💬</div>
                        <div class="setting-text">Chats</div>
                    </div>
                    <div class="setting-item" onclick="openNotificationSettings()">
                        <div class="setting-icon">🔔</div>
                        <div class="setting-text">Notifications</div>
                    </div>
                    <div class="setting-item" onclick="openStorageSettings()">
                        <div class="setting-icon">💾</div>
                        <div class="setting-text">Storage and Data</div>
                    </div>
                    <div class="setting-item" onclick="openHelp()">
                        <div class="setting-icon">❓</div>
                        <div class="setting-text">Help</div>
                    </div>
                    <div class="setting-item" onclick="logout()">
                        <div class="setting-icon">🚪</div>
                        <div class="setting-text">Log Out</div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // Complete NOS Messenger JavaScript Implementation
            let currentUser = null;
            let socket = null;
            let currentConversation = null;
            let peerConnection = null;
            let localStream = null;
            let remoteStream = null;
            let currentCall = null;
            let mediaRecorder = null;
            let audioChunks = [];
            let recordingInterval = null;
            let recordingTime = 0;
            let isRecording = false;
            let conversations = [];
            let statusUpdates = [];

            // WebRTC Configuration
            const configuration = {
                iceServers: [
                    { urls: 'stun:stun.l.google.com:19302' },
                    { urls: 'stun:stun1.l.google.com:19302' },
                    { urls: 'stun:stun2.l.google.com:19302' },
                    { urls: 'stun:stun3.l.google.com:19302' }
                ]
            };

            // Initialize App
            function initApp() {
                checkAutoLogin();
                setupEventListeners();
            }

            function checkAutoLogin() {
                const savedUser = localStorage.getItem('nosUser');
                if (savedUser) {
                    currentUser = JSON.parse(savedUser);
                    showAppInterface();
                    connectWebSocket();
                    loadConversations();
                    loadStatusUpdates();
                }
            }

            function setupEventListeners() {
                // Message input auto-resize
                const messageInput = document.getElementById('messageInput');
                messageInput.addEventListener('input', function() {
                    this.style.height = 'auto';
                    this.style.height = (this.scrollHeight) + 'px';
                    document.getElementById('sendButton').disabled = this.value.trim() === '';
                });

                // Enter key to send message
                messageInput.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        sendMessage();
                    }
                });

                // Typing indicators
                messageInput.addEventListener('input', function() {
                    if (socket && currentConversation) {
                        socket.emit('typing', {
                            conversation_id: currentConversation.id,
                            typing: true
                        });
                    }
                });

                messageInput.addEventListener('blur', function() {
                    if (socket && currentConversation) {
                        socket.emit('typing', {
                            conversation_id: currentConversation.id,
                            typing: false
                        });
                    }
                });

                // Voice recorder touch events
                document.addEventListener('touchstart', startVoiceRecording);
                document.addEventListener('touchend', stopVoiceRecording);
                document.addEventListener('mousedown', startVoiceRecording);
                document.addEventListener('mouseup', stopVoiceRecording);
            }

            // User Registration
            function registerUser() {
                const username = document.getElementById('usernameInput').value.trim();
                const phone = document.getElementById('phoneInput').value.trim();

                if (!username) {
                    alert('Please enter your name');
                    return;
                }

                fetch('/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        username: username,
                        phone_number: phone
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        currentUser = data.user;
                        localStorage.setItem('nosUser', JSON.stringify(data.user));
                        showAppInterface();
                        connectWebSocket();
                        loadConversations();
                        loadStatusUpdates();
                    } else {
                        alert('Error: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Registration error:', error);
                    alert('Registration failed. Please try again.');
                });
            }

            function showAppInterface() {
                document.getElementById('loginScreen').style.display = 'none';
                document.getElementById('appContainer').style.display = 'flex';

                // Update user info
                document.getElementById('userName').textContent = currentUser.display_name || currentUser.username;
                document.getElementById('userAvatarText').textContent = getInitials(currentUser.display_name || currentUser.username);
                document.getElementById('userStatus').textContent = currentUser.online ? 'Online' : 'Offline';
            }

            // WebSocket Connection
            function connectWebSocket() {
                socket = io({
                    query: {
                        user_id: currentUser.id
                    }
                });

                socket.on('connect', () => {
                    console.log('Connected to NOS server');
                    updateUserStatus(true);
                });

                socket.on('disconnect', () => {
                    console.log('Disconnected from NOS server');
                    updateUserStatus(false);
                });

                // Message events
                socket.on('new_message', handleNewMessage);
                socket.on('message_status', handleMessageStatus);
                socket.on('typing', handleTyping);
                socket.on('stop_typing', handleStopTyping);

                // Call events
                socket.on('incoming_call', handleIncomingCall);
                socket.on('call_accepted', handleCallAccepted);
                socket.on('call_rejected', handleCallRejected);
                socket.on('call_ended', handleCallEnded);
                socket.on('ice_candidate', handleIceCandidate);

                // Group events
                socket.on('group_updated', handleGroupUpdated);
                socket.on('user_joined', handleUserJoined);
                socket.on('user_left', handleUserLeft);

                // Status events
                socket.on('status_updated', handleStatusUpdated);
                socket.on('status_viewed', handleStatusViewed);
            }

            function updateUserStatus(online) {
                currentUser.online = online;
                document.getElementById('userStatus').textContent = online ? 'Online' : 'Offline';
                
                if (socket && socket.connected) {
                    socket.emit('user_status', {
                        online: online,
                        last_seen: new Date().toISOString()
                    });
                }
            }

            // Conversation Management
            function loadConversations() {
                fetch('/api/conversations')
                    .then(response => response.json())
                    .then(data => {
                        conversations = data.conversations;
                        renderConversationList(conversations);
                    })
                    .catch(error => {
                        console.error('Error loading conversations:', error);
                        // Load sample conversations for demo
                        loadSampleConversations();
                    });
            }

            function loadSampleConversations() {
                conversations = [
                    {
                        id: 'general',
                        name: 'General Chat',
                        type: 'group',
                        last_message: 'Welcome to NOS Messenger!',
                        last_activity: new Date().toISOString(),
                        unread_count: 0,
                        avatar_text: 'GC',
                        online: true
                    },
                    {
                        id: 'support',
                        name: 'NOS Support',
                        type: 'user',
                        last_message: 'How can we help you today?',
                        last_activity: new Date().toISOString(),
                        unread_count: 0,
                        avatar_text: 'NS',
                        online: true
                    },
                    {
                        id: 'john',
                        name: 'John Doe',
                        type: 'user',
                        last_message: 'See you at the meeting!',
                        last_activity: new Date(Date.now() - 3600000).toISOString(),
                        unread_count: 2,
                        avatar_text: 'JD',
                        online: false
                    }
                ];
                renderConversationList(conversations);
            }

            function renderConversationList(conversations) {
                const container = document.getElementById('conversationList');
                container.innerHTML = conversations.map(conv => `
                    <div class="conversation-item ${conv.id === currentConversation?.id ? 'active' : ''}" onclick="selectConversation('${conv.id}')">
                        <div class="conversation-avatar">
                            <span>${conv.avatar_text}</span>
                            ${conv.online ? '<div class="online-indicator"></div>' : ''}
                        </div>
                        <div class="conversation-info">
                            <div class="conversation-header">
                                <div class="conversation-name">${conv.name}</div>
                                <div class="conversation-time">${formatTime(conv.last_activity)}</div>
                            </div>
                            <div class="conversation-preview">
                                ${conv.last_message}
                                ${conv.unread_count > 0 ? `<span style="background: #ff4444; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px;">${conv.unread_count}</span>` : ''}
                            </div>
                        </div>
                    </div>
                `).join('');
            }

            function selectConversation(conversationId) {
                const conversation = conversations.find(c => c.id === conversationId);
                if (!conversation) return;

                currentConversation = conversation;

                // Update UI
                document.getElementById('chatParticipantName').textContent = conversation.name;
                document.getElementById('chatAvatar').querySelector('span').textContent = conversation.avatar_text;
                document.getElementById('chatOnlineIndicator').style.display = conversation.online ? 'block' : 'none';
                document.getElementById('chatParticipantStatus').textContent = conversation.online ? 'Online' : 'Offline';

                // Show chat actions and input
                document.getElementById('chatActions').style.display = 'flex';
                document.getElementById('inputContainer').style.display = 'block';
                document.getElementById('groupInfoButton').style.display = conversation.type === 'group' ? 'block' : 'none';

                // Load messages
                loadConversationMessages(conversationId);

                // Update conversation list active state
                document.querySelectorAll('.conversation-item').forEach(item => {
                    item.classList.remove('active');
                });
                event.currentTarget.classList.add('active');

                // Mark as read
                if (conversation.unread_count > 0) {
                    markConversationAsRead(conversationId);
                }
            }

            function loadConversationMessages(conversationId) {
                fetch(`/api/messages/${conversationId}`)
                    .then(response => response.json())
                    .then(data => {
                        renderMessages(data.messages);
                    })
                    .catch(error => {
                        console.error('Error loading messages:', error);
                        // Load sample messages for demo
                        loadSampleMessages();
                    });
            }

            function loadSampleMessages() {
                const messages = [
                    {
                        id: '1',
                        conversation_id: currentConversation.id,
                        user_id: 'system',
                        message_type: 'text',
                        content: 'Welcome to ' + currentConversation.name + '! Start chatting now.',
                        timestamp: new Date().toISOString(),
                        status: 'delivered'
                    }
                ];
                renderMessages(messages);
            }

            function renderMessages(messages) {
                const container = document.getElementById('chatMessages');
                container.innerHTML = '';

                if (messages.length === 0) {
                    container.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 40px; font-size: 14px;">No messages yet. Start the conversation!</div>';
                    return;
                }

                messages.forEach(message => {
                    const isSent = message.user_id === currentUser.id;
                    addMessageToUI(message, isSent);
                });

                container.scrollTop = container.scrollHeight;
            }

            // Message Handling
            function sendMessage() {
                const input = document.getElementById('messageInput');
                const message = input.value.trim();

                if (!message || !currentConversation) return;

                const messageData = {
                    id: generateId(),
                    conversation_id: currentConversation.id,
                    user_id: currentUser.id,
                    message_type: 'text',
                    content: message,
                    timestamp: new Date().toISOString(),
                    status: 'sent'
                };

                // Add to UI immediately
                addMessageToUI(messageData, true);

                // Clear input
                input.value = '';
                input.style.height = 'auto';
                document.getElementById('sendButton').disabled = true;

                // Send via WebSocket
                if (socket) {
                    socket.emit('send_message', messageData);
                }

                // Save to database
                fetch('/api/send_message', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(messageData)
                }).catch(error => {
                    console.error('Error sending message:', error);
                });

                // Stop typing indicator
                if (socket) {
                    socket.emit('typing', {
                        conversation_id: currentConversation.id,
                        typing: false
                    });
                }
            }

            function handleNewMessage(data) {
                if (data.conversation_id === currentConversation?.id) {
                    addMessageToUI(data.message, false);
                } else {
                    // Update conversation list with new message
                    updateConversationPreview(data.conversation_id, data.message);
                }
            }

            function addMessageToUI(messageData, isSent) {
                const messagesContainer = document.getElementById('chatMessages');
                
                // Remove placeholder if exists
                const placeholder = messagesContainer.querySelector('div[style*="text-align: center"]');
                if (placeholder) {
                    placeholder.remove();
                }

                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${isSent ? 'sent' : 'received'}`;
                messageDiv.innerHTML = `
                    ${!isSent ? `
                        <div class="message-header">
                            <div class="message-sender">${messageData.sender || 'User'}</div>
                            <div class="message-time">${formatTime(messageData.timestamp)}</div>
                        </div>
                    ` : ''}
                    <div class="message-content">${messageData.content}</div>
                    ${isSent ? `
                        <div class="message-status">
                            ${messageData.status === 'read' ? '✓✓' : messageData.status === 'delivered' ? '✓✓' : '✓'}
                        </div>
                    ` : ''}
                `;

                messagesContainer.appendChild(messageDiv);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }

            // Voice Messages
            function startVoiceRecording(e) {
                if (!isRecording && currentConversation) {
                    e.preventDefault();
                    isRecording = true;
                    recordingTime = 0;
                    document.getElementById('voiceRecorder').style.display = 'block';
                    
                    recordingInterval = setInterval(() => {
                        recordingTime++;
                        const minutes = Math.floor(recordingTime / 60);
                        const seconds = recordingTime % 60;
                        document.getElementById('recordingTime').textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
                    }, 1000);

                    startAudioRecording();
                }
            }

            function stopVoiceRecording() {
                if (isRecording) {
                    isRecording = false;
                    clearInterval(recordingInterval);
                    document.getElementById('voiceRecorder').style.display = 'none';
                    stopAudioRecording();
                }
            }

            async function startAudioRecording() {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    mediaRecorder = new MediaRecorder(stream);
                    audioChunks = [];

                    mediaRecorder.ondataavailable = (event) => {
                        audioChunks.push(event.data);
                    };

                    mediaRecorder.onstop = async () => {
                        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                        await sendVoiceMessage(audioBlob);
                        stream.getTracks().forEach(track => track.stop());
                    };

                    mediaRecorder.start();
                } catch (error) {
                    console.error('Error starting audio recording:', error);
                    alert('Microphone access is required for voice messages');
                    isRecording = false;
                    document.getElementById('voiceRecorder').style.display = 'none';
                    clearInterval(recordingInterval);
                }
            }

            function stopAudioRecording() {
                if (mediaRecorder && mediaRecorder.state === 'recording') {
                    mediaRecorder.stop();
                }
            }

            async function sendVoiceMessage(audioBlob) {
                if (!currentConversation) return;

                try {
                    const formData = new FormData();
                    formData.append('voice_message', audioBlob);
                    formData.append('conversation_id', currentConversation.id);
                    formData.append('duration', recordingTime);

                    const response = await fetch('/send_voice_message', {
                        method: 'POST',
                        body: formData
                    });

                    const result = await response.json();
                    if (result.success) {
                        console.log('Voice message sent successfully');
                    }
                } catch (error) {
                    console.error('Error sending voice message:', error);
                }
            }

            // Voice and Video Calls
            async function startVoiceCall() {
                if (!currentConversation) return;
                await startCall('voice');
            }

            async function startVideoCall() {
                if (!currentConversation) return;
                await startCall('video');
            }

            async function startCall(callType) {
                try {
                    localStream = await navigator.mediaDevices.getUserMedia({
                        audio: true,
                        video: callType === 'video'
                    });

                    peerConnection = new RTCPeerConnection(configuration);

                    // Add local stream
                    localStream.getTracks().forEach(track => {
                        peerConnection.addTrack(track, localStream);
                    });

                    // Handle remote stream
                    peerConnection.ontrack = (event) => {
                        remoteStream = event.streams[0];
                        document.getElementById('remoteVideo').srcObject = remoteStream;
                    };

                    // Handle ICE candidates
                    peerConnection.onicecandidate = (event) => {
                        if (event.candidate && socket) {
                            socket.emit('ice_candidate', {
                                target_conversation: currentConversation.id,
                                candidate: event.candidate
                            });
                        }
                    };

                    // Create offer
                    const offer = await peerConnection.createOffer();
                    await peerConnection.setLocalDescription(offer);

                    // Send call offer
                    if (socket) {
                        socket.emit('call_offer', {
                            conversation_id: currentConversation.id,
                            call_type: callType,
                            offer: offer
                        });
                    }

                    currentCall = {
                        conversation: currentConversation.id,
                        type: callType,
                        direction: 'outgoing'
                    };

                    showCallInterface();
                } catch (error) {
                    console.error('Error starting call:', error);
                    alert(`Error starting ${callType} call: ${error.message}`);
                }
            }

            function handleIncomingCall(data) {
                currentCall = {
                    conversation: data.conversation_id,
                    type: data.call_type,
                    direction: 'incoming',
                    offer: data.offer,
                    caller: data.caller
                };

                document.getElementById('incomingCallerName').textContent = data.caller_name || 'Incoming Call';
                document.getElementById('incomingCallType').textContent = data.call_type === 'video' ? 'Incoming Video Call' : 'Incoming Voice Call';
                document.getElementById('incomingCall').style.display = 'flex';
            }

            async function answerCall(accept) {
                document.getElementById('incomingCall').style.display = 'none';

                if (!accept) {
                    if (socket) {
                        socket.emit('call_rejected', {
                            conversation_id: currentCall.conversation
                        });
                    }
                    currentCall = null;
                    return;
                }

                try {
                    localStream = await navigator.mediaDevices.getUserMedia({
                        audio: true,
                        video: currentCall.type === 'video'
                    });

                    peerConnection = new RTCPeerConnection(configuration);

                    // Add local stream
                    localStream.getTracks().forEach(track => {
                        peerConnection.addTrack(track, localStream);
                    });

                    // Handle remote stream
                    peerConnection.ontrack = (event) => {
                        remoteStream = event.streams[0];
                        document.getElementById('remoteVideo').srcObject = remoteStream;
                    };

                    // Handle ICE candidates
                    peerConnection.onicecandidate = (event) => {
                        if (event.candidate && socket) {
                            socket.emit('ice_candidate', {
                                target_conversation: currentCall.conversation,
                                candidate: event.candidate
                            });
                        }
                    };

                    // Set remote description and create answer
                    await peerConnection.setRemoteDescription(currentCall.offer);
                    const answer = await peerConnection.createAnswer();
                    await peerConnection.setLocalDescription(answer);

                    // Send answer
                    if (socket) {
                        socket.emit('call_answer', {
                            conversation_id: currentCall.conversation,
                            answer: answer
                        });
                    }

                    showCallInterface();
                } catch (error) {
                    console.error('Error answering call:', error);
                    alert('Error answering call: ' + error.message);
                }
            }

            function handleCallAccepted(data) {
                if (peerConnection) {
                    peerConnection.setRemoteDescription(data.answer);
                }
            }

            function handleCallEnded() {
                endCall();
            }

            function handleIceCandidate(data) {
                if (peerConnection) {
                    peerConnection.addIceCandidate(data.candidate);
                }
            }

            function showCallInterface() {
                document.getElementById('callInterface').style.display = 'flex';
                document.getElementById('localVideo').srcObject = localStream;
                document.getElementById('callParticipantName').textContent = currentConversation?.name || 'Call';
                document.getElementById('callStatus').textContent = 'Connected';
            }

            function endCall() {
                if (peerConnection) {
                    peerConnection.close();
                    peerConnection = null;
                }

                if (localStream) {
                    localStream.getTracks().forEach(track => track.stop());
                    localStream = null;
                }

                document.getElementById('callInterface').style.display = 'none';
                document.getElementById('incomingCall').style.display = 'none';

                if (socket && currentCall) {
                    socket.emit('end_call', {
                        conversation_id: currentCall.conversation
                    });
                }

                currentCall = null;
            }

            function toggleMute() {
                if (localStream) {
                    const audioTrack = localStream.getAudioTracks()[0];
                    audioTrack.enabled = !audioTrack.enabled;
                    document.getElementById('muteButton').style.background = audioTrack.enabled ? 'rgba(255,255,255,0.2)' : '#ff4444';
                }
            }

            function toggleVideo() {
                if (localStream) {
                    const videoTrack = localStream.getVideoTracks()[0];
                    if (videoTrack) {
                        videoTrack.enabled = !videoTrack.enabled;
                        document.getElementById('videoButton').style.background = videoTrack.enabled ? 'rgba(255,255,255,0.2)' : '#ff4444';
                    }
                }
            }

            function toggleSpeaker() {
                // Toggle speaker phone (would need additional audio context)
                alert('Speaker toggle would be implemented here');
            }

            // Status Updates
            function loadStatusUpdates() {
                fetch('/api/status_updates')
                    .then(response => response.json())
                    .then(data => {
                        statusUpdates = data.status_updates;
                        renderStatusList();
                    })
                    .catch(error => {
                        console.error('Error loading status updates:', error);
                    });
            }

            function renderStatusList() {
                // This would render the status list in the status tab
            }

            function showStatusView() {
                document.getElementById('statusView').style.display = 'block';
                // Load and display status updates
            }

            // Utility Functions
            function generateId() {
                return Date.now().toString() + Math.random().toString(36).substr(2, 9);
            }

            function formatTime(timestamp) {
                const date = new Date(timestamp);
                const now = new Date();
                const diff = now - date;

                if (diff < 60000) return 'Just now';
                if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago';
                if (diff < 86400000) return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                return date.toLocaleDateString();
            }

            function getInitials(name) {
                return name.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2);
            }

            function switchTab(tabName) {
                // Update tab UI
                document.querySelectorAll('.sidebar-tab').forEach(tab => {
                    tab.classList.remove('active');
                });
                event.target.classList.add('active');

                // Load appropriate content
                switch(tabName) {
                    case 'chats':
                        loadConversations();
                        break;
                    case 'status':
                        loadStatusUpdates();
                        break;
                    case 'calls':
                        loadCallHistory();
                        break;
                    case 'contacts':
                        loadContacts();
                        break;
                }
            }

            function searchConversations(query) {
                const filtered = conversations.filter(conv => 
                    conv.name.toLowerCase().includes(query.toLowerCase()) ||
                    conv.last_message.toLowerCase().includes(query.toLowerCase())
                );
                renderConversationList(filtered);
            }

            function searchInChat() {
                const query = prompt('Search in conversation:');
                if (query) {
                    // Highlight and scroll to matching messages
                    alert(`Would search for: ${query}`);
                }
            }

            function newChat() {
                const username = prompt('Enter username or phone number:');
                if (username) {
                    // Create new conversation
                    alert(`Would start chat with: ${username}`);
                }
            }

            function showSettings() {
                document.getElementById('settingsModal').style.display = 'flex';
            }

            function closeSettings() {
                document.getElementById('settingsModal').style.display = 'none';
            }

            function openProfileSettings() {
                alert('Profile settings would open here');
            }

            function attachFile() {
                const input = document.createElement('input');
                input.type = 'file';
                input.onchange = (e) => {
                    const file = e.target.files[0];
                    if (file) {
                        sendFileMessage(file);
                    }
                };
                input.click();
            }

            function attachImage() {
                const input = document.createElement('input');
                input.type = 'file';
                input.accept = 'image/*';
                input.onchange = (e) => {
                    const file = e.target.files[0];
                    if (file) {
                        sendImageMessage(file);
                    }
                };
                input.click();
            }

            function attachContact() {
                alert('Contact sharing would be implemented here');
            }

            function attachLocation() {
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition((position) => {
                        const { latitude, longitude } = position.coords;
                        sendLocationMessage(latitude, longitude);
                    }, (error) => {
                        alert('Unable to get location: ' + error.message);
                    });
                } else {
                    alert('Geolocation is not supported by this browser.');
                }
            }

            function sendFileMessage(file) {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('conversation_id', currentConversation.id);

                fetch('/send_file', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        console.log('File sent successfully');
                    }
                })
                .catch(error => {
                    console.error('Error sending file:', error);
                });
            }

            function sendImageMessage(file) {
                const formData = new FormData();
                formData.append('image', file);
                formData.append('conversation_id', currentConversation.id);

                fetch('/send_image', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        console.log('Image sent successfully');
                    }
                })
                .catch(error => {
                    console.error('Error sending image:', error);
                });
            }

            function sendLocationMessage(latitude, longitude) {
                const messageData = {
                    id: generateId(),
                    conversation_id: currentConversation.id,
                    user_id: currentUser.id,
                    message_type: 'location',
                    content: `Location: ${latitude}, ${longitude}`,
                    timestamp: new Date().toISOString(),
                    status: 'sent',
                    location: { latitude, longitude }
                };

                if (socket) {
                    socket.emit('send_message', messageData);
                }
            }

            function logout() {
                if (confirm('Are you sure you want to log out?')) {
                    localStorage.removeItem('nosUser');
                    location.reload();
                }
            }

            // Initialize the app when page loads
            document.addEventListener('DOMContentLoaded', initApp);
        </script>
    </body>
    </html>
    ''')

# API Routes
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        phone_number = data.get('phone_number', '').strip()

        if not username:
            return jsonify({'success': False, 'error': 'Username is required'})

        # Check if user already exists
        existing_user = db.get_user_by_username(username)
        if existing_user:
            return jsonify({'success': True, 'user': existing_user})

        user_id = str(uuid.uuid4())[:8]
        user_data = {
            'id': user_id,
            'username': username,
            'phone_number': phone_number,
            'display_name': username,
            'status_text': 'Hey there! I am using NOS',
            'online': True,
            'last_seen': datetime.now().isoformat(),
            'created_at': datetime.now().isoformat(),
            'privacy_settings': {
                'last_seen': 'everyone',
                'profile_photo': 'everyone',
                'status': 'everyone'
            },
            'blocked_users': [],
            'theme': 'light',
            'language': 'en'
        }

        db.save_user(user_data)
        session['user_id'] = user_id

        return jsonify({
            'success': True,
            'user': user_data
        })

    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'success': False, 'error': 'Registration failed'})

@app.route('/api/conversations')
def get_conversations():
    user_id = request.args.get('user_id') or session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'})

    # Get user's groups
    groups = db.get_user_groups(user_id)
    
    # Get user's contacts
    contacts = db.get_user_contacts(user_id)
    
    conversations = []
    
    # Add groups to conversations
    for group in groups:
        # Get last message for the group
        messages = db.get_conversation_messages(group['id'], limit=1)
        last_message = messages[0] if messages else None
        
        conversations.append({
            'id': group['id'],
            'name': group['name'],
            'type': 'group',
            'last_message': last_message['content'] if last_message else 'No messages yet',
            'last_activity': last_message['timestamp'] if last_message else group['created_at'],
            'unread_count': 0,
            'avatar_text': ''.join([word[0] for word in group['name'].split()[:2]]).upper(),
            'online': True
        })
    
    # Add contacts to conversations
    for contact in contacts:
        # Create conversation ID (combination of user IDs)
        conversation_id = f"private_{min(user_id, contact['id'])}_{max(user_id, contact['id'])}"
        
        # Get last message for the conversation
        messages = db.get_conversation_messages(conversation_id, limit=1)
        last_message = messages[0] if messages else None
        
        conversations.append({
            'id': conversation_id,
            'name': contact['display_name'] or contact['username'],
            'type': 'user',
            'last_message': last_message['content'] if last_message else 'Start a conversation',
            'last_activity': last_message['timestamp'] if last_message else contact['last_seen'],
            'unread_count': 0,
            'avatar_text': get_initials(contact['display_name'] or contact['username']),
            'online': contact['online']
        })
    
    return jsonify({'success': True, 'conversations': conversations})

@app.route('/api/messages/<conversation_id>')
def get_messages(conversation_id):
    messages = db.get_conversation_messages(conversation_id, limit=100)
    return jsonify({'success': True, 'messages': messages})

@app.route('/api/send_message', methods=['POST'])
def api_send_message():
    try:
        data = request.get_json()
        db.save_message(data)
        
        # Broadcast to other users in the conversation
        socketio.emit('new_message', {
            'conversation_id': data['conversation_id'],
            'message': data
        })
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return jsonify({'success': False, 'error': 'Failed to send message'})

@app.route('/send_voice_message', methods=['POST'])
def send_voice_message():
    try:
        if 'voice_message' not in request.files:
            return jsonify({'success': False, 'error': 'No voice message'})

        voice_file = request.files['voice_message']
        conversation_id = request.form.get('conversation_id')
        duration = request.form.get('duration', 0)
        user_id = session.get('user_id')

        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'})

        user = db.get_user(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'})

        # Save voice file
        filename = f"voice_{uuid.uuid4()}.wav"
        filepath = os.path.join('uploads/voice', filename)
        voice_file.save(filepath)

        # Create message
        message_data = {
            'id': str(uuid.uuid4()),
            'conversation_id': conversation_id,
            'user_id': user_id,
            'message_type': 'voice',
            'file_path': filepath,
            'duration': duration,
            'timestamp': datetime.now().isoformat(),
            'status': 'sent'
        }

        db.save_message(message_data)

        # Broadcast message
        socketio.emit('new_message', {
            'conversation_id': conversation_id,
            'message': message_data
        })

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Voice message error: {e}")
        return jsonify({'success': False, 'error': 'Failed to send voice message'})

@app.route('/send_file', methods=['POST'])
def send_file():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file'})

        file = request.files['file']
        conversation_id = request.form.get('conversation_id')
        user_id = session.get('user_id')

        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'})

        filename = secure_filename(file.filename)
        filepath = os.path.join('uploads/documents', f"{uuid.uuid4()}_{filename}")
        file.save(filepath)

        message_data = {
            'id': str(uuid.uuid4()),
            'conversation_id': conversation_id,
            'user_id': user_id,
            'message_type': 'file',
            'content': filename,
            'file_path': filepath,
            'file_size': os.path.getsize(filepath),
            'timestamp': datetime.now().isoformat(),
            'status': 'sent'
        }

        db.save_message(message_data)
        socketio.emit('new_message', {
            'conversation_id': conversation_id,
            'message': message_data
        })

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"File send error: {e}")
        return jsonify({'success': False, 'error': 'Failed to send file'})

@app.route('/send_image', methods=['POST'])
def send_image():
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image'})

        image_file = request.files['image']
        conversation_id = request.form.get('conversation_id')
        user_id = session.get('user_id')

        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'})

        filename = f"image_{uuid.uuid4()}.jpg"
        filepath = os.path.join('uploads/images', filename)
        image_file.save(filepath)

        # Create thumbnail
        try:
            with Image.open(filepath) as img:
                img.thumbnail((200, 200))
                thumbnail_path = os.path.join('uploads/images', f"thumb_{filename}")
                img.save(thumbnail_path, 'JPEG')
        except Exception as e:
            logger.error(f"Thumbnail creation error: {e}")
            thumbnail_path = None

        message_data = {
            'id': str(uuid.uuid4()),
            'conversation_id': conversation_id,
            'user_id': user_id,
            'message_type': 'image',
            'content': 'Image',
            'file_path': filepath,
            'thumbnail': thumbnail_path,
            'file_size': os.path.getsize(filepath),
            'timestamp': datetime.now().isoformat(),
            'status': 'sent'
        }

        db.save_message(message_data)
        socketio.emit('new_message', {
            'conversation_id': conversation_id,
            'message': message_data
        })

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Image send error: {e}")
        return jsonify({'success': False, 'error': 'Failed to send image'})

@app.route('/api/status_updates')
def get_status_updates():
    # This would return the user's status updates and contacts' statuses
    return jsonify({'success': True, 'status_updates': []})

# WebSocket Events
@socketio.on('connect')
def handle_connect():
    user_id = request.args.get('user_id')
    if user_id:
        user = db.get_user(user_id)
        if user:
            user['online'] = True
            user['last_seen'] = datetime.now().isoformat()
            db.save_user(user)
            logger.info(f"User {user['username']} connected")

@socketio.on('disconnect')
def handle_disconnect():
    user_id = request.args.get('user_id')
    if user_id:
        user = db.get_user(user_id)
        if user:
            user['online'] = False
            user['last_seen'] = datetime.now().isoformat()
            db.save_user(user)
            logger.info(f"User {user['username']} disconnected")

@socketio.on('send_message')
def handle_send_message(data):
    # Save message to database
    db.save_message(data)
    
    # Broadcast to all users in the conversation
    socketio.emit('new_message', {
        'conversation_id': data['conversation_id'],
        'message': data
    })

@socketio.on('typing')
def handle_typing(data):
    # Broadcast typing indicator to other users in the conversation
    socketio.emit('typing', {
        'conversation_id': data['conversation_id'],
        'user_id': data.get('user_id'),
        'typing': data['typing']
    }, room=data['conversation_id'])

@socketio.on('call_offer')
def handle_call_offer(data):
    # Broadcast call offer to the conversation
    socketio.emit('incoming_call', {
        'conversation_id': data['conversation_id'],
        'call_type': data['call_type'],
        'offer': data['offer'],
        'caller': data.get('caller')
    }, room=data['conversation_id'])

@socketio.on('call_answer')
def handle_call_answer(data):
    # Broadcast call answer
    socketio.emit('call_accepted', {
        'conversation_id': data['conversation_id'],
        'answer': data['answer']
    }, room=data['conversation_id'])

@socketio.on('end_call')
def handle_end_call(data):
    # Broadcast call end
    socketio.emit('call_ended', {
        'conversation_id': data['conversation_id']
    }, room=data['conversation_id'])

@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    # Broadcast ICE candidate
    socketio.emit('ice_candidate', {
        'conversation_id': data['target_conversation'],
        'candidate': data['candidate']
    }, room=data['target_conversation'])

# Utility function
def get_initials(name):
    return ''.join([word[0] for word in name.split()[:2]]).upper()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Use this for production
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
