import string
import random
import time
import logging
import bcrypt
from flask import flash, redirect, render_template, request, session, url_for
from urllib.parse import urlparse, urljoin
from extensions import mail
from routes.auth.database.auth_db import AuthOperation as AuthDb
from routes.auth.utils.utils_login import increment_user_login_attempts, is_user_locked_out, reset_user_login_attempts, verify_password
from routes.auth.utils.utils_signup import generate_otp, send_signup_email_otp
from routes import users_bp

auth_db = AuthDb()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

def _get_role_dashboard(role, user_code):
    dashboards = {
        'admin': 'users.dashboard_admin',
        'project_lead': 'users.dashboard_project_lead',
        'quality_reviewer': 'users.dashboard_quality_reviewer',
        'tasker': 'users.dashboard_tasker',
    }
    return url_for(dashboards.get(role, 'users.index'), user_code=user_code)

@users_bp.route("/user_login", methods=['GET', 'POST'])
def user_login():
    try:
        if 'user_username' in session and 'user_code' in session:
            return redirect(_get_role_dashboard(session.get('user_role', ''), session.get('user_code', '')))
        
        if is_user_locked_out():
            flash("Too many failed attempts. Try again in 5 minutes.", 'error')
            return redirect(url_for('users.index'))
            
        if request.method == 'GET':
            next_url = request.args.get('next')
            if next_url and is_safe_url(next_url):
                session['user_login_next_url'] = next_url
            if request.args.get('go_back'):
                session.pop('user_login_step', None)
                session.pop('user_email_pending', None)
                session.pop('user_setup_pending', None)
                return redirect(url_for('users.user_login'))
                
        step = session.get('user_login_step', 'email')
        
        if request.method == 'POST':
            if 'email' in request.form:
                email = request.form.get('email', '').strip().lower()
                user = auth_db.get_user_by_email(email)
                
                if not user:
                    flash("No account found with this email.", 'error')
                    return redirect(url_for('users.user_login'))
                
                if user.get('role') == 'admin':
                    flash("Admin accounts must log in through the Admin Portal.", 'info')
                    return redirect(url_for('users.admin_login'))

                if not user.get('password') or user.get('password') == '':
                    otp_val = generate_otp()
                    session['user_setup_pending'] = {
                        'email': user['email'], 'username': user['username'], 'role': user['role']
                    }
                    send_signup_email_otp(user['username'], user['email'], otp_val, mail)
                    session['user_login_step'] = 'setup_otp'
                    flash("First time login detected. Verification code sent to your email.", "info")
                    return redirect(url_for('users.user_login'))
                    
                session['user_email_pending'] = email
                session['user_login_step'] = 'password'
                return redirect(url_for('users.user_login'))
                
            elif 'password' in request.form:
                email = session.get('user_email_pending')
                password = request.form.get('password', '')
                
                if not email:
                    flash("Session expired. Please start over.", 'error')
                    session.pop('user_login_step', None)
                    return redirect(url_for('users.user_login'))
                    
                user = auth_db.get_user_by_email(email)
                if not user or user.get('role') == 'admin':
                    session.pop('user_login_step', None)
                    return redirect(url_for('users.user_login'))
                    
                if verify_password(password, user['password']):
                    user_code = user.get('user_code')
                    if not user_code:
                        prefix = {'project_lead': 'PL', 'quality_reviewer': 'QR', 'tasker': 'TK'}.get(user.get('role', ''), 'US')
                        chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
                        user_code = f"{prefix}-{chars}"
                        auth_db.update_user_code(email, user_code)

                    if hasattr(session, 'regenerate'): session.regenerate()
                    session['user_username'] = user['username']
                    session['user_email'] = user['email']
                    session['user_role'] = user.get('role', '')
                    session['user_code'] = user_code
                    
                    reset_user_login_attempts()
                    session.pop('user_login_step', None)
                    session.pop('user_email_pending', None)
                    next_url = session.pop('user_login_next_url', None)
                    
                    flash("Login successful!", 'success')
                    if next_url and is_safe_url(next_url): return redirect(next_url)
                    return redirect(_get_role_dashboard(user.get('role', ''), user_code))
                else:
                    increment_user_login_attempts()
                    flash("Invalid password.", 'error')
                    return redirect(url_for('users.user_login'))

            elif 'setup_otp' in request.form:
                pending = session.get('user_setup_pending')
                if not pending: return redirect(url_for('users.user_login'))

                user_otp = request.form.get('setup_otp', '').strip()
                from routes.auth.utils.utils_signup import validate_otp
                is_valid, msg = validate_otp(user_otp)

                if is_valid:
                    session['user_login_step'] = 'set_new_password'
                    flash("Email verified. Please set your permanent password.", 'success')
                    return redirect(url_for('users.user_login'))
                else:
                    flash(msg, 'error')
                    return redirect(url_for('users.user_login'))

            elif 'new_password' in request.form:
                pending = session.get('user_setup_pending')
                new_password = request.form.get('new_password', '')

                if not pending or len(new_password) < 8:
                    flash("Password must be at least 8 characters.", 'error')
                    return redirect(url_for('users.user_login'))

                hashed_pw = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                auth_db.update_user_password(pending['email'], hashed_pw)

                user = auth_db.get_user_by_email(pending['email'])
                user_code = user.get('user_code')
                if not user_code:
                    role = pending['role']
                    prefix = {'project_lead': 'PL', 'quality_reviewer': 'QR', 'tasker': 'TK'}.get(role, 'US')
                    chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
                    user_code = f"{prefix}-{chars}"
                    auth_db.update_user_code(pending['email'], user_code)

                if hasattr(session, 'regenerate'): session.regenerate()
                session['user_username'] = pending['username']
                session['user_email'] = pending['email']
                session['user_role'] = pending['role']
                session['user_code'] = user_code

                reset_user_login_attempts()
                session.pop('user_setup_pending', None)
                session.pop('user_login_step', None)

                flash("Account setup complete! Welcome aboard.", 'success')
                return redirect(_get_role_dashboard(pending['role'], user_code))
                    
        return render_template("auth/user_login.html", step=step)
    except Exception:
        return render_template("auth/error.html", error_message="Unable to process login.")

@users_bp.route("/admin_login", methods=['GET', 'POST'])
def admin_login():
    try:
        if 'user_username' in session and session.get('user_role') == 'admin':
            return redirect(url_for('users.dashboard_admin', user_code=session.get('user_code')))
            
        if is_user_locked_out():
            flash("Too many failed attempts. Try again in 5 minutes.", 'error')
            return redirect(url_for('users.index'))
            
        if request.method == 'GET' and request.args.get('go_back'):
            session.pop('admin_login_step', None)
            session.pop('admin_email_pending', None)
            session.pop('admin_setup_pending', None)
            return redirect(url_for('users.admin_login'))
            
        step = session.get('admin_login_step', 'email')
        
        if request.method == 'POST':
            if 'email' in request.form:
                email = request.form.get('email', '').strip().lower()
                user = auth_db.get_user_by_email(email)
                
                if not user or user.get('role') != 'admin':
                    flash("Unauthorized. Admin privileges required.", 'error')
                    return redirect(url_for('users.admin_login'))

                if not user.get('password') or user.get('password') == '':
                    otp_val = generate_otp()
                    session['admin_setup_pending'] = {
                        'email': user['email'], 'username': user['username'], 'role': 'admin'
                    }
                    send_signup_email_otp(user['username'], user['email'], otp_val, mail)
                    session['admin_login_step'] = 'setup_otp'
                    flash("First time login detected. Verification code sent to your email.", "info")
                    return redirect(url_for('users.admin_login'))
                    
                session['admin_email_pending'] = email
                session['admin_login_step'] = 'password'
                return redirect(url_for('users.admin_login'))
                
            elif 'password' in request.form:
                email = session.get('admin_email_pending')
                password = request.form.get('password', '')
                
                if not email:
                    flash("Session expired. Please start over.", 'error')
                    session.pop('admin_login_step', None)
                    return redirect(url_for('users.admin_login'))
                    
                user = auth_db.get_user_by_email(email)
                if not user or user.get('role') != 'admin':
                    session.pop('admin_login_step', None)
                    return redirect(url_for('users.admin_login'))
                    
                if verify_password(password, user['password']):
                    user_code = user.get('user_code')
                    if not user_code:
                        chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
                        user_code = f"AD-{chars}"
                        auth_db.update_user_code(email, user_code)

                    otp_val = generate_otp()
                    session['admin_2fa_pending'] = {
                        'email': user['email'], 'username': user['username'], 'role': 'admin', 'user_code': user_code
                    }
                    send_signup_email_otp(user['username'], user['email'], otp_val, mail)
                    
                    reset_user_login_attempts()
                    session.pop('admin_login_step', None)
                    session.pop('admin_email_pending', None)
                    return render_template("auth/admin_otp.html", email=user['email'])
                else:
                    increment_user_login_attempts()
                    flash("Invalid password.", 'error')
                    return redirect(url_for('users.admin_login'))

            elif 'setup_otp' in request.form:
                pending = session.get('admin_setup_pending')
                if not pending: return redirect(url_for('users.admin_login'))

                user_otp = request.form.get('setup_otp', '').strip()
                from routes.auth.utils.utils_signup import validate_otp
                is_valid, msg = validate_otp(user_otp)

                if is_valid:
                    session['admin_login_step'] = 'set_new_password'
                    flash("Email verified. Please set your permanent password.", 'success')
                    return redirect(url_for('users.admin_login'))
                else:
                    flash(msg, 'error')
                    return redirect(url_for('users.admin_login'))

            elif 'new_password' in request.form:
                pending = session.get('admin_setup_pending')
                new_password = request.form.get('new_password', '')

                if not pending or len(new_password) < 8:
                    flash("Password must be at least 8 characters.", 'error')
                    return redirect(url_for('users.admin_login'))

                hashed_pw = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                auth_db.update_user_password(pending['email'], hashed_pw)

                user = auth_db.get_user_by_email(pending['email'])
                user_code = user.get('user_code')
                if not user_code:
                    chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
                    user_code = f"AD-{chars}"
                    auth_db.update_user_code(pending['email'], user_code)

                if hasattr(session, 'regenerate'): session.regenerate()
                session['user_username'] = pending['username']
                session['user_email'] = pending['email']
                session['user_role'] = pending['role']
                session['user_code'] = user_code

                reset_user_login_attempts()
                session.pop('admin_setup_pending', None)
                session.pop('admin_login_step', None)

                flash("Password set successfully! Welcome to the Admin Console.", 'success')
                return redirect(url_for('users.dashboard_admin', user_code=user_code))
                    
        return render_template("auth/admin_login.html", step=step)
    except Exception:
        return render_template("auth/error.html", error_message="Unable to process admin login.")

@users_bp.route("/admin_login_verify", methods=['POST'])
def admin_login_verify():
    pending = session.get('admin_2fa_pending')
    if not pending:
        return redirect(url_for('users.admin_login'))
        
    user_otp = request.form.get('otp', '').strip()
    from routes.auth.utils.utils_signup import validate_otp
    is_valid, msg = validate_otp(user_otp)
    
    if is_valid:
        if hasattr(session, 'regenerate'): session.regenerate()
        session['user_username'] = pending['username']
        session['user_email'] = pending['email']
        session['user_role'] = pending['role']
        session['user_code'] = pending['user_code']
        session.pop('admin_2fa_pending', None)
        flash("Admin verification successful.", 'success')
        return redirect(url_for('users.dashboard_admin', user_code=pending['user_code']))
    else:
        flash(msg, 'error')
        return render_template("auth/admin_otp.html", email=pending['email'])

@users_bp.route('/user_logout')
def user_logout():
    session.clear()
    flash("Logged out successfully.", 'success')
    return redirect(url_for('users.index'))