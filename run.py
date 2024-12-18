from app import create_app
from config import Config
from flask import redirect, url_for

app = create_app(Config)
@app.route('/')
def home():
    # 重定向到 auth/login
    return redirect(url_for('auth.login'))

if __name__ == "__main__":
    app.run(host='0.0.0.0',debug=True, port=5033)
