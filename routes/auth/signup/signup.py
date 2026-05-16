from flask import render_template, request, redirect, url_for, flash, session, jsonify
from extensions import limiter, mail
from routes.auth.utils.utils_signup import (
    clear_signup_session, is_valid_email, is_password_secure,
    generate_otp, validate_otp, send_signup_email_otp, send_signup_success_email, generate_user_code
)
from routes.auth.database.auth_db import AuthOperation
from routes.dashboards.index_db import UserOperation
import time
import bcrypt
import logging
from routes import users_bp

auth_db = AuthOperation()
signup_db_helper = UserOperation() # <-- Renamed to fix variable pollution collision

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VALID_ROLES = ['project_lead', 'quality_reviewer', 'tasker']

def _get_role_dashboard(role, user_code):
    dashboards = {
        'project_lead': 'users.dashboard_project_lead',
        'quality_reviewer': 'users.dashboard_quality_reviewer',
        'tasker': 'users.dashboard_tasker',
    }
    return url_for(dashboards.get(role, 'users.index'), user_code=user_code)

@users_bp.route("/api/auth/check-username", methods=['POST'])
def api_auth_check_username():
    data = request.get_json()
    if not data: return jsonify({"status": "invalid", "message": "Invalid request"}), 400
    username = data.get('username', '').strip()
    if len(username) < 3: return jsonify({"status": "invalid", "message": "Username must be at least 3 characters"})
    if auth_db.is_username_taken(username): return jsonify({"status": "taken", "message": "Username is already taken"})
    return jsonify({"status": "available", "message": "Username is available"})

@users_bp.route("/user_signup", methods=['GET', 'POST'])
def user_signup():
    try:
        if 'user_email' in session and 'user_username' in session: return redirect(url_for('users.index'))
        if 'user_signup_data' not in session: session['user_signup_data'] = {}
        signup_data = session['user_signup_data']
        step = 'role'
        
        if 'user_signup_role' in signup_data: step = 'details'
        if 'user_signup_username' in signup_data:
            if signup_data['user_signup_role'] in ['quality_reviewer', 'tasker']:
                step = 'assignment' if 'user_signup_assigned_pl' not in signup_data else 'password'
            else:
                step = 'password'

        if request.method == 'GET':
            if request.args.get('next'): session['user_login_next_url'] = request.args.get('next')
            if request.args.get('go_back'):
                if step == 'password':
                    if signup_data['user_signup_role'] in ['quality_reviewer', 'tasker']:
                        signup_data.pop('user_signup_assigned_pl', None)
                        signup_data.pop('user_signup_assigned_qr', None)
                        step = 'assignment'
                    else:
                        signup_data.pop('user_signup_username', None)
                        signup_data.pop('user_signup_email', None)
                        signup_data.pop('user_signup_job_title', None)
                        step = 'details'
                elif step == 'assignment':
                    signup_data.pop('user_signup_username', None)
                    signup_data.pop('user_signup_email', None)
                    signup_data.pop('user_signup_job_title', None)
                    step = 'details'
                elif step == 'details':
                    signup_data.pop('user_signup_role', None)
                    step = 'role'
                session['user_signup_data'] = signup_data
                return redirect(url_for('users.user_signup'))

        pl_list = qr_list = []
        if step == 'assignment':
            pl_list = auth_db.get_active_users_by_role('project_lead')
            if signup_data['user_signup_role'] == 'tasker':
                qr_list = auth_db.get_active_users_by_role('quality_reviewer')

        if request.method == 'POST':
            if 'role' in request.form:
                role = request.form.get('role', '').strip()
                if role not in VALID_ROLES: flash("Invalid role.", 'error')
                else:
                    signup_data['user_signup_role'] = role
                    session['user_signup_data'] = signup_data
                return redirect(url_for('users.user_signup'))

            elif 'username' in request.form:
                username = request.form.get('username', '').strip()
                email = request.form.get('email', '').strip().lower()
                job_title = request.form.get('job_title', '').strip()

                wl_mode = signup_db_helper.get_setting('whitelist_mode')
                if wl_mode == 'on' and not signup_db_helper.is_email_whitelisted(email):
                    flash("Your email is not authorized by the admin.", 'error')
                    return redirect(url_for('users.user_signup'))

                allowed_domains = signup_db_helper.get_setting('allowed_domains')
                if allowed_domains:
                    domain_list = [d.strip().lower() for d in allowed_domains.split(',')]
                    user_domain = email.split('@')[-1]
                    if user_domain not in domain_list:
                        flash(f"Domain @{user_domain} is not allowed by admin.", 'error')
                        return redirect(url_for('users.user_signup'))

                if not username or len(username) < 3: flash("Invalid username.", 'warning')
                elif auth_db.is_username_taken(username): flash("Username taken.", 'error')
                elif not is_valid_email(email): flash("Invalid email.", 'error')
                elif auth_db.get_user_by_email(email): flash("Email exists.", 'error')
                else:
                    signup_data.update({'user_signup_username': username, 'user_signup_email': email, 'user_signup_job_title': job_title})
                    session['user_signup_data'] = signup_data
                return redirect(url_for('users.user_signup'))

            elif 'assigned_pl' in request.form:
                assigned_pl = request.form.get('assigned_pl')
                if not assigned_pl: flash("Project Lead required.", 'warning')
                else:
                    signup_data['user_signup_assigned_pl'] = assigned_pl
                    if signup_data['user_signup_role'] == 'tasker':
                        assigned_qr = request.form.get('assigned_qr')
                        if not assigned_qr: flash("Quality Reviewer required.", 'warning')
                        else: signup_data['user_signup_assigned_qr'] = assigned_qr
                    session['user_signup_data'] = signup_data
                return redirect(url_for('users.user_signup'))

            elif 'password' in request.form:
                password = request.form.get('password', '').strip()
                if not is_password_secure(password): flash("Weak password.", 'warning')
                else:
                    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                    signup_data['user_signup_password'] = hashed_pw
                    otp_value = generate_otp()
                    session['user_signup_otp_data'] = {'otp': otp_value, 'timestamp': time.time(), 'email': signup_data['user_signup_email']}
                    session['user_signup_data'] = signup_data
                    if send_signup_email_otp(signup_data['user_signup_username'], signup_data['user_signup_email'], otp_value, mail):
                        flash("OTP sent.", 'success')
                        session['user_signup_otp_last_sent'] = time.time()
                        return redirect(url_for('users.user_email_otp_verify'))
                    else: flash("Failed to send OTP.", 'error')
                return redirect(url_for('users.user_signup'))

        return render_template("auth/user_signup.html", step=step, signup_data=signup_data, pl_list=pl_list, qr_list=qr_list)
    except Exception:
        return render_template("auth/error.html", error_message="Signup Error.")

@users_bp.route("/user_email_otp_verify", methods=['GET', 'POST'])
def user_email_otp_verify():
    try:
        otp_data = session.get('user_signup_otp_data')
        signup_data = session.get('user_signup_data')
        if not otp_data or not signup_data: return redirect(url_for('users.user_signup'))

        if request.method == 'POST':
            is_valid, msg = validate_otp(request.form.get('otp', '').strip())
            if is_valid:
                user_code = generate_user_code(signup_data['user_signup_role'])
                auth_db.user_signup_insert(
                    user_code, signup_data['user_signup_username'], signup_data['user_signup_password'],
                    signup_data['user_signup_email'], signup_data['user_signup_role'],
                    signup_data.get('user_signup_job_title'), True,
                    signup_data.get('user_signup_assigned_pl'), signup_data.get('user_signup_assigned_qr')
                )
                pl_name = qr_name = None
                if signup_data.get('user_signup_assigned_pl'):
                    pl_user = auth_db.get_user_by_id(signup_data['user_signup_assigned_pl'])
                    if pl_user: pl_name = pl_user['username']
                if signup_data.get('user_signup_assigned_qr'):
                    qr_user = auth_db.get_user_by_id(signup_data['user_signup_assigned_qr'])
                    if qr_user: qr_name = qr_user['username']
                
                new_user_row = auth_db.get_user_by_email(signup_data['user_signup_email'])
                dashboard_url = url_for(f"users.dashboard_{signup_data['user_signup_role']}", user_code=user_code, _external=True)
                send_signup_success_email(signup_data['user_signup_username'], signup_data['user_signup_email'], signup_data['user_signup_role'], pl_name, qr_name, user_code, dashboard_url, mail)
                
                session.clear()
                session.update({
                    'user_username': new_user_row['username'], 
                    'user_email': new_user_row['email'], 
                    'user_role': new_user_row['role'], 
                    'user_code': user_code
                })
                
                next_url = session.pop('user_login_next_url', None)
                clear_signup_session()
                flash("Signup successful!", 'success')
                return redirect(next_url or _get_role_dashboard(new_user_row['role'], user_code))
            else:
                flash(msg, 'error')
        return render_template("auth/user_signup.html", step='otp', signup_data=signup_data)
    except Exception as e:
        logger.error(f"Signup Verification Failure: {e}")
        return render_template("auth/error.html", error_message="Verification Error.")

@users_bp.route("/user_resend_otp", methods=['POST'])
def user_resend_otp():
    try:
        signup_data = session.get('user_signup_data', {})
        if not signup_data: return redirect(url_for('users.user_signup'))
        if time.time() - session.get('user_signup_otp_last_sent', 0) < 60:
            flash("Wait 60 seconds.", 'warning')
            return redirect(url_for('users.user_email_otp_verify'))
        new_otp = generate_otp()
        session['user_signup_otp_data'].update({'otp': new_otp, 'timestamp': time.time()})
        session['user_signup_otp_last_sent'] = time.time()
        if send_signup_email_otp(signup_data['user_signup_username'], signup_data['user_signup_email'], new_otp, mail): flash("New OTP sent.", 'success')
        else: flash("Failed to send OTP.", 'error')
        return redirect(url_for('users.user_email_otp_verify'))
    except Exception:
        return redirect(url_for('users.user_signup'))