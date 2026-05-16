from functools import wraps
from flask import flash, redirect, request, session, url_for, abort
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO
from flask_mail import Mail
import logging

logger = logging.getLogger(__name__)

socketio = SocketIO()
mail = Mail()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    headers_enabled=True,
    storage_uri="memory://"
)

def init_limiter(app):
    limiter.init_app(app)

def user_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_username' not in session or 'user_email' not in session:
            flash("Access denied. Please log in to continue.", 'error')
            next_url = request.path
            return redirect(url_for('users.user_login', next=next_url))
        return f(*args, **kwargs)
    return decorated_function

def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_role') != 'admin':
            flash("Admin login required to access this page.", "error")
            return redirect(url_for('users.admin_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function