from flask import render_template, request, redirect, url_for, flash, session, jsonify
from extensions import limiter, mail
from routes.auth.utils.utils_signup import (
    clear_signup_session, is_valid_email, is_password_secure,
    generate_otp, validate_otp, send_signup_email_otp, send_signup_success_email
)
from routes.auth.database.auth_db import AuthOperation
import time
import bcrypt
import logging
from routes import users_bp

auth_db = AuthOperation()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VALID_ROLES = ['project_lead', 'quality_reviewer', 'tasker']


def _get_role_dashboard(role):
    dashboards = {
        'project_lead': 'users.dashboard_project_lead',
        'quality_reviewer': 'users.dashboard_quality_reviewer',
        'tasker': 'users.dashboard_tasker',
    }
    return url_for(dashboards.get(role, 'users.index'))


@users_bp.route("/api/auth/check-username", methods=['POST'])
def api_auth_check_username():
    data = request.get_json()
    if not data:
        return jsonify({"status": "invalid", "message": "Invalid request"}), 400
    username = data.get('username', '').strip()
    if len(username) < 3:
        return jsonify({"status": "invalid", "message": "Username must be at least 3 characters"})
    if auth_db.is_username_taken(username):
        return jsonify({"status": "taken", "message": "Username is already taken"})
    return jsonify({"status": "available", "message": "Username is available"})


@users_bp.route("/user_signup", methods=['GET', 'POST'])
def user_signup():
    try:
        if 'user_email' in session and 'user_username' in session:
            flash("You're already logged in.", 'info')
            return redirect(url_for('users.index'))

        if 'user_signup_data' not in session:
            session['user_signup_data'] = {}

        signup_data = session['user_signup_data']

        step = 'role'
        if 'user_signup_role' in signup_data:
            step = 'details'
        if 'user_signup_username' in signup_data:
            step = 'password'

        if request.method == 'GET':
            next_url = request.args.get('next')
            if next_url:
                session['user_login_next_url'] = next_url
            if request.args.get('go_back'):
                if step == 'password':
                    signup_data.pop('user_signup_username', None)
                    signup_data.pop('user_signup_email', None)
                    signup_data.pop('user_signup_job_title', None)
                    step = 'details'
                elif step == 'details':
                    signup_data.pop('user_signup_role', None)
                    step = 'role'
                session['user_signup_data'] = signup_data
                return redirect(url_for('users.user_signup'))

        if request.method == 'POST':
            if 'role' in request.form:
                role = request.form.get('role', '').strip()
                if role not in VALID_ROLES:
                    flash("Please select a valid role.", 'signup_error')
                else:
                    signup_data['user_signup_role'] = role
                    session['user_signup_data'] = signup_data
                return redirect(url_for('users.user_signup'))

            elif 'username' in request.form:
                username = request.form.get('username', '').strip()
                email = request.form.get('email', '').strip().lower()
                job_title = request.form.get('job_title', '').strip()

                if not username:
                    flash("Username is required.", 'signup_warning')
                elif len(username) < 3:
                    flash("Username must be at least 3 characters.", 'signup_warning')
                elif auth_db.is_username_taken(username):
                    flash("Username is already taken.", 'signup_error')
                elif not is_valid_email(email):
                    flash("Invalid email format.", 'signup_error')
                elif auth_db.get_user_by_email(email):
                    flash("Email already exists. Please login.", 'signup_error')
                else:
                    signup_data['user_signup_username'] = username
                    signup_data['user_signup_email'] = email
                    signup_data['user_signup_job_title'] = job_title
                    session['user_signup_data'] = signup_data
                    return redirect(url_for('users.user_signup'))
                return redirect(url_for('users.user_signup'))

            elif 'password' in request.form:
                password = request.form.get('password', '').strip()
                if not is_password_secure(password):
                    flash("Password must include uppercase, number, and special character.", 'signup_warning')
                else:
                    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                    signup_data['user_signup_password'] = hashed_pw
                    otp_value = generate_otp()
                    session['user_signup_otp_data'] = {
                        'otp': otp_value,
                        'timestamp': time.time(),
                        'email': signup_data['user_signup_email']
                    }
                    session['user_signup_data'] = signup_data

                    if send_signup_email_otp(signup_data['user_signup_username'], signup_data['user_signup_email'], otp_value, mail):
                        flash("OTP sent to your email.", 'signup_success')
                        session['user_signup_otp_last_sent'] = time.time()
                        return redirect(url_for('users.user_email_otp_verify'))
                    else:
                        flash("Network error: Could not send OTP. Please try again.", 'signup_error')
                return redirect(url_for('users.user_signup'))

        return render_template("auth/user_signup.html", step=step, signup_data=signup_data)

    except Exception as e:
        logger.error(f"Critical Signup Error: {e}")
        return render_template("auth/error.html", error_message="An unexpected error occurred during signup.")


@users_bp.route("/user_email_otp_verify", methods=['GET', 'POST'])
def user_email_otp_verify():
    try:
        otp_data = session.get('user_signup_otp_data')
        signup_data = session.get('user_signup_data')

        if not otp_data or not signup_data:
            flash("Session expired. Please restart signup.", 'signup_error')
            return redirect(url_for('users.user_signup'))

        if request.method == 'POST':
            user_otp = request.form.get('otp', '').strip()
            is_valid, msg = validate_otp(user_otp)

            if is_valid:
                try:
                    auth_db.user_signup_insert(
                        signup_data['user_signup_username'],
                        signup_data['user_signup_password'],
                        signup_data['user_signup_email'],
                        signup_data['user_signup_role'],
                        signup_data.get('user_signup_job_title'),
                        is_verified=True
                    )
                    send_signup_success_email(signup_data['user_signup_username'], signup_data['user_signup_email'], mail)
                    session['user_username'] = signup_data['user_signup_username']
                    session['user_email'] = signup_data['user_signup_email']
                    session['user_role'] = signup_data['user_signup_role']
                    next_url = session.pop('user_login_next_url', None)
                    clear_signup_session()
                    flash("Signup successful! Welcome.", 'signup_success')
                    return redirect(next_url or _get_role_dashboard(signup_data['user_signup_role']))
                except Exception as e:
                    logger.error(f"DB Insert Error: {e}")
                    flash("Database error creating account. Please contact support.", 'signup_error')
                    return redirect(url_for('users.user_signup'))
            else:
                flash(msg, 'signup_error')

        return render_template("auth/user_signup.html", step='otp', signup_data=signup_data)
    except Exception as e:
        logger.error(f"OTP Verify Error: {e}")
        return render_template("auth/error.html", error_message="System error during verification.")


@users_bp.route("/user_resend_otp", methods=['POST'])
def user_resend_otp():
    try:
        signup_data = session.get('user_signup_data', {})
        if not signup_data:
            return redirect(url_for('users.user_signup'))

        if time.time() - session.get('user_signup_otp_last_sent', 0) < 60:
            flash("Wait 60 seconds before resending OTP.", 'signup_warning')
            return redirect(url_for('users.user_email_otp_verify'))

        new_otp = generate_otp()
        session['user_signup_otp_data']['otp'] = new_otp
        session['user_signup_otp_data']['timestamp'] = time.time()
        session['user_signup_otp_last_sent'] = time.time()

        if send_signup_email_otp(signup_data['user_signup_username'], signup_data['user_signup_email'], new_otp, mail):
            flash("New OTP sent.", 'signup_success')
        else:
            flash("Failed to resend OTP.", 'signup_error')
        return redirect(url_for('users.user_email_otp_verify'))
    except Exception:
        return redirect(url_for('users.user_signup'))
