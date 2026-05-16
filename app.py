from flask import Flask, jsonify, session, request, redirect, url_for
from flask_wtf import CSRFProtect
from extensions import init_limiter, socketio, mail
from dotenv import load_dotenv
import logging
import os
from config import Config
from datetime import timedelta
from routes import users_bp

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

mail.init_app(app)
csrf = CSRFProtect(app)
init_limiter(app)

socketio.init_app(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25
)

is_production = bool(os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER'))

app.config.update({
    'SESSION_COOKIE_SECURE': is_production,
    'SESSION_COOKIE_HTTPONLY': True,
    'SESSION_COOKIE_SAMESITE': 'Lax',
    'SESSION_PERMANENT': True,
    'PERMANENT_SESSION_LIFETIME': timedelta(minutes=30)
})

@app.after_request
def add_security_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

app.register_blueprint(users_bp)

csrf.exempt(app.view_functions['users.api_auth_check_username'])
csrf.exempt(app.view_functions['users.api_ping'])

@app.before_request
def make_session_permanent():
    session.permanent = True

@app.before_request
def check_session_validity():
    if 'user_username' in session or 'user_email' in session:
        if not ('user_username' in session and 'user_email' in session):
            for key in ['user_username', 'user_email', 'user_google_id', 'user_role', 'user_code']:
                session.pop(key, None)
            session.modified = True

@app.errorhandler(400)
def handle_400(error):
    if "CSRF" in str(error):
        return jsonify({"error": "CSRF Token Expired", "reload": True}), 400
    return jsonify({"error": "Bad Request", "message": "Invalid Request"}), 400

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "404 Not Found", "message": "The requested URL was not found."}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "500 Internal Server Error", "message": "An internal error occurred."}), 500

@app.errorhandler(403)
def forbidden_error(error):
    return jsonify({"error": "403 Forbidden", "message": "Access Denied."}), 403

@app.errorhandler(401)
def unauthorized_error(error):
    return jsonify({"error": "401 Unauthorized", "message": "Login required."}), 401

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.FileHandler("app.log"), logging.StreamHandler()]
    )
    try:
        socketio.run(app, debug=False, port=5000, allow_unsafe_werkzeug=True)
    except Exception as e:
        app.logger.error(f"Failed to start the application: {e}")