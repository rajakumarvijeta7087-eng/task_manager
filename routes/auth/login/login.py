import logging
from flask import (
    flash, redirect, render_template, request, session, url_for
)
from flask_mail import Mail
from urllib.parse import urlparse, urljoin
from routes.auth.database.auth_db import AuthOperation as AuthDb
from routes.auth.utils.utils_login import (
    increment_user_login_attempts, is_user_locked_out, reset_user_login_attempts, verify_password
)
from routes import users_bp

auth_db = AuthDb()
mail = Mail()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VALID_ROLES = ['project_lead', 'quality_reviewer', 'tasker']

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

def _get_role_dashboard(role):
    dashboards = {
        'project_lead': 'users.dashboard_project_lead',
        'quality_reviewer': 'users.dashboard_quality_reviewer',
        'tasker': 'users.dashboard_tasker',
    }
    return url_for(dashboards.get(role, 'users.index'))

@users_bp.route("/user_login", methods=['GET', 'POST'])
def user_login():
    try:
        if 'user_username' in session:
            return redirect(_get_role_dashboard(session.get('user_role', '')))

        if is_user_locked_out():
            flash("Too many failed attempts. Try again in 5 minutes.", 'login_error')
            return redirect(url_for('users.index'))

        if request.method == 'GET':
            next_url = request.args.get('next')
            if next_url and is_safe_url(next_url):
                session['user_login_next_url'] = next_url
            if request.args.get('go_back'):
                session.pop('user_login_step', None)
                session.pop('user_email_pending', None)
                return redirect(url_for('users.user_login'))

        step = session.get('user_login_step', 'email')

        if request.method == 'POST':
            if 'email' in request.form:
                email = request.form.get('email', '').strip().lower()
                user = auth_db.get_user_by_email(email)

                if not user:
                    flash("No account found with this email.", 'login_error')
                    return redirect(url_for('users.user_login'))

                if user.get('auth_type') == 'google' and not user.get('password'):
                    session['user_email_pending'] = email
                    flash("Please set a password for this Google account first.", 'login_info')
                    return redirect(url_for('users.user_set_password', email=email))

                session['user_email_pending'] = email
                session['user_login_step'] = 'password'
                return redirect(url_for('users.user_login'))

            elif 'password' in request.form:
                email = session.get('user_email_pending')
                password = request.form.get('password', '')

                if not email:
                    flash("Session expired.", 'login_error')
                    session.pop('user_login_step', None)
                    return redirect(url_for('users.user_login'))

                user = auth_db.get_user_by_email(email)
                if not user:
                    session.pop('user_login_step', None)
                    return redirect(url_for('users.user_login'))

                if verify_password(password, user['password']):
                    if hasattr(session, 'regenerate'):
                        session.regenerate()

                    session['user_username'] = user['username']
                    session['user_email'] = user['email']
                    session['user_role'] = user.get('role', '')
                

                    reset_user_login_attempts()
                    session.pop('user_login_step', None)
                    session.pop('user_email_pending', None)

                    next_url = session.pop('user_login_next_url', None)
                    flash("Login successful!", 'login_success')

                    if next_url and is_safe_url(next_url):
                        return redirect(next_url)
                    return redirect(_get_role_dashboard(user.get('role', '')))
                else:
                    increment_user_login_attempts()
                    flash("Invalid password.", 'login_error')
                    return redirect(url_for('users.user_login'))

        return render_template("auth/user_login.html", step=step)

    except Exception as e:
        logger.error(f"Login Error: {e}")
        return render_template("auth/error.html", error_message="Unable to process login due to system error.")

@users_bp.route('/user_logout')
def user_logout():
    session.clear()
    flash("Logged out successfully.", 'logout_success')
    response = redirect(url_for('users.index'))
    response.set_cookie('pq_logout_trigger', '1', max_age=10)
    return response