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
        <title>NOS Mobile</title>
        <style>
            body { 
                font-family: Arial; 
                background: #128C7E; 
                margin: 0; 
                height: 100vh; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
            }
            .container { 
                background: white; 
                padding: 40px; 
                border-radius: 20px; 
                text-align: center; 
                max-width: 400px;
                width: 90%;
            }
            h1 { 
                color: #075E54; 
                margin-bottom: 10px;
            }
            p {
                color: #666;
                margin-bottom: 20px;
            }
            button { 
                background: #25D366; 
                color: white; 
                border: none; 
                padding: 15px 30px; 
                border-radius: 25px; 
                font-size: 18px; 
                cursor: pointer;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 NOS Mobile</h1>
            <p>Complete messenger with voice/video calls</p>
            <button onclick="alert('NOS Mobile Ready!')">Start Messaging</button>
        </div>
    </body>
    </html>
    '''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
