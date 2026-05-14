from flask import render_template, request, redirect, url_for, session, flash
from flask_mail import Mail
from routes.auth.utils.utils_forgot import send_forgot_otp_email
from routes.auth.utils.utils_signup import is_password_secure
from routes.auth.database.auth_db import AuthOperation
import bcrypt
import time
import logging
from routes import users_bp

auth_db = AuthOperation()
mail = Mail()
logger = logging.getLogger(__name__)

def _get_role_dashboard(role):
    dashboards = {
        'project_lead': 'users.dashboard_project_lead',
        'quality_reviewer': 'users.dashboard_quality_reviewer',
        'tasker': 'users.dashboard_tasker',
    }
    return url_for(dashboards.get(role, 'users.index'))

@users_bp.route("/user_forgot_password", methods=['GET', 'POST'])
def user_forgot_password():
    try:
        if 'user_username' in session:
            return redirect(_get_role_dashboard(session.get('user_role', '')))

        step = session.get('user_forgot_step', 'email')

        go_back = request.args.get('go_back')
        if go_back:
            if go_back == '2':
                session['user_forgot_step'] = 'password'
            elif go_back == '1':
                session['user_forgot_step'] = 'email'
                session.pop('user_forgot_email', None)
            return redirect(url_for('users.user_forgot_password'))

        if request.method == 'POST':
            if 'email' in request.form:
                email = request.form.get('email', '').strip()
                user = auth_db.get_user_by_email(email)
                if user:
                    session['user_forgot_email'] = email
                    session['user_forgot_step'] = 'password'
                    flash("Email found. Create new password.", 'forgot_success')
                else:
                    flash("Email not registered.", 'forgot_error')
                return redirect(url_for('users.user_forgot_password'))

            elif 'new_password' in request.form:
                new_pw = request.form.get('new_password', '')
                confirm_pw = request.form.get('confirm_password', '')

                if new_pw != confirm_pw:
                    flash("Passwords do not match.", 'forgot_error')
                elif not is_password_secure(new_pw):
                    flash("Password too weak.", 'forgot_error')
                else:
                    session['user_forgot_new_password_hash'] = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
                    email = session.get('user_forgot_email')
                    try:
                        send_forgot_otp_email(email, mail)
                        session['user_forgot_step'] = 'otp'
                        flash("OTP sent to your email.", 'forgot_success')
                    except Exception:
                        flash("Network error sending OTP. Please try again.", 'forgot_error')

                return redirect(url_for('users.user_forgot_password'))

            elif 'otp' in request.form:
                user_otp = request.form.get('otp', '').strip()
                otp_session = session.get('user_forgot_otp')

                if not otp_session or time.time() > otp_session['expiry']:
                    flash("OTP expired.", 'forgot_error')
                elif user_otp != otp_session['value']:
                    flash("Invalid OTP.", 'forgot_error')
                else:
                    email = session.pop('user_forgot_email', None)
                    new_hash = session.pop('user_forgot_new_password_hash', None)
                    auth_db.update_user_password(email, new_hash)

                    session.pop('user_forgot_step', None)
                    session.pop('user_forgot_otp', None)

                    flash("Password reset successful. Please login.", 'login_success')
                    return redirect(url_for('users.user_login'))

                return redirect(url_for('users.user_forgot_password'))

        return render_template('auth/forgot_password.html', step=step)

    except Exception as e:
        logger.error(f"Forgot Password Error: {e}")
        return render_template("auth/error.html", error_message="System error. Please try again later.")