from flask import Flask, render_template_string, request, jsonify
import os
import uuid
from datetime import datetime

app = Flask(__name__)

# In-memory storage for demo
chats = {}
users = {}
messages = {}

@app.route('/')
def home():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NOS Messenger - Premium Communication</title>
    <style>
        :root {
            --primary: #0d47a1;
            --primary-dark: #08306b;
            --secondary: #1976d2;
            --accent: #1565c0;
            --background: #f8f9fa;
            --surface: #ffffff;
            --text-primary: #1a1a1a;
            --text-secondary: #666666;
            --border: #e0e0e0;
            --success: #2e7d32;
            --online: #4caf50;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Roboto', sans-serif;
        }

        body {
            background: var(--background);
            color: var(--text-primary);
            height: 100vh;
            overflow: hidden;
        }

        .app-container {
            display: flex;
            height: 100vh;
            max-width: 1400px;
            margin: 0 auto;
            background: var(--surface);
            box-shadow: 0 0 40px rgba(0,0,0,0.1);
        }

        /* Sidebar */
        .sidebar {
            width: 380px;
            background: var(--surface);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
        }

        .sidebar-header {
            padding: 20px;
            background: var(--primary);
            color: white;
        }

        .brand {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .brand h1 {
            font-size: 24px;
            font-weight: 600;
            letter-spacing: -0.5px;
        }

        .user-actions {
            display: flex;
            gap: 15px;
        }

        .icon-btn {
            background: none;
            border: none;
            color: white;
            font-size: 20px;
            cursor: pointer;
            padding: 5px;
            border-radius: 50%;
            transition: background 0.2s;
        }

        .icon-btn:hover {
            background: rgba(255,255,255,0.1);
        }

        .search-container {
            padding: 15px 20px;
            background: var(--surface);
            border-bottom: 1px solid var(--border);
        }

        .search-box {
            width: 100%;
            padding: 12px 20px;
            border: 1px solid var(--border);
            border-radius: 25px;
            background: var(--background);
            font-size: 14px;
            outline: none;
            transition: border 0.2s;
        }

        .search-box:focus {
            border-color: var(--secondary);
        }

        .chat-list {
            flex: 1;
            overflow-y: auto;
        }

        .chat-item {
            padding: 18px 20px;
            border-bottom: 1px solid var(--border);
            cursor: pointer;
            transition: background 0.2s;
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .chat-item:hover {
            background: var(--background);
        }

        .chat-item.active {
            background: #e3f2fd;
        }

        .avatar {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: var(--primary);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            font-size: 18px;
        }

        .chat-info {
            flex: 1;
        }

        .chat-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 5px;
        }

        .chat-name {
            font-weight: 600;
            font-size: 16px;
        }

        .chat-time {
            font-size: 12px;
            color: var(--text-secondary);
        }

        .chat-preview {
            font-size: 14px;
            color: var(--text-secondary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        /* Main Chat Area */
        .chat-area {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: var(--surface);
        }

        .chat-header-main {
            padding: 20px 30px;
            border-bottom: 1px solid var(--border);
            background: var(--surface);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .chat-user-info {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .user-status {
            display: flex;
            flex-direction: column;
        }

        .user-name {
            font-weight: 600;
            font-size: 18px;
        }

        .user-status-text {
            font-size: 13px;
            color: var(--text-secondary);
        }

        .status-online {
            color: var(--online);
        }

        .chat-actions {
            display: flex;
            gap: 20px;
        }

        .messages-container {
            flex: 1;
            padding: 30px;
            overflow-y: auto;
            background: var(--background);
        }

        .message {
            max-width: 70%;
            margin-bottom: 20px;
            padding: 15px 20px;
            border-radius: 18px;
            position: relative;
            line-height: 1.4;
            animation: fadeIn 0.3s ease-in;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message.sent {
            background: var(--primary);
            color: white;
            margin-left: auto;
            border-bottom-right-radius: 5px;
        }

        .message.received {
            background: var(--surface);
            color: var(--text-primary);
            border: 1px solid var(--border);
            border-bottom-left-radius: 5px;
        }

        .message-time {
            font-size: 11px;
            opacity: 0.8;
            margin-top: 5px;
            text-align: right;
        }

        .message-input-container {
            padding: 20px 30px;
            background: var(--surface);
            border-top: 1px solid var(--border);
        }

        .input-wrapper {
            display: flex;
            align-items: center;
            gap: 15px;
            background: var(--background);
            border: 1px solid var(--border);
            border-radius: 25px;
            padding: 5px 5px 5px 20px;
        }

        .message-input {
            flex: 1;
            border: none;
            background: none;
            outline: none;
            font-size: 15px;
            padding: 12px 0;
            resize: none;
            max-height: 120px;
        }

        .input-actions {
            display: flex;
            gap: 10px;
            align-items: center;
        }

        .attach-btn, .emoji-btn, .send-btn {
            background: none;
            border: none;
            font-size: 20px;
            cursor: pointer;
            padding: 8px;
            border-radius: 50%;
            transition: background 0.2s;
            color: var(--text-secondary);
        }

        .attach-btn:hover, .emoji-btn:hover {
            background: rgba(0,0,0,0.05);
        }

        .send-btn {
            background: var(--primary);
            color: white;
        }

        .send-btn:hover {
            background: var(--primary-dark);
        }

        /* Features Panel */
        .features-panel {
            width: 300px;
            background: var(--surface);
            border-left: 1px solid var(--border);
            padding: 30px 20px;
            overflow-y: auto;
        }

        .feature-section {
            margin-bottom: 30px;
        }

        .feature-section h3 {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 15px;
            color: var(--primary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .feature-item {
            padding: 12px 15px;
            background: var(--background);
            border-radius: 10px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: background 0.2s;
            border: 1px solid transparent;
        }

        .feature-item:hover {
            background: #e3f2fd;
            border-color: var(--secondary);
        }

        .feature-item.active {
            background: #e3f2fd;
            border-color: var(--secondary);
        }

        /* Welcome Screen */
        .welcome-screen {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: var(--background);
            text-align: center;
            padding: 40px;
        }

        .welcome-icon {
            font-size: 80px;
            margin-bottom: 30px;
            color: var(--primary);
        }

        .welcome-title {
            font-size: 32px;
            font-weight: 300;
            margin-bottom: 15px;
            color: var(--text-primary);
        }

        .welcome-subtitle {
            font-size: 16px;
            color: var(--text-secondary);
            margin-bottom: 40px;
            max-width: 500px;
            line-height: 1.6;
        }

        .feature-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            max-width: 600px;
            margin-top: 30px;
        }

        .feature-card {
            background: var(--surface);
            padding: 25px;
            border-radius: 12px;
            border: 1px solid var(--border);
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .feature-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }

        .feature-card h4 {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 10px;
            color: var(--text-primary);
        }

        .feature-card p {
            font-size: 14px;
            color: var(--text-secondary);
            line-height: 1.5;
        }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="brand">
                    <h1>NOS MESSENGER</h1>
                    <div class="user-actions">
                        <button class="icon-btn" title="Status">●</button>
                        <button class="icon-btn" title="New Chat">+</button>
                        <button class="icon-btn" title="Menu">⋮</button>
                    </div>
                </div>
            </div>

            <div class="search-container">
                <input type="text" class="search-box" placeholder="Search or start new chat">
            </div>

            <div class="chat-list">
                <div class="chat-item active">
                    <div class="avatar">JS</div>
                    <div class="chat-info">
                        <div class="chat-header">
                            <div class="chat-name">John Smith</div>
                            <div class="chat-time">12:45</div>
                        </div>
                        <div class="chat-preview">Meeting confirmed for tomorrow at 2 PM</div>
                    </div>
                </div>
                <div class="chat-item">
                    <div class="avatar">MJ</div>
                    <div class="chat-info">
                        <div class="chat-header">
                            <div class="chat-name">Maria Johnson</div>
                            <div class="chat-time">11:30</div>
                        </div>
                        <div class="chat-preview">Can you send the project files? 📁</div>
                    </div>
                </div>
                <div class="chat-item">
                    <div class="avatar">DT</div>
                    <div class="chat-info">
                        <div class="chat-header">
                            <div class="chat-name">Design Team</div>
                            <div class="chat-time">10:15</div>
                        </div>
                        <div class="chat-preview">Alex: New mockups are ready for review</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Main Chat Area -->
        <div class="chat-area">
            <div class="chat-header-main">
                <div class="chat-user-info">
                    <div class="avatar">JS</div>
                    <div class="user-status">
                        <div class="user-name">John Smith</div>
                        <div class="user-status-text status-online">Online</div>
                    </div>
                </div>
                <div class="chat-actions">
                    <button class="icon-btn" title="Voice Call">📞</button>
                    <button class="icon-btn" title="Video Call">🎥</button>
                    <button class="icon-btn" title="Search">🔍</button>
                    <button class="icon-btn" title="Menu">⋮</button>
                </div>
            </div>

            <div class="messages-container">
                <div class="message received">
                    Hi there! The presentation is scheduled for 2 PM tomorrow. 😊
                    <div class="message-time">12:40</div>
                </div>
                <div class="message sent">
                    Got it! I'll prepare the slides today. 👍
                    <div class="message-time">12:41</div>
                </div>
                <div class="message received">
                    Perfect! Don't forget to include the Q3 metrics 📊
                    <div class="message-time">12:42</div>
                </div>
                <div class="message sent">
                    Already on it! The charts look amazing btw 🚀
                    <div class="message-time">12:43</div>
                </div>
                <div class="message received">
                    Great! See you tomorrow at 2 PM then! 👋
                    <div class="message-time">12:45</div>
                </div>
            </div>

            <div class="message-input-container">
                <div class="input-wrapper">
                    <button class="attach-btn" title="Attach">📎</button>
                    <textarea class="message-input" placeholder="Type a message..." rows="1"></textarea>
                    <div class="input-actions">
                        <button class="emoji-btn" title="Emoji">😊</button>
                        <button class="send-btn" title="Send">➤</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Features Panel -->
        <div class="features-panel">
            <div class="feature-section">
                <h3>Messaging Features</h3>
                <div class="feature-item active">Disappearing Messages</div>
                <div class="feature-item">View Once Media</div>
                <div class="feature-item">Message Reactions</div>
                <div class="feature-item">Reply Privately</div>
                <div class="feature-item">Forward Messages</div>
            </div>

            <div class="feature-section">
                <h3>Media & Files</h3>
                <div class="feature-item">Send Full-quality Photos</div>
                <div class="feature-item">Document Sharing</div>
                <div class="feature-item">Voice Messages</div>
                <div class="feature-item">Media Gallery</div>
            </div>

            <div class="feature-section">
                <h3>Calls & Video</h3>
                <div class="feature-item">Voice Calls</div>
                <div class="feature-item">Video Calls</div>
                <div class="feature-item">Group Calls</div>
                <div class="feature-item">Screen Sharing</div>
            </div>

            <div class="feature-section">
                <h3>Privacy & Security</h3>
                <div class="feature-item">End-to-End Encryption</div>
                <div class="feature-item">Two-Step Verification</div>
                <div class="feature-item">Block Contacts</div>
                <div class="feature-item">Privacy Settings</div>
            </div>
        </div>
    </div>

    <script>
        // Message sending functionality
        const messageInput = document.querySelector('.message-input');
        const sendButton = document.querySelector('.send-btn');
        const messagesContainer = document.querySelector('.messages-container');
        const emojiButton = document.querySelector('.emoji-btn');

        function sendMessage() {
            const text = messageInput.value.trim();
            if (text) {
                const messageElement = document.createElement('div');
                messageElement.className = 'message sent';
                messageElement.innerHTML = `
                    ${text}
                    <div class="message-time">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
                `;
                messagesContainer.appendChild(messageElement);
                messageInput.value = '';
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
                
                // Auto-reply after 1 second
                setTimeout(() => {
                    const replies = [
                        "Thanks for your message! 👍",
                        "I'll get back to you soon 📅",
                        "Noted! 😊",
                        "Let me check and revert 🔍",
                        "Perfect timing! ⏰"
                    ];
                    const randomReply = replies[Math.floor(Math.random() * replies.length)];
                    
                    const replyElement = document.createElement('div');
                    replyElement.className = 'message received';
                    replyElement.innerHTML = `
                        ${randomReply}
                        <div class="message-time">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
                    `;
                    messagesContainer.appendChild(replyElement);
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }, 1000);
            }
        }

        sendButton.addEventListener('click', sendMessage);
        
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // Auto-resize textarea
        messageInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });

        // Chat selection
        document.querySelectorAll('.chat-item').forEach(item => {
            item.addEventListener('click', function() {
                document.querySelectorAll('.chat-item').forEach(i => i.classList.remove('active'));
                this.classList.add('active');
            });
        });

        // Feature selection
        document.querySelectorAll('.feature-item').forEach(item => {
            item.addEventListener('click', function() {
                document.querySelectorAll('.feature-item').forEach(i => i.classList.remove('active'));
                this.classList.add('active');
                // In real app, this would show feature details
            });
        });

        console.log('NOS Messenger - Premium Communication Platform');
    </script>
</body>
</html>
    ''')

@app.route('/api/send_message', methods=['POST'])
def send_message():
    data = request.json
    chat_id = data.get('chat_id')
    message = data.get('message')
    user_id = data.get('user_id')
    
    if chat_id not in messages:
        messages[chat_id] = []
    
    message_data = {
        'id': str(uuid.uuid4()),
        'text': message,
        'sender': user_id,
        'timestamp': datetime.now().isoformat(),
        'type': 'text'
    }
    
    messages[chat_id].append(message_data)
    return jsonify({'status': 'success', 'message': message_data})

@app.route('/api/chats', methods=['GET'])
def get_chats():
    return jsonify({'chats': chats})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'NOS Messenger', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
