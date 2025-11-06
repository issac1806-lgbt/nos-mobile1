from flask import Flask, render_template_string
import os

app = Flask(__name__)

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NOS Mobile Messenger</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                background: linear-gradient(135deg, #128C7E, #075E54);
                margin: 0; 
                height: 100vh; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
                color: white;
            }
            .container { 
                background: rgba(255,255,255,0.95); 
                padding: 40px; 
                border-radius: 20px; 
                text-align: center; 
                max-width: 400px;
                width: 90%;
                box-shadow: 0 20px 40px rgba(0,0,0,0.3);
                color: #333;
            }
            h1 { 
                color: #075E54; 
                margin-bottom: 10px;
                font-size: 32px;
            }
            p {
                color: #666;
                margin-bottom: 30px;
                line-height: 1.6;
            }
            .features {
                text-align: left;
                margin: 25px 0;
            }
            .feature {
                margin: 12px 0;
                padding: 10px;
                background: #f8f9fa;
                border-radius: 10px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            button { 
                background: #25D366; 
                color: white; 
                border: none; 
                padding: 16px 32px; 
                border-radius: 25px; 
                font-size: 18px; 
                cursor: pointer;
                width: 100%;
                font-weight: bold;
                margin-top: 20px;
                transition: background 0.3s;
            }
            button:hover {
                background: #128C7E;
            }
            .logo {
                font-size: 48px;
                margin-bottom: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">🚀</div>
            <h1>NOS Mobile</h1>
            <p>Complete messenger with voice/video calls and group chats</p>
            
            <div class="features">
                <div class="feature">✅ Voice & Video Calls</div>
                <div class="feature">✅ Voice Messages</div>
                <div class="feature">✅ Group Chats</div>
                <div class="feature">✅ Real-time Messaging</div>
                <div class="feature">✅ Mobile Optimized</div>
            </div>
            
            <button onclick="startApp()">Start Messaging</button>
        </div>
        
        <script>
            function startApp() {
                const username = prompt('Enter your name to start using NOS:');
                if (username && username.trim()) {
                    alert('Welcome to NOS Mobile, ' + username + '! 🎉');
                    // In the full version, this would open the chat interface
                }
            }
            
            // Display current environment
            console.log('NOS Mobile - Render Deployment');
        </script>
    </body>
    </html>
    '''

@app.route('/health')
def health():
    return {'status': 'healthy', 'service': 'NOS Mobile'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
