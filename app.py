from flask import Flask, render_template_string, request, jsonify, session
import uuid
from datetime import datetime
import os
import json
import sqlite3
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'whatsapp-clone-secure-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Database setup
def init_db():
    conn = sqlite3.connect('whatsapp.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id TEXT PRIMARY KEY, username TEXT UNIQUE, display_name TEXT, 
                  user_code TEXT UNIQUE, online INTEGER DEFAULT 0, last_seen TEXT,
                  avatar_color TEXT, created_at TEXT)''')
    
    # Friend requests
    c.execute('''CREATE TABLE IF NOT EXISTS friend_requests
                 (id TEXT PRIMARY KEY, from_user_id TEXT, to_user_id TEXT,
                  status TEXT DEFAULT 'pending', created_at TEXT)''')
    
    # Friends
    c.execute('''CREATE TABLE IF NOT EXISTS friends
                 (user_id TEXT, friend_id TEXT, created_at TEXT,
                  PRIMARY KEY (user_id, friend_id))''')
    
    # Conversations
    c.execute('''CREATE TABLE IF NOT EXISTS conversations
                 (id TEXT PRIMARY KEY, name TEXT, is_group INTEGER DEFAULT 0,
                  created_by TEXT, created_at TEXT)''')
    
    # Conversation participants
    c.execute('''CREATE TABLE IF NOT EXISTS conversation_participants
                 (conversation_id TEXT, user_id TEXT,
                  PRIMARY KEY (conversation_id, user_id))''')
    
    # Messages
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id TEXT PRIMARY KEY, conversation_id TEXT, user_id TEXT,
                  content TEXT, message_type TEXT DEFAULT 'text',
                  timestamp TEXT, status TEXT DEFAULT 'sent')''')
    
    # Active calls
    c.execute('''CREATE TABLE IF NOT EXISTS active_calls
                 (id TEXT PRIMARY KEY, from_user_id TEXT, to_user_id TEXT,
                  conversation_id TEXT, call_type TEXT, status TEXT,
                  created_at TEXT)''')
    
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect('whatsapp.db')
    conn.row_factory = sqlite3.Row
    return conn

# Utility functions
def generate_user_code():
    return str(uuid.uuid4())[:8].upper()

def get_user_initial(name):
    return name[0].upper() if name else 'U'

def get_avatar_color(user_id):
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']
    return colors[hash(user_id) % len(colors)]

# Routes
@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>WhatsApp Clone</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Segoe UI', sans-serif; 
                background: #111b21; 
                color: white;
                height: 100vh;
                overflow: hidden;
            }
            .app-container {
                display: flex;
                height: 100vh;
                max-width: 1600px;
                margin: 0 auto;
                background: #222e35;
            }
            .sidebar {
                width: 400px;
                background: #2a3942;
                border-right: 1px solid #333;
                display: flex;
                flex-direction: column;
            }
            .sidebar-header {
                padding: 20px;
                background: #202c33;
                display: flex;
                align-items: center;
                gap: 15px;
            }
            .user-avatar {
                width: 50px;
                height: 50px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-size: 20px;
                color: white;
            }
            .user-info {
                flex: 1;
            }
            .user-name {
                font-weight: 600;
                font-size: 18px;
            }
            .user-status {
                font-size: 14px;
                color: #8696a0;
            }
            .user-code {
                font-size: 12px;
                color: #00a884;
                margin-top: 2px;
            }
            .sidebar-tabs {
                display: flex;
                background: #202c33;
            }
            .tab {
                flex: 1;
                padding: 15px;
                text-align: center;
                cursor: pointer;
                border-bottom: 3px solid transparent;
                transition: all 0.3s;
            }
            .tab.active {
                border-bottom-color: #00a884;
                color: #00a884;
            }
            .search-box {
                padding: 15px;
                background: #202c33;
            }
            .search-box input {
                width: 100%;
                padding: 12px 20px;
                background: #2a3942;
                border: none;
                border-radius: 20px;
                color: white;
                font-size: 14px;
            }
            .content-area {
                flex: 1;
                overflow-y: auto;
            }
            .conversation-item, .friend-item {
                padding: 15px;
                border-bottom: 1px solid #2a3942;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 15px;
                transition: background 0.2s;
            }
            .conversation-item:hover, .friend-item:hover {
                background: #2a3942;
            }
            .conversation-item.active {
                background: #2a3942;
            }
            .item-avatar {
                width: 55px;
                height: 55px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-size: 18px;
                color: white;
            }
            .item-info {
                flex: 1;
            }
            .item-name {
                font-weight: 600;
                font-size: 16px;
                margin-bottom: 5px;
            }
            .item-preview {
                font-size: 14px;
                color: #8696a0;
            }
            .item-status {
                font-size: 12px;
                color: #00a884;
            }
            .chat-area {
                flex: 1;
                display: flex;
                flex-direction: column;
            }
            .chat-header {
                padding: 15px 20px;
                background: #202c33;
                border-bottom: 1px solid #2a3942;
                display: flex;
                align-items: center;
                gap: 15px;
            }
            .chat-avatar {
                width: 50px;
                height: 50px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-size: 18px;
                color: white;
            }
            .chat-info {
                flex: 1;
            }
            .chat-name {
                font-weight: 600;
                font-size: 18px;
            }
            .chat-status {
                font-size: 14px;
                color: #8696a0;
            }
            .chat-actions {
                display: flex;
                gap: 10px;
            }
            .action-btn {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                border: none;
                background: #2a3942;
                color: white;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .messages-container {
                flex: 1;
                padding: 20px;
                overflow-y: auto;
                background: #0b141a;
                background-image: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" opacity="0.03"><path fill="%2300a884" d="M50 0L100 50L50 100L0 50Z"/></svg>');
            }
            .message {
                max-width: 65%;
                margin-bottom: 15px;
                padding: 12px 16px;
                border-radius: 8px;
                position: relative;
                animation: fadeIn 0.3s;
            }
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .message.sent {
                background: #005c4b;
                margin-left: auto;
                border-top-right-radius: 0;
            }
            .message.received {
                background: #202c33;
                margin-right: auto;
                border-top-left-radius: 0;
            }
            .message-content {
                line-height: 1.4;
            }
            .message-time {
                font-size: 11px;
                color: #8696a0;
                text-align: right;
                margin-top: 5px;
            }
            .input-container {
                padding: 15px 20px;
                background: #202c33;
                display: flex;
                align-items: center;
                gap: 15px;
            }
            .input-actions {
                display: flex;
                gap: 10px;
            }
            .input-action {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                border: none;
                background: #2a3942;
                color: white;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .message-input {
                flex: 1;
                padding: 12px 20px;
                background: #2a3942;
                border: none;
                border-radius: 20px;
                color: white;
                font-size: 15px;
                resize: none;
                max-height: 120px;
            }
            .send-btn {
                width: 45px;
                height: 45px;
                border-radius: 50%;
                border: none;
                background: #00a884;
                color: white;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .login-screen {
                display: flex;
                height: 100vh;
                background: linear-gradient(135deg, #00a884 0%, #128c7e 100%);
                align-items: center;
                justify-content: center;
            }
            .login-box {
                background: white;
                padding: 40px;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                width: 90%;
                max-width: 400px;
                text-align: center;
            }
            .login-title {
                color: #128c7e;
                font-size: 32px;
                font-weight: bold;
                margin-bottom: 10px;
            }
            .login-subtitle {
                color: #666;
                margin-bottom: 30px;
            }
            .login-input {
                width: 100%;
                padding: 15px;
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-bottom: 15px;
                font-size: 16px;
            }
            .login-btn {
                width: 100%;
                padding: 15px;
                background: #00a884;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
            }
            .add-friend-btn {
                position: fixed;
                bottom: 20px;
                right: 20px;
                width: 60px;
                height: 60px;
                border-radius: 50%;
                background: #00a884;
                color: white;
                border: none;
                font-size: 24px;
                cursor: pointer;
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
                z-index: 1000;
            }
            .friend-requests {
                padding: 15px;
            }
            .friend-request-item {
                background: #2a3942;
                padding: 15px;
                border-radius: 10px;
                margin-bottom: 10px;
                display: flex;
                align-items: center;
                gap: 15px;
            }
            .request-actions {
                display: flex;
                gap: 10px;
                margin-left: auto;
            }
            .accept-btn, .decline-btn {
                padding: 8px 15px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 14px;
            }
            .accept-btn {
                background: #00a884;
                color: white;
            }
            .decline-btn {
                background: #ff4444;
                color: white;
            }
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
                align-items: center;
                justify-content: center;
            }
            .caller-info {
                text-align: center;
                color: white;
                margin-bottom: 30px;
            }
            .caller-name {
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 10px;
            }
            .call-status {
                font-size: 16px;
                color: #8696a0;
            }
            .call-controls {
                display: flex;
                gap: 20px;
            }
            .call-btn {
                width: 60px;
                height: 60px;
                border-radius: 50%;
                border: none;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 20px;
            }
            .accept-call {
                background: #00a884;
                color: white;
            }
            .decline-call {
                background: #ff4444;
                color: white;
            }
            .end-call {
                background: #ff4444;
                color: white;
            }
        </style>
    </head>
    <body>
        <div id="loginScreen" class="login-screen">
            <div class="login-box">
                <div class="login-title">WhatsApp</div>
                <div class="login-subtitle">Complete Messenger with All Features</div>
                <input type="text" id="usernameInput" class="login-input" placeholder="Enter your name">
                <button onclick="login()" class="login-btn">Get Started</button>
            </div>
        </div>

        <div id="appContainer" class="app-container" style="display: none;">
            <div class="sidebar">
                <div class="sidebar-header">
                    <div class="user-avatar" id="userAvatar" style="background: #FF6B6B;">U</div>
                    <div class="user-info">
                        <div class="user-name" id="userName">User</div>
                        <div class="user-status" id="userStatus">Online</div>
                        <div class="user-code" id="userCode">CODE: --------</div>
                    </div>
                </div>
                
                <div class="sidebar-tabs">
                    <div class="tab active" onclick="switchTab('chats')">Chats</div>
                    <div class="tab" onclick="switchTab('friends')">Friends</div>
                    <div class="tab" onclick="switchTab('requests')">Requests</div>
                </div>
                
                <div class="search-box">
                    <input type="text" id="searchInput" placeholder="Search...">
                </div>
                
                <div class="content-area" id="contentArea">
                    <!-- Content will be loaded here -->
                </div>
            </div>
            
            <div class="chat-area">
                <div class="chat-header">
                    <div class="chat-avatar" id="chatAvatar" style="background: #4ECDC4;">C</div>
                    <div class="chat-info">
                        <div class="chat-name" id="chatName">Select a chat</div>
                        <div class="chat-status" id="chatStatus">Click on a conversation to start messaging</div>
                    </div>
                    <div class="chat-actions" id="chatActions" style="display: none;">
                        <button class="action-btn" onclick="startVoiceCall()" title="Voice call">📞</button>
                        <button class="action-btn" onclick="startVideoCall()" title="Video call">📹</button>
                    </div>
                </div>
                
                <div class="messages-container" id="messagesContainer">
                    <div style="text-align: center; color: #8696a0; padding: 40px;">
                        Select a conversation to start messaging
                    </div>
                </div>
                
                <div class="input-container" id="inputContainer" style="display: none;">
                    <div class="input-actions">
                        <button class="input-action" title="Emoji">😊</button>
                        <button class="input-action" title="Attach">📎</button>
                    </div>
                    <textarea class="message-input" id="messageInput" placeholder="Type a message..." rows="1"></textarea>
                    <button class="send-btn" onclick="sendMessage()" title="Send">➤</button>
                </div>
            </div>
        </div>

        <!-- Call Interface -->
        <div id="callInterface" class="call-interface">
            <div class="caller-info">
                <div class="caller-name" id="callerName">John Doe</div>
                <div class="call-status" id="callStatus">Calling...</div>
            </div>
            <div class="call-controls">
                <button class="call-btn accept-call" onclick="answerCall(true)">📞</button>
                <button class="call-btn decline-call" onclick="answerCall(false)">📞</button>
                <button class="call-btn end-call" onclick="endCall()" style="display: none;">📞</button>
            </div>
        </div>

        <button class="add-friend-btn" onclick="showAddFriend()" title="Add Friend">+</button>

        <script>
            let currentUser = null;
            let socket = null;
            let currentConversation = null;
            let currentCall = null;
            let conversations = [];
            let friends = [];
            let friendRequests = [];

            // Initialize app
            function initApp() {
                const savedUser = localStorage.getItem('whatsappUser');
                if (savedUser) {
                    currentUser = JSON.parse(savedUser);
                    showApp();
                    connectSocket();
                    loadData();
                }
            }

            function login() {
                const username = document.getElementById('usernameInput').value.trim();
                if (!username) {
                    alert('Please enter your name');
                    return;
                }

                fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: username})
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        currentUser = data.user;
                        localStorage.setItem('whatsappUser', JSON.stringify(data.user));
                        showApp();
                        connectSocket();
                        loadData();
                    } else {
                        alert('Error: ' + data.error);
                    }
                });
            }

            function showApp() {
                document.getElementById('loginScreen').style.display = 'none';
                document.getElementById('appContainer').style.display = 'flex';
                
                document.getElementById('userName').textContent = currentUser.display_name;
                document.getElementById('userAvatar').textContent = currentUser.display_name.charAt(0).toUpperCase();
                document.getElementById('userAvatar').style.background = currentUser.avatar_color;
                document.getElementById('userCode').textContent = 'CODE: ' + currentUser.user_code;
                document.getElementById('userStatus').textContent = 'Online';

                loadConversations();
            }

            function connectSocket() {
                socket = io({query: {user_id: currentUser.id}});
                
                socket.on('connect', () => {
                    console.log('Connected to server');
                    updateOnlineStatus(true);
                });

                socket.on('new_message', handleNewMessage);
                socket.on('friend_request', handleFriendRequest);
                socket.on('friend_request_accepted', handleFriendRequestAccepted);
                socket.on('incoming_call', handleIncomingCall);
                socket.on('call_accepted', handleCallAccepted);
                socket.on('call_ended', handleCallEnded);
            }

            function loadData() {
                loadConversations();
                loadFriends();
                loadFriendRequests();
            }

            function loadConversations() {
                fetch('/api/conversations?user_id=' + currentUser.id)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        conversations = data.conversations;
                        renderConversations();
                    }
                });
            }

            function loadFriends() {
                fetch('/api/friends?user_id=' + currentUser.id)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        friends = data.friends;
                    }
                });
            }

            function loadFriendRequests() {
                fetch('/api/friend_requests?user_id=' + currentUser.id)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        friendRequests = data.requests;
                    }
                });
            }

            function renderConversations() {
                const container = document.getElementById('contentArea');
                container.innerHTML = conversations.map(conv => `
                    <div class="conversation-item" onclick="selectConversation('${conv.id}')">
                        <div class="item-avatar" style="background: ${conv.avatar_color || '#4ECDC4'};">${conv.name.charAt(0).toUpperCase()}</div>
                        <div class="item-info">
                            <div class="item-name">${conv.name}</div>
                            <div class="item-preview">${conv.last_message || 'No messages yet'}</div>
                        </div>
                    </div>
                `).join('');
            }

            function renderFriends() {
                const container = document.getElementById('contentArea');
                container.innerHTML = friends.map(friend => `
                    <div class="friend-item" onclick="startChatWithFriend('${friend.id}')">
                        <div class="item-avatar" style="background: ${friend.avatar_color || '#45B7D1'};">${friend.display_name.charAt(0).toUpperCase()}</div>
                        <div class="item-info">
                            <div class="item-name">${friend.display_name}</div>
                            <div class="item-status">${friend.online ? 'Online' : 'Offline'}</div>
                            <div class="item-preview">Code: ${friend.user_code}</div>
                        </div>
                    </div>
                `).join('');
            }

            function renderFriendRequests() {
                const container = document.getElementById('contentArea');
                if (friendRequests.length === 0) {
                    container.innerHTML = '<div style="text-align: center; color: #8696a0; padding: 40px;">No pending friend requests</div>';
                    return;
                }

                container.innerHTML = friendRequests.map(req => `
                    <div class="friend-request-item">
                        <div class="item-avatar" style="background: ${req.from_avatar_color || '#FF6B6B'};">${req.from_display_name.charAt(0).toUpperCase()}</div>
                        <div class="item-info">
                            <div class="item-name">${req.from_display_name}</div>
                            <div class="item-preview">Wants to be your friend</div>
                        </div>
                        <div class="request-actions">
                            <button class="accept-btn" onclick="respondToRequest('${req.id}', true)">Accept</button>
                            <button class="decline-btn" onclick="respondToRequest('${req.id}', false)">Decline</button>
                        </div>
                    </div>
                `).join('');
            }

            function switchTab(tabName) {
                document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
                event.target.classList.add('active');

                if (tabName === 'chats') {
                    renderConversations();
                } else if (tabName === 'friends') {
                    renderFriends();
                } else if (tabName === 'requests') {
                    renderFriendRequests();
                }
            }

            function selectConversation(conversationId) {
                currentConversation = conversations.find(c => c.id === conversationId);
                if (!currentConversation) return;

                document.getElementById('chatName').textContent = currentConversation.name;
                document.getElementById('chatAvatar').textContent = currentConversation.name.charAt(0).toUpperCase();
                document.getElementById('chatAvatar').style.background = currentConversation.avatar_color || '#4ECDC4';
                document.getElementById('chatStatus').textContent = 'Online';
                document.getElementById('chatActions').style.display = 'flex';
                document.getElementById('inputContainer').style.display = 'flex';

                loadMessages(conversationId);
            }

            function loadMessages(conversationId) {
                fetch('/api/messages/' + conversationId)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        renderMessages(data.messages);
                    }
                });
            }

            function renderMessages(messages) {
                const container = document.getElementById('messagesContainer');
                container.innerHTML = messages.map(msg => `
                    <div class="message ${msg.user_id === currentUser.id ? 'sent' : 'received'}">
                        <div class="message-content">${msg.content}</div>
                        <div class="message-time">${formatTime(msg.timestamp)}</div>
                    </div>
                `).join('');
                
                container.scrollTop = container.scrollHeight;
            }

            function sendMessage() {
                const input = document.getElementById('messageInput');
                const content = input.value.trim();
                
                if (!content || !currentConversation) return;

                const messageData = {
                    id: 'msg_' + Date.now(),
                    conversation_id: currentConversation.id,
                    user_id: currentUser.id,
                    content: content,
                    timestamp: new Date().toISOString()
                };

                // Add to UI immediately
                addMessageToUI(messageData, true);
                input.value = '';

                // Send to server
                fetch('/api/send_message', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(messageData)
                });

                if (socket) {
                    socket.emit('send_message', messageData);
                }
            }

            function addMessageToUI(messageData, isSent) {
                const container = document.getElementById('messagesContainer');
                const placeholder = container.querySelector('div[style]');
                if (placeholder) placeholder.remove();

                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${isSent ? 'sent' : 'received'}`;
                messageDiv.innerHTML = `
                    <div class="message-content">${messageData.content}</div>
                    <div class="message-time">${formatTime(messageData.timestamp)}</div>
                `;
                
                container.appendChild(messageDiv);
                container.scrollTop = container.scrollHeight;
            }

            function handleNewMessage(data) {
                if (currentConversation && data.conversation_id === currentConversation.id) {
                    addMessageToUI(data.message, false);
                }
            }

            function showAddFriend() {
                const userCode = prompt('Enter friend\'s code:');
                if (userCode) {
                    fetch('/api/send_friend_request', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            from_user_id: currentUser.id,
                            to_user_code: userCode
                        })
                    })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            alert('Friend request sent!');
                            loadFriendRequests();
                        } else {
                            alert('Error: ' + data.error);
                        }
                    });
                }
            }

            function respondToRequest(requestId, accept) {
                fetch('/api/respond_friend_request', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        request_id: requestId,
                        accept: accept
                    })
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        loadFriendRequests();
                        loadFriends();
                        if (accept) {
                            alert('Friend added successfully!');
                        }
                    }
                });
            }

            function handleFriendRequest(data) {
                loadFriendRequests();
                alert(`New friend request from ${data.from_user.display_name}`);
            }

            function handleFriendRequestAccepted(data) {
                loadFriends();
                alert(`${data.friend.display_name} accepted your friend request!`);
            }

            function startChatWithFriend(friendId) {
                fetch('/api/create_conversation', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        user_id: currentUser.id,
                        friend_id: friendId
                    })
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        loadConversations();
                        // Switch to chats tab and select the conversation
                        document.querySelectorAll('.tab')[0].click();
                        // You might want to automatically select the new conversation here
                    }
                });
            }

            function startVoiceCall() {
                if (!currentConversation) return;
                
                fetch('/api/start_call', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        from_user_id: currentUser.id,
                        conversation_id: currentConversation.id,
                        call_type: 'voice'
                    })
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        currentCall = data.call;
                        showCallInterface('outgoing');
                    }
                });
            }

            function startVideoCall() {
                if (!currentConversation) return;
                
                fetch('/api/start_call', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        from_user_id: currentUser.id,
                        conversation_id: currentConversation.id,
                        call_type: 'video'
                    })
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        currentCall = data.call;
                        showCallInterface('outgoing');
                    }
                });
            }

            function handleIncomingCall(data) {
                currentCall = data.call;
                document.getElementById('callerName').textContent = data.caller.display_name;
                document.getElementById('callStatus').textContent = `Incoming ${data.call.call_type} call`;
                showCallInterface('incoming');
            }

            function showCallInterface(type) {
                const callInterface = document.getElementById('callInterface');
                const acceptBtn = callInterface.querySelector('.accept-call');
                const declineBtn = callInterface.querySelector('.decline-call');
                const endBtn = callInterface.querySelector('.end-call');
                
                if (type === 'incoming') {
                    acceptBtn.style.display = 'flex';
                    declineBtn.style.display = 'flex';
                    endBtn.style.display = 'none';
                    document.getElementById('callStatus').textContent = 'Incoming call';
                } else {
                    acceptBtn.style.display = 'none';
                    declineBtn.style.display = 'none';
                    endBtn.style.display = 'flex';
                    document.getElementById('callStatus').textContent = 'Calling...';
                }
                
                callInterface.style.display = 'flex';
            }

            function answerCall(accept) {
                if (!currentCall) return;
                
                fetch('/api/answer_call', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        call_id: currentCall.id,
                        accept: accept
                    })
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        if (accept) {
                            document.getElementById('callStatus').textContent = 'Call connected';
                            document.querySelector('.accept-call').style.display = 'none';
                            document.querySelector('.decline-call').style.display = 'none';
                            document.querySelector('.end-call').style.display = 'flex';
                        } else {
                            hideCallInterface();
                        }
                    }
                });
            }

            function endCall() {
                if (!currentCall) return;
                
                fetch('/api/end_call', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        call_id: currentCall.id
                    })
                })
                .then(r => r.json())
                .then(data => {
                    hideCallInterface();
                });
            }

            function handleCallAccepted(data) {
                document.getElementById('callStatus').textContent = 'Call connected';
                document.querySelector('.accept-call').style.display = 'none';
                document.querySelector('.decline-call').style.display = 'none';
                document.querySelector('.end-call').style.display = 'flex';
            }

            function handleCallEnded(data) {
                hideCallInterface();
                alert('Call ended');
            }

            function hideCallInterface() {
                document.getElementById('callInterface').style.display = 'none';
                currentCall = null;
            }

            function formatTime(timestamp) {
                const date = new Date(timestamp);
                return date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            }

            function updateOnlineStatus(online) {
                if (socket) {
                    socket.emit('user_status', {online: online});
                }
            }

            // Auto-resize textarea and enter to send
            document.addEventListener('DOMContentLoaded', function() {
                const textarea = document.getElementById('messageInput');
                textarea.addEventListener('input', function() {
                    this.style.height = 'auto';
                    this.style.height = (this.scrollHeight) + 'px';
                });

                textarea.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        sendMessage();
                    }
                });

                initApp();
            });
        </script>
    </body>
    </html>
    '''

# API Routes
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username', '').strip()
    
    if not username:
        return jsonify({'success': False, 'error': 'Username is required'})
    
    db = get_db()
    
    # Check if user exists
    user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    
    if not user:
        # Create new user
        user_id = str(uuid.uuid4())
        user_code = generate_user_code()
        avatar_color = get_avatar_color(user_id)
        
        db.execute('INSERT INTO users (id, username, display_name, user_code, online, last_seen, avatar_color, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                   (user_id, username, username, user_code, 1, datetime.now().isoformat(), avatar_color, datetime.now().isoformat()))
        db.commit()
        user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    else:
        # Update online status
        db.execute('UPDATE users SET online = 1, last_seen = ? WHERE id = ?
                           db.execute('UPDATE users SET online = 1, last_seen = ? WHERE id = ?', 
                   (datetime.now().isoformat(), user['id']))
        db.commit()
        user = db.execute('SELECT * FROM users WHERE id = ?', (user['id'],)).fetchone()
    
    user_dict = dict(user)
    db.close()
    return jsonify({'success': True, 'user': user_dict})

@app.route('/api/conversations')
def api_conversations():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'})
    
    db = get_db()
    
    # Get user's conversations
    conversations = db.execute('''
        SELECT c.*, 
               (SELECT content FROM messages WHERE conversation_id = c.id ORDER BY timestamp DESC LIMIT 1) as last_message
        FROM conversations c
        JOIN conversation_participants cp ON c.id = cp.conversation_id
        WHERE cp.user_id = ?
        ORDER BY (SELECT timestamp FROM messages WHERE conversation_id = c.id ORDER BY timestamp DESC LIMIT 1) DESC
    ''', (user_id,)).fetchall()
    
    result = []
    for conv in conversations:
        conv_dict = dict(conv)
        # Get conversation participants for individual chats
        if not conv_dict['is_group']:
            participants = db.execute('''
                SELECT u.display_name, u.avatar_color 
                FROM conversation_participants cp
                JOIN users u ON cp.user_id = u.id
                WHERE cp.conversation_id = ? AND cp.user_id != ?
            ''', (conv_dict['id'], user_id)).fetchone()
            if participants:
                conv_dict['name'] = participants['display_name']
                conv_dict['avatar_color'] = participants['avatar_color']
        result.append(conv_dict)
    
    db.close()
    return jsonify({'success': True, 'conversations': result})

@app.route('/api/messages/<conversation_id>')
def api_messages(conversation_id):
    db = get_db()
    messages = db.execute('''
        SELECT m.*, u.display_name 
        FROM messages m 
        JOIN users u ON m.user_id = u.id 
        WHERE m.conversation_id = ? 
        ORDER BY m.timestamp
    ''', (conversation_id,)).fetchall()
    
    result = [dict(msg) for msg in messages]
    db.close()
    return jsonify({'success': True, 'messages': result})

@app.route('/api/send_message', methods=['POST'])
def api_send_message():
    data = request.get_json()
    
    db = get_db()
    db.execute('INSERT INTO messages (id, conversation_id, user_id, content, timestamp) VALUES (?, ?, ?, ?, ?)',
               (data['id'], data['conversation_id'], data['user_id'], data['content'], data['timestamp']))
    db.commit()
    
    # Get conversation participants
    participants = db.execute('SELECT user_id FROM conversation_participants WHERE conversation_id = ?', 
                             (data['conversation_id'],)).fetchall()
    
    # Broadcast to participants
    for participant in participants:
        if participant['user_id'] != data['user_id']:  # Don't send to sender
            socketio.emit('new_message', {
                'conversation_id': data['conversation_id'],
                'message': data
            }, room=participant['user_id'])
    
    db.close()
    return jsonify({'success': True})

@app.route('/api/friends')
def api_friends():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'})
    
    db = get_db()
    friends = db.execute('''
        SELECT u.id, u.username, u.display_name, u.user_code, u.online, u.avatar_color
        FROM friends f
        JOIN users u ON f.friend_id = u.id
        WHERE f.user_id = ?
    ''', (user_id,)).fetchall()
    
    result = [dict(friend) for friend in friends]
    db.close()
    return jsonify({'success': True, 'friends': result})

@app.route('/api/friend_requests')
def api_friend_requests():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'})
    
    db = get_db()
    requests = db.execute('''
        SELECT fr.*, u.display_name as from_display_name, u.avatar_color as from_avatar_color
        FROM friend_requests fr
        JOIN users u ON fr.from_user_id = u.id
        WHERE fr.to_user_id = ? AND fr.status = 'pending'
    ''', (user_id,)).fetchall()
    
    result = [dict(req) for req in requests]
    db.close()
    return jsonify({'success': True, 'requests': result})

@app.route('/api/send_friend_request', methods=['POST'])
def api_send_friend_request():
    data = request.get_json()
    from_user_id = data.get('from_user_id')
    to_user_code = data.get('to_user_code')
    
    if not from_user_id or not to_user_code:
        return jsonify({'success': False, 'error': 'Missing data'})
    
    db = get_db()
    
    # Find target user by code
    to_user = db.execute('SELECT * FROM users WHERE user_code = ?', (to_user_code,)).fetchone()
    if not to_user:
        return jsonify({'success': False, 'error': 'User not found'})
    
    if from_user_id == to_user['id']:
        return jsonify({'success': False, 'error': 'Cannot add yourself'})
    
    # Check if already friends
    existing_friend = db.execute('SELECT * FROM friends WHERE user_id = ? AND friend_id = ?', 
                                (from_user_id, to_user['id'])).fetchone()
    if existing_friend:
        return jsonify({'success': False, 'error': 'Already friends'})
    
    # Check if request already exists
    existing_request = db.execute('SELECT * FROM friend_requests WHERE from_user_id = ? AND to_user_id = ? AND status = "pending"',
                                 (from_user_id, to_user['id'])).fetchone()
    if existing_request:
        return jsonify({'success': False, 'error': 'Friend request already sent'})
    
    # Create friend request
    request_id = str(uuid.uuid4())
    db.execute('INSERT INTO friend_requests (id, from_user_id, to_user_id, status, created_at) VALUES (?, ?, ?, "pending", ?)',
               (request_id, from_user_id, to_user['id'], datetime.now().isoformat()))
    db.commit()
    
    # Notify target user
    from_user = db.execute('SELECT * FROM users WHERE id = ?', (from_user_id,)).fetchone()
    socketio.emit('friend_request', {
        'request_id': request_id,
        'from_user': dict(from_user)
    }, room=to_user['id'])
    
    db.close()
    return jsonify({'success': True, 'message': 'Friend request sent'})

@app.route('/api/respond_friend_request', methods=['POST'])
def api_respond_friend_request():
    data = request.get_json()
    request_id = data.get('request_id')
    accept = data.get('accept', False)
    
    db = get_db()
    
    # Get request details
    request_data = db.execute('SELECT * FROM friend_requests WHERE id = ?', (request_id,)).fetchone()
    if not request_data:
        return jsonify({'success': False, 'error': 'Request not found'})
    
    if accept:
        # Add to friends table both ways
        db.execute('INSERT OR IGNORE INTO friends (user_id, friend_id, created_at) VALUES (?, ?, ?)',
                  (request_data['from_user_id'], request_data['to_user_id'], datetime.now().isoformat()))
        db.execute('INSERT OR IGNORE INTO friends (user_id, friend_id, created_at) VALUES (?, ?, ?)',
                  (request_data['to_user_id'], request_data['from_user_id'], datetime.now().isoformat()))
        
        # Notify the requester
        new_friend = db.execute('SELECT * FROM users WHERE id = ?', (request_data['to_user_id'],)).fetchone()
        socketio.emit('friend_request_accepted', {
            'friend': dict(new_friend)
        }, room=request_data['from_user_id'])
    
    # Update request status
    db.execute('UPDATE friend_requests SET status = ? WHERE id = ?', 
               ('accepted' if accept else 'declined', request_id))
    db.commit()
    db.close()
    
    return jsonify({'success': True, 'message': 'Friend request ' + ('accepted' if accept else 'declined')})

@app.route('/api/create_conversation', methods=['POST'])
def api_create_conversation():
    data = request.get_json()
    user_id = data.get('user_id')
    friend_id = data.get('friend_id')
    
    if not user_id or not friend_id:
        return jsonify({'success': False, 'error': 'Missing data'})
    
    db = get_db()
    
    # Check if conversation already exists
    existing_conv = db.execute('''
        SELECT c.id FROM conversations c
        JOIN conversation_participants cp1 ON c.id = cp1.conversation_id
        JOIN conversation_participants cp2 ON c.id = cp2.conversation_id
        WHERE cp1.user_id = ? AND cp2.user_id = ? AND c.is_group = 0
    ''', (user_id, friend_id)).fetchone()
    
    if existing_conv:
        db.close()
        return jsonify({'success': True, 'conversation_id': existing_conv['id']})
    
    # Create new conversation
    conv_id = str(uuid.uuid4())
    friend_user = db.execute('SELECT display_name FROM users WHERE id = ?', (friend_id,)).fetchone()
    conv_name = f"Chat with {friend_user['display_name']}"
    
    db.execute('INSERT INTO conversations (id, name, is_group, created_by, created_at) VALUES (?, ?, ?, ?, ?)',
               (conv_id, conv_name, 0, user_id, datetime.now().isoformat()))
    
    # Add participants
    db.execute('INSERT INTO conversation_participants (conversation_id, user_id) VALUES (?, ?)', (conv_id, user_id))
    db.execute('INSERT INTO conversation_participants (conversation_id, user_id) VALUES (?, ?)', (conv_id, friend_id))
    
    db.commit()
    db.close()
    
    return jsonify({'success': True, 'conversation_id': conv_id})

@app.route('/api/start_call', methods=['POST'])
def api_start_call():
    data = request.get_json()
    from_user_id = data.get('from_user_id')
    conversation_id = data.get('conversation_id')
    call_type = data.get('call_type', 'voice')
    
    db = get_db()
    
    # Get conversation participants
    participants = db.execute('SELECT user_id FROM conversation_participants WHERE conversation_id = ? AND user_id != ?',
                             (conversation_id, from_user_id)).fetchall()
    
    if not participants:
        return jsonify({'success': False, 'error': 'No participants found'})
    
    # Create call record
    call_id = str(uuid.uuid4())
    db.execute('INSERT INTO active_calls (id, from_user_id, to_user_id, conversation_id, call_type, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
               (call_id, from_user_id, participants[0]['user_id'], conversation_id, call_type, 'ringing', datetime.now().isoformat()))
    db.commit()
    
    # Get caller info
    caller = db.execute('SELECT * FROM users WHERE id = ?', (from_user_id,)).fetchone()
    
    # Notify recipient
    socketio.emit('incoming_call', {
        'call': {
            'id': call_id,
            'type': call_type,
            'conversation_id': conversation_id
        },
        'caller': dict(caller)
    }, room=participants[0]['user_id'])
    
    db.close()
    return jsonify({'success': True, 'call': {'id': call_id, 'type': call_type}})

@app.route('/api/answer_call', methods=['POST'])
def api_answer_call():
    data = request.get_json()
    call_id = data.get('call_id')
    accept = data.get('accept', False)
    
    db = get_db()
    
    call = db.execute('SELECT * FROM active_calls WHERE id = ?', (call_id,)).fetchone()
    if not call:
        return jsonify({'success': False, 'error': 'Call not found'})
    
    if accept:
        db.execute('UPDATE active_calls SET status = ? WHERE id = ?', ('active', call_id))
        # Notify caller
        socketio.emit('call_accepted', {
            'call_id': call_id
        }, room=call['from_user_id'])
    else:
        db.execute('UPDATE active_calls SET status = ? WHERE id = ?', ('declined', call_id))
        # Notify caller
        socketio.emit('call_ended', {
            'call_id': call_id
        }, room=call['from_user_id'])
    
    db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/api/end_call', methods=['POST'])
def api_end_call():
    data = request.get_json()
    call_id = data.get('call_id')
    
    db = get_db()
    
    call = db.execute('SELECT * FROM active_calls WHERE id = ?', (call_id,)).fetchone()
    if call:
        # Notify other participant
        other_user = call['to_user_id']
        socketio.emit('call_ended', {
            'call_id': call_id
        }, room=other_user)
        
        db.execute('DELETE FROM active_calls WHERE id = ?', (call_id,))
        db.commit()
    
    db.close()
    return jsonify({'success': True})

# WebSocket events
@socketio.on('connect')
def handle_connect():
    user_id = request.args.get('user_id')
    if user_id:
        join_room(user_id)
        db = get_db()
        db.execute('UPDATE users SET online = 1 WHERE id = ?', (user_id,))
        db.commit()
        db.close()
        print(f"User {user_id} connected")

@socketio.on('disconnect')
def handle_disconnect():
    user_id = request.args.get('user_id')
    if user_id:
        db = get_db()
        db.execute('UPDATE users SET online = 0 WHERE id = ?', (user_id,))
        db.commit()
        db.close()
        print(f"User {user_id} disconnected")

@socketio.on('send_message')
def handle_send_message(data):
    # Broadcast to conversation participants (already handled in API)
    pass

@socketio.on('user_status')
def handle_user_status(data):
    # Update user status
    user_id = request.args.get('user_id')
    if user_id:
        db = get_db()
        db.execute('UPDATE users SET online = ? WHERE id = ?', (data['online'], user_id))
        db.commit()
        db.close()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
