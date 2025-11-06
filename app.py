# Trigger deployment
from flask import Flask, render_template_string, request, jsonify, session, send_file
import uuid
from datetime import datetime, timedelta
import threading
import time
import json
import os
import logging
from flask_socketio import SocketIO, emit
import sqlite3
import base64

# Configuration
SECRET_KEY = os.environ.get('SECRET_KEY', 'nos-mobile-secure-2024')
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
PORT = int(os.environ.get('PORT', 5000))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('NOS-Mobile')

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# Mobile-optimized Socket.IO
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25,
    logger=DEBUG,
    engineio_logger=DEBUG
)

# Create upload directory
os.makedirs('uploads', exist_ok=True)

# Database setup
class NOSDatabase:
    def __init__(self):
        self.db_path = 'nos_mobile.db'
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE,
                phone TEXT,
                avatar TEXT,
                status TEXT DEFAULT 'Available',
                online BOOLEAN DEFAULT FALSE,
                last_seen DATETIME,
                created_at DATETIME
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                room_id TEXT,
                user_id TEXT,
                username TEXT,
                message_type TEXT,
                content TEXT,
                file_path TEXT,
                duration INTEGER,
                timestamp DATETIME,
                status TEXT DEFAULT 'sent'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id TEXT PRIMARY KEY,
                name TEXT,
                created_by TEXT,
                created_at DATETIME
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_members (
                group_id TEXT,
                user_id TEXT,
                role TEXT DEFAULT 'member',
                joined_at DATETIME,
                PRIMARY KEY (group_id, user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def execute_query(self, query, params=()):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        result = cursor.fetchall()
        conn.close()
        return result

db = NOSDatabase()

# In-memory storage for real-time features
active_users = {}
active_calls = {}
user_sockets = {}

# WebRTC configuration for mobile
def get_webrtc_config():
    return {
        'iceServers': [
            {'urls': 'stun:stun.l.google.com:19302'},
            {'urls': 'stun:stun1.l.google.com:19302'},
            {'urls': 'stun:stun2.l.google.com:19302'},
            {'urls': 'stun:stun3.l.google.com:19302'},
            {
                'urls': 'turn:numb.viagenie.ca',
                'username': 'free',
                'credential': 'free'
            }
        ]
    }

@app.route('/')
def mobile_interface():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>NOS - Mobile Messenger</title>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="theme-color" content="#128C7E">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        /* Mobile-First CSS */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #128C7E;
            height: 100vh;
            overflow: hidden;
        }

        .mobile-container {
            width: 100%;
            height: 100vh;
            background: white;
            display: flex;
            flex-direction: column;
        }

        /* Header */
        .header {
            background: #075E54;
            color: white;
            padding: 15px;
            height: 60px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .header-title {
            font-size: 18px;
            font-weight: 600;
        }

        /* Tabs */
        .tabs {
            display: flex;
            background: #128C7E;
            overflow-x: auto;
            height: 50px;
        }

        .tab {
            padding: 15px 20px;
            color: white;
            white-space: nowrap;
            border-bottom: 3px solid transparent;
            font-size: 14px;
            min-width: 80px;
            text-align: center;
        }

        .tab.active {
            border-bottom-color: white;
            background: rgba(255,255,255,0.1);
        }

        /* Content */
        .content {
            flex: 1;
            display: flex;
            height: calc(100vh - 110px);
        }

        .sidebar {
            width: 100%;
            background: white;
            overflow-y: auto;
        }

        /* Chat List */
        .chat-list {
            overflow-y: auto;
        }

        .chat-item {
            padding: 15px;
            border-bottom: 1px solid #f0f0f0;
            display: flex;
            align-items: center;
            gap: 12px;
            cursor: pointer;
        }

        .chat-avatar {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: #25D366;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            font-size: 18px;
        }

        .online-dot {
            width: 12px;
            height: 12px;
            background: #25D366;
            border: 2px solid white;
            border-radius: 50%;
            margin-left: -15px;
            margin-top: 35px;
        }

        .chat-info {
            flex: 1;
        }

        .chat-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 4px;
        }

        .chat-name {
            font-weight: 600;
            font-size: 16px;
        }

        .chat-time {
            font-size: 12px;
            color: #666;
        }

        .chat-preview {
            font-size: 14px;
            color: #666;
        }

        /* Messages */
        .messages-area {
            flex: 1;
            padding: 10px;
            overflow-y: auto;
            background: #E5DDD5;
            display: flex;
            flex-direction: column;
        }

        .message {
            max-width: 85%;
            margin-bottom: 8px;
            padding: 12px 16px;
            border-radius: 18px;
            position: relative;
        }

        .message.sent {
            background: #DCF8C6;
            align-self: flex-end;
        }

        .message.received {
            background: white;
            align-self: flex-start;
        }

        .message-content {
            font-size: 15px;
            line-height: 1.4;
        }

        .message-time {
            font-size: 11px;
            color: #667781;
            text-align: right;
            margin-top: 4px;
        }

        /* Input Area */
        .input-area {
            padding: 10px 15px;
            background: white;
            border-top: 1px solid #e0e0e0;
            display: flex;
            align-items: flex-end;
            gap: 8px;
        }

        .input-actions {
            display: flex;
            gap: 5px;
        }

        .input-btn {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: none;
            background: #f0f0f0;
            color: #555;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
        }

        .message-input {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid #e0e0e0;
            border-radius: 25px;
            font-size: 16px;
            resize: none;
            max-height: 120px;
        }

        .send-btn {
            width: 44px;
            height: 44px;
            background: #128C7E;
            color: white;
            border: none;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
        }

        /* Voice Recorder */
        .voice-recorder {
            position: fixed;
            bottom: 80px;
            left: 20px;
            right: 20px;
            background: #075E54;
            color: white;
            padding: 20px;
            border-radius: 25px;
            text-align: center;
            display: none;
        }

        /* Call Interface */
        .call-interface {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: #1a1a1a;
            z-index: 1000;
            display: none;
        }

        /* Login Screen */
        .login-screen {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100vh;
            padding: 30px;
            background: linear-gradient(135deg, #128C7E 0%, #075E54 100%);
            color: white;
        }
    </style>
</head>
<body>
    <!-- Login Screen -->
    <div id="loginScreen" class="login-screen">
        <div style="text-align: center; margin-bottom: 40px;">
            <div style="font-size: 48px; margin-bottom: 15px;">💬</div>
            <h1 style="font-size: 32px; margin-bottom: 10px;">NOS</h1>
            <p style="font-size: 16px; opacity: 0.9;">Mobile Messenger with Calls</p>
        </div>
        
        <div style="width: 100%; max-width: 320px;">
            <input type="text" id="usernameInput" placeholder="Your name" style="width: 100%; padding: 16px; border: none; border-radius: 25px; margin-bottom: 15px; font-size: 16px; background: rgba(255,255,255,0.9);">
            <button onclick="registerUser()" style="width: 100%; padding: 16px; background: #25D366; color: white; border: none; border-radius: 25px; font-size: 16px; font-weight: 600;">Start Messaging</button>
        </div>
        
        <div style="margin-top: 40px; text-align: center;">
            <div style="font-size: 14px; opacity: 0.8; line-height: 1.5;">
                ✅ Voice & Video Calls<br>
                ✅ Voice Messages<br>
                ✅ Group Chats<br>
                ✅ Mobile Optimized
            </div>
        </div>
    </div>

    <!-- Main App -->
    <div id="appContainer" class="mobile-container" style="display: none;">
        <!-- Header -->
        <div class="header">
            <div class="header-title" id="headerTitle">Chats</div>
            <div style="display: flex; gap: 10px;">
                <button style="background: none; border: none; color: white; font-size: 18px;" onclick="searchChats()">🔍</button>
                <button style="background: none; border: none; color: white; font-size: 18px;" onclick="showSettings()">⚙️</button>
            </div>
        </div>

        <!-- Tabs -->
        <div class="tabs">
            <div class="tab active" onclick="switchTab('chats')">Chats</div>
            <div class="tab" onclick="switchTab('calls')">Calls</div>
            <div class="tab" onclick="switchTab('status')">Status</div>
            <div class="tab" onclick="switchTab('settings')">Settings</div>
        </div>

        <!-- Content -->
        <div class="content">
            <!-- Sidebar -->
            <div class="sidebar">
                <div class="chat-list" id="chatList">
                    <!-- Chats will be loaded here -->
                </div>
            </div>

            <!-- Main Chat Area -->
            <div class="main-content" id="mainChat" style="display: none; flex: 1; flex-direction: column;">
                <!-- Chat Header -->
                <div class="header">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <button style="background: none; border: none; color: white; font-size: 20px;" onclick="backToChats()">←</button>
                        <div>
                            <div class="header-title" id="chatWithName">Loading...</div>
                            <div style="font-size: 12px; opacity: 0.8;" id="chatStatus">...</div>
                        </div>
                    </div>
                    <div style="display: flex; gap: 10px;">
                        <button style="background: none; border: none; color: white; font-size: 18px;" onclick="startVoiceCall()">📞</button>
                        <button style="background: none; border: none; color: white; font-size: 18px;" onclick="startVideoCall()">📹</button>
                    </div>
                </div>

                <!-- Messages -->
                <div class="messages-area" id="messagesArea">
                    <div style="text-align: center; color: #666; padding: 40px;">
                        Select a conversation to start messaging
                    </div>
                </div>

                <!-- Input Area -->
                <div class="input-area" id="inputContainer" style="display: none;">
                    <div class="input-actions">
                        <button class="input-btn" onclick="toggleVoiceRecorder()">🎤</button>
                        <button class="input-btn" onclick="attachImage()">📷</button>
                        <button class="input-btn" onclick="attachFile()">📎</button>
                    </div>
                    <textarea class="message-input" id="messageInput" placeholder="Type a message..." rows="1"></textarea>
                    <button class="send-btn" onclick="sendMessage()" id="sendBtn">➤</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Voice Recorder -->
    <div id="voiceRecorder" class="voice-recorder">
        <div style="display: flex; align-items: center; justify-content: center; gap: 10px; margin-bottom: 10px;">
            <div style="width: 12px; height: 12px; background: #ff4444; border-radius: 50%; animation: pulse 1s infinite;"></div>
            <div style="font-size: 16px; font-weight: 600;" id="recordingTime">0:00</div>
        </div>
        <div style="font-size: 14px; opacity: 0.9;">Recording... Release to send</div>
    </div>

    <!-- Call Interface -->
    <div id="callInterface" class="call-interface">
        <video id="remoteVideo" style="width: 100%; height: 100%; object-fit: cover;" autoplay playsinline></video>
        <video id="localVideo" style="position: absolute; bottom: 100px; right: 20px; width: 120px; height: 160px; border-radius: 10px; border: 2px solid white;" autoplay playsinline muted></video>
        <div style="position: absolute; top: 60px; left: 0; right: 0; text-align: center; color: white; padding: 20px;">
            <div style="font-size: 24px; font-weight: 600;" id="callParticipant">Participant</div>
            <div style="font-size: 16px; opacity: 0.9;" id="callStatus">Connecting...</div>
        </div>
        <div style="position: absolute; bottom: 40px; left: 0; right: 0; display: flex; justify-content: center; gap: 25px; padding: 0 20px;">
            <button style="width: 60px; height: 60px; border-radius: 50%; border: none; background: rgba(255,255,255,0.2); color: white; font-size: 20px;" onclick="toggleMute()">🎤</button>
            <button style="width: 60px; height: 60px; border-radius: 50%; border: none; background: rgba(255,255,255,0.2); color: white; font-size: 20px;" onclick="toggleVideo()">📹</button>
            <button style="width: 60px; height: 60px; border-radius: 50%; border: none; background: #ff4444; color: white; font-size: 20px;" onclick="endCall()">📞</button>
        </div>
    </div>

    <script>
        // Mobile NOS App JavaScript
        let currentUser = null;
        let socket = null;
        let currentChat = null;
        let peerConnection = null;
        let localStream = null;
        let currentCall = null;
        let isRecording = false;
        let recordingTime = 0;
        let recordingInterval = null;

        // Initialize app
        function initApp() {
            checkAutoLogin();
        }

        function checkAutoLogin() {
            const savedUser = localStorage.getItem('nosUser');
            if (savedUser) {
                currentUser = JSON.parse(savedUser);
                showAppInterface();
                connectWebSocket();
                loadChats();
            }
        }

        async function registerUser() {
            const username = document.getElementById('usernameInput').value.trim();
            if (!username) {
                alert('Please enter your name');
                return;
            }

            try {
                const response = await fetch('/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username})
                });

                const data = await response.json();
                
                if (data.success) {
                    currentUser = data.user;
                    localStorage.setItem('nosUser', JSON.stringify(data.user));
                    showAppInterface();
                    connectWebSocket();
                    loadChats();
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                alert('Network error. Please try again.');
            }
        }

        function showAppInterface() {
            document.getElementById('loginScreen').style.display = 'none';
            document.getElementById('appContainer').style.display = 'flex';
        }

        function connectWebSocket() {
            socket = io({
                query: { user_id: currentUser.id }
            });

            socket.on('connect', () => {
                console.log('Connected to NOS');
            });

            socket.on('new_message', handleNewMessage);
            socket.on('incoming_call', handleIncomingCall);
            socket.on('call_accepted', handleCallAccepted);
            socket.on('call_ended', handleCallEnded);
        }

        function loadChats() {
            // Sample chats for demo
            const chats = [
                {
                    id: 'general',
                    name: 'General Chat',
                    lastMessage: 'Welcome to NOS!',
                    time: new Date().toISOString(),
                    unread: 0,
                    avatar: 'GC',
                    online: true
                },
                {
                    id: 'support', 
                    name: 'NOS Support',
                    lastMessage: 'How can we help you?',
                    time: new Date().toISOString(),
                    unread: 3,
                    avatar: 'NS',
                    online: true
                }
            ];

            renderChatList(chats);
        }

        function renderChatList(chats) {
            const container = document.getElementById('chatList');
            container.innerHTML = chats.map(chat => `
                <div class="chat-item" onclick="selectChat('${chat.id}')">
                    <div style="position: relative;">
                        <div class="chat-avatar">${chat.avatar}</div>
                        ${chat.online ? '<div class="online-dot"></div>' : ''}
                    </div>
                    <div class="chat-info">
                        <div class="chat-header">
                            <div class="chat-name">${chat.name}</div>
                            <div class="chat-time">${formatTime(chat.time)}</div>
                        </div>
                        <div class="chat-preview">
                            ${chat.lastMessage}
                            ${chat.unread > 0 ? `<span style="background: #25D366; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px;">${chat.unread}</span>` : ''}
                        </div>
                    </div>
                </div>
            `).join('');
        }

        function selectChat(chatId) {
            currentChat = {
                id: chatId,
                name: chatId === 'general' ? 'General Chat' : 'NOS Support'
            };

            document.getElementById('sidebar').style.display = 'none';
            document.getElementById('mainChat').style.display = 'flex';
            document.getElementById('chatWithName').textContent = currentChat.name;
            document.getElementById('chatStatus').textContent = 'Online';
            document.getElementById('inputContainer').style.display = 'flex';

            loadMessages(chatId);
        }

        function backToChats() {
            document.getElementById('sidebar').style.display = 'block';
            document.getElementById('mainChat').style.display = 'none';
            document.getElementById('inputContainer').style.display = 'none';
            currentChat = null;
        }

        function loadMessages(chatId) {
            const messagesArea = document.getElementById('messagesArea');
            messagesArea.innerHTML = `
                <div class="message received">
                    <div class="message-content">
                        Welcome to ${currentChat.name}! Start chatting now.
                    </div>
                    <div class="message-time">${formatTime(new Date())}</div>
                </div>
                <div class="message sent">
                    <div class="message-content">
                        Hello! Testing NOS Mobile.
                    </div>
                    <div class="message-time">${formatTime(new Date())}</div>
                </div>
            `;
        }

        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();

            if (!message || !currentChat) return;

            // Add to UI immediately
            const messagesArea = document.getElementById('messagesArea');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message sent';
            messageDiv.innerHTML = `
                <div class="message-content">${message}</div>
                <div class="message-time">${formatTime(new Date())}</div>
            `;
            messagesArea.appendChild(messageDiv);

            // Clear input
            input.value = '';

            // Send via WebSocket
            if (socket) {
                socket.emit('send_message', {
                    chat_id: currentChat.id,
                    content: message,
                    timestamp: new Date().toISOString()
                });
            }

            // Scroll to bottom
            messagesArea.scrollTop = messagesArea.scrollHeight;
        }

        function handleNewMessage(data) {
            if (currentChat && data.chat_id === currentChat.id) {
                const messagesArea = document.getElementById('messagesArea');
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message received';
                messageDiv.innerHTML = `
                    <div class="message-content">${data.content}</div>
                    <div class="message-time">${formatTime(data.timestamp)}</div>
                `;
                messagesArea.appendChild(messageDiv);
                messagesArea.scrollTop = messagesArea.scrollHeight;
            }
        }

        // Voice Messages
        function toggleVoiceRecorder() {
            if (!isRecording) {
                startVoiceRecording();
            } else {
                stopVoiceRecording();
            }
        }

        function startVoiceRecording() {
            isRecording = true;
            recordingTime = 0;
            document.getElementById('voiceRecorder').style.display = 'block';
            
            recordingInterval = setInterval(() => {
                recordingTime++;
                const minutes = Math.floor(recordingTime / 60);
                const seconds = recordingTime % 60;
                document.getElementById('recordingTime').textContent = 
                    `${minutes}:${seconds.toString().padStart(2, '0')}`;
            }, 1000);

            // Start actual recording would go here
        }

        function stopVoiceRecording() {
            isRecording = false;
            clearInterval(recordingInterval);
            document.getElementById('voiceRecorder').style.display = 'none';
            
            if (recordingTime >= 1) {
                // Send voice message
                sendVoiceMessage();
            }
        }

        function sendVoiceMessage() {
            if (!currentChat) return;
            
            const messagesArea = document.getElementById('messagesArea');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message sent';
            messageDiv.innerHTML = `
                <div class="message-content">
                    <div style="display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: rgba(255,255,255,0.1); border-radius: 20px;">
                        <button style="width: 30px; height: 30px; border-radius: 50%; background: white; border: none; color: #075E54; display: flex; align-items: center; justify-content: center;">▶</button>
                        <div>${recordingTime}s</div>
                    </div>
                </div>
                <div class="message-time">${formatTime(new Date())}</div>
            `;
            messagesArea.appendChild(messageDiv);
            messagesArea.scrollTop = messagesArea.scrollHeight;
        }

        // Voice and Video Calls
        async function startVoiceCall() {
            if (!currentChat) return;
            await startCall('voice');
        }

        async function startVideoCall() {
            if (!currentChat) return;
            await startCall('video');
        }

        async function startCall(callType) {
            try {
                // Get user media
                localStream = await navigator.mediaDevices.getUserMedia({
                    audio: true,
                    video: callType === 'video'
                });

                // Show call interface
                document.getElementById('callInterface').style.display = 'flex';
                document.getElementById('localVideo').srcObject = localStream;
                document.getElementById('callParticipant').textContent = currentChat.name;
                document.getElementById('callStatus').textContent = 'Calling...';

                currentCall = {
                    chat: currentChat.id,
                    type: callType
                };

                // In real implementation, you would create WebRTC connection here
                
            } catch (error) {
                alert('Cannot access camera/microphone. Please check permissions.');
            }
        }

        function handleIncomingCall(data) {
            // Show incoming call interface
            alert(`Incoming ${data.call_type} call from ${data.caller_name}`);
        }

        function handleCallAccepted(data) {
            document.getElementById('callStatus').textContent = 'Connected';
        }

        function handleCallEnded() {
            endCall();
        }

        function endCall() {
            if (localStream) {
                localStream.getTracks().forEach(track => track.stop());
                localStream = null;
            }
            document.getElementById('callInterface').style.display = 'none';
            currentCall = null;
        }

        function toggleMute() {
            if (localStream) {
                const audioTrack = localStream.getAudioTracks()[0];
                audioTrack.enabled = !audioTrack.enabled;
            }
        }

        function toggleVideo() {
            if (localStream) {
                const videoTrack = localStream.getVideoTracks()[0];
                if (videoTrack) {
                    videoTrack.enabled = !videoTrack.enabled;
                }
            }
        }

        // Utility functions
        function formatTime(timestamp) {
            const date = new Date(timestamp);
            const now = new Date();
            const diff = now - date;

            if (diff < 60000) return 'Now';
            if (diff < 3600000) return Math.floor(diff / 60000) + 'm';
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }

        function switchTab(tabName) {
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('headerTitle').textContent = tabName.charAt(0).toUpperCase() + tabName.slice(1);
            
            if (tabName === 'chats') {
                loadChats();
            }
        }

        function searchChats() {
            alert('Search functionality coming soon!');
        }

        function showSettings() {
            alert('Settings coming soon!');
        }

        function attachImage() {
            alert('Image attachment coming soon!');
        }

        function attachFile() {
            alert('File attachment coming soon!');
        }

        // Initialize when page loads
        document.addEventListener('DOMContentLoaded', initApp);
    </script>
</body>
</html>
''')

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        
        if not username:
            return jsonify({'success': False, 'error': 'Username required'})
        
        user_id = str(uuid.uuid4())[:8]
        
        # Save to database
        db.execute_query('''
            INSERT INTO users (id, username, online, created_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, True, datetime.now()))
        
        session['user_id'] = user_id
        active_users[user_id] = {
            'id': user_id,
            'username': username,
            'online': True
        }
        
        return jsonify({
            'success': True,
            'user': {
                'id': user_id,
                'username': username,
                'online': True,
                'created_at': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# WebSocket events
@socketio.on('connect')
def handle_connect():
    user_id = request.args.get('user_id')
    if user_id:
        user_sockets[user_id] = request.sid
        if user_id in active_users:
            active_users[user_id]['online'] = True
        logger.info(f"User {user_id} connected")

@socketio.on('disconnect')
def handle_disconnect():
    user_id = None
    for uid, sid in user_sockets.items():
        if sid == request.sid:
            user_id = uid
            break
    
    if user_id and user_id in active_users:
        active_users[user_id]['online'] = False
        user_sockets.pop(user_id, None)

@socketio.on('send_message')
def handle_send_message(data):
    # Broadcast to all connected clients
    emit('new_message', {
        'chat_id': data['chat_id'],
        'content': data['content'],
        'timestamp': data.get('timestamp', datetime.now().isoformat())
    }, broadcast=True)

@socketio.on('call_offer')
def handle_call_offer(data):
    # Broadcast call offer
    emit('incoming_call', {
        'chat_id': data['chat_id'],
        'call_type': data['call_type'],
        'caller_name': active_users.get(data.get('caller_id'), {}).get('username', 'User')
    }, broadcast=True)

@socketio.on('call_answer')
def handle_call_answer(data):
    emit('call_accepted', {
        'chat_id': data['chat_id']
    }, broadcast=True)

@socketio.on('end_call')
def handle_end_call(data):
    emit('call_ended', {
        'chat_id': data['chat_id']
    }, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=PORT, debug=DEBUG)
