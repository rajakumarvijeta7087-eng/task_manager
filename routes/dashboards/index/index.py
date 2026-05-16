import os
from flask import flash, jsonify, redirect, render_template, request, session, url_for
from routes.dashboards.databases.index_db import UserOperation as EnrollUserOperation
from routes.auth.database.auth_db import AuthOperation
from extensions import mail
from flask_mail import Message
from routes.dashboards.utils.utils import save_upload
from routes import users_bp
from functools import wraps
import logging
import bcrypt

enroll_user_op = EnrollUserOperation()
auth_op = AuthOperation()

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_email') or not session.get('user_username'):
            flash("Please log in to continue.", "error")
            return redirect(url_for('users.user_login', next=request.url))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_role') != 'admin':
            flash("Admin access required.", "error")
            return redirect(url_for('users.index'))
        return f(*args, **kwargs)
    return decorated

def _get_user_data():
    email = session.get('user_email')
    if not email: return None
    try: return auth_op.get_user_by_email(email)
    except Exception as e:
        logger.error(f"Error fetching user data: {e}")
        return None

@users_bp.route('/api/ping', methods=['POST'])
@login_required
def api_ping():
    email = session.get('user_email')
    if email: auth_op.update_last_active(email)
    return jsonify({"status": "ok"})

@users_bp.route('/', methods=['GET'])
def index():
    try:
        r = session.get('user_role')
        c = session.get('user_code')
        if r and c:
            if r == 'admin': return redirect(url_for('users.dashboard_admin', user_code=c))
            elif r == 'project_lead': return redirect(url_for('users.dashboard_project_lead', user_code=c))
            elif r == 'quality_reviewer': return redirect(url_for('users.dashboard_quality_reviewer', user_code=c))
            elif r == 'tasker': return redirect(url_for('users.dashboard_tasker', user_code=c))
        return redirect(url_for('users.user_login'))
    except Exception as e:
        logger.error(f"Routing Error on Index: {e}")
        return render_template("auth/error.html", error_message="Something went wrong during redirect.")

@users_bp.route('/dashboard/admin/<user_code>')
@login_required
@admin_required
def dashboard_admin(user_code):
    try:
        if session.get('user_code') != user_code: return redirect(url_for('users.index'))
        user = _get_user_data()
        if not user: return redirect(url_for('users.user_login'))
        dashboard_data = enroll_user_op.admin_get_dashboard()
        return render_template('dashboards/admin.html', user=user, dashboard=dashboard_data)
    except Exception as e:
        logger.error(f"Admin Dashboard Error: {e}")
        return render_template("auth/error.html", error_message="Could not load admin dashboard.")

@users_bp.route('/dashboard/project-lead/<user_code>')
@login_required
def dashboard_project_lead(user_code):
    try:
        if session.get('user_role') != 'project_lead' or session.get('user_code') != user_code: return redirect(url_for('users.index'))
        user = _get_user_data()
        if not user: return redirect(url_for('users.user_login'))
        dashboard_data = enroll_user_op.get_project_lead_dashboard(user['id'])
        return render_template('dashboards/project_lead.html', user=user, dashboard=dashboard_data)
    except Exception as e:
        logger.error(f"PL Dashboard Error: {e}")
        return render_template("auth/error.html", error_message="Could not load project lead dashboard.")

@users_bp.route('/dashboard/quality-reviewer/<user_code>')
@login_required
def dashboard_quality_reviewer(user_code):
    try:
        if session.get('user_role') != 'quality_reviewer' or session.get('user_code') != user_code: return redirect(url_for('users.index'))
        user = _get_user_data()
        if not user: return redirect(url_for('users.user_login'))
        dashboard_data = enroll_user_op.get_quality_reviewer_dashboard(user['id'])
        return render_template('dashboards/quality_reviewer.html', user=user, dashboard=dashboard_data)
    except Exception as e:
        logger.error(f"QR Dashboard Error: {e}")
        return render_template("auth/error.html", error_message="Could not load quality reviewer dashboard.")

@users_bp.route('/dashboard/tasker/<user_code>')
@login_required
def dashboard_tasker(user_code):
    try:
        if session.get('user_role') != 'tasker' or session.get('user_code') != user_code: return redirect(url_for('users.index'))
        user = _get_user_data()
        if not user: return redirect(url_for('users.user_login'))
        dashboard_data = enroll_user_op.get_tasker_dashboard(user['id'])
        return render_template('dashboards/tasker.html', user=user, dashboard=dashboard_data)
    except Exception as e:
        logger.error(f"Tasker Dashboard Error: {e}")
        return render_template("auth/error.html", error_message="Could not load tasker dashboard.")

@users_bp.route('/tasks')
@login_required
def tasks_page():
    user = _get_user_data()
    if not user: return redirect(url_for('users.user_login'))
    tasks_data = enroll_user_op.get_all_user_tasks(user['id'])
    return render_template('dashboards/tasks.html', user=user, tasks=tasks_data)

@users_bp.route('/attendance')
@login_required
def attendance_page():
    user = _get_user_data()
    if not user: return redirect(url_for('users.user_login'))
    full_history = enroll_user_op.get_full_attendance_history(user['id'])
    return render_template('dashboards/attendance.html', user=user, attendance_history=full_history)

@users_bp.route('/leave')
@login_required
def leave_page():
    user = _get_user_data()
    if not user: return redirect(url_for('users.user_login'))
    my_leaves = enroll_user_op.get_my_leaves(user['id'])
    team_leaves = enroll_user_op.get_pending_team_leaves(user['id'], user['role'])
    return render_template('dashboards/leave.html', user=user, my_leaves=my_leaves, team_leaves=team_leaves)

@users_bp.route('/settings')
@login_required
def settings_page():
    user = _get_user_data()
    if not user: return redirect(url_for('users.user_login'))
    return render_template('dashboards/settings.html', user=user)

@users_bp.route('/api/attendance/punch-in', methods=['POST'])
@login_required
def api_punch_in():
    user = _get_user_data()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    result = enroll_user_op.punch_in(user['id'])
    if result.get("status") == "error": return jsonify({"error": result.get("message", "Error")}), 400
    return jsonify(result)

@users_bp.route('/api/attendance/punch-out', methods=['POST'])
@login_required
def api_punch_out():
    user = _get_user_data()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    result = enroll_user_op.punch_out(user['id'])
    if result.get("status") == "error": return jsonify({"error": result.get("message", "Error")}), 400
    return jsonify(result)

@users_bp.route('/api/attendance/status', methods=['GET'])
@login_required
def api_attendance_status():
    user = _get_user_data()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    return jsonify(enroll_user_op.get_attendance_status(user['id']))

@users_bp.route('/api/leave/request', methods=['POST'])
@login_required
def api_leave_request():
    try:
        user = _get_user_data()
        if not user: return jsonify({"error": "Unauthorized"}), 401
        leave_type = request.form.get('leave_type')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        reason = request.form.get('reason')
        leave_days = request.form.get('leave_days')
        attachment = request.files.get('attachment')
        if not all([leave_type, start_date, end_date, reason, leave_days]): return jsonify({"error": "Missing fields"}), 400
        attach_path = save_upload(attachment, "leaves") if attachment else None
        result = enroll_user_op.request_leave(user['id'], leave_type, start_date, end_date, reason, leave_days, attach_path)
        if result.get("status") == "ok": return jsonify({"status": "ok"})
        return jsonify({"error": result.get("message", "Error")}), 400
    except Exception:
        return jsonify({"error": "System error"}), 500

@users_bp.route('/api/leave/action', methods=['POST'])
@login_required
def api_leave_action():
    user = _get_user_data()
    if not user or user['role'] == 'tasker': return jsonify({"error": "Unauthorized"}), 403
    data = request.get_json()
    leave_id = data.get('leave_id')
    action = data.get('action')
    result = enroll_user_op.process_leave_action(leave_id, action)
    if result.get("status") == "ok":
        try:
            leave_data = result['leave_data']
            if result['new_status'] in ['approved', 'rejected']:
                msg = Message(subject=f"Leave Request {result['new_status'].title()}", sender=session.get('user_email'), recipients=[leave_data['email']])
                msg.body = f"Hello {leave_data['username']},\n\nYour leave request for {leave_data['leave_days']} days starting on {leave_data['start_date']} has been {result['new_status']}.\n\nRegards,\nManagement"
                mail.send(msg)
        except Exception as e:
            logger.error(f"Email failed to send for leave: {e}")
        return jsonify({"status": "ok"})
    return jsonify({"error": result.get("message", "Error")}), 400

@users_bp.route('/api/task/submit', methods=['POST'])
@login_required
def api_task_submit():
    user = _get_user_data()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    task_id = data.get('task_id')
    start_screenshot = data.get('start_screenshot', '')
    end_screenshot = data.get('end_screenshot', '')
    start_time = data.get('start_time', '')
    end_time = data.get('end_time', '')
    if not task_id: return jsonify({"error": "Task ID is required"}), 400
    result = enroll_user_op.submit_task(task_id, user['id'], start_screenshot, end_screenshot, start_time, end_time)
    if result.get("status") == "ok": return jsonify(result)
    return jsonify({"error": result.get("message", "Error")}), 400

@users_bp.route('/api/task/review', methods=['POST'])
@login_required
def api_task_review():
    if session.get('user_role') != 'quality_reviewer': return jsonify({"error": "Denied"}), 403
    user = _get_user_data()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    task_id = data.get('task_id')
    decision = data.get('decision')
    note = data.get('note', '')
    if not task_id or decision not in ('approve', 'reject'): return jsonify({"error": "Invalid"}), 400
    result = enroll_user_op.review_task(task_id, user['id'], decision, note)
    if result.get("status") == "ok": return jsonify(result)
    return jsonify({"error": result.get("message", "Error")}), 400

@users_bp.route('/api/task/assign', methods=['POST'])
@login_required
def api_task_assign():
    if session.get('user_role') not in ('project_lead', 'quality_reviewer'): return jsonify({"error": "Denied"}), 403
    user = _get_user_data()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    project_id = data.get('project_id')
    assigned_to = data.get('assigned_to')
    priority = data.get('priority', 'medium')
    due_date = data.get('due_date')
    if not title or not assigned_to: return jsonify({"error": "Required fields missing"}), 400
    result = enroll_user_op.assign_task(title, description, project_id, user['id'], assigned_to, priority, due_date)
    if result.get("status") == "ok": return jsonify(result)
    return jsonify({"error": result.get("message", "Error")}), 400

@users_bp.route('/api/task/bulk_assign', methods=['POST'])
@login_required
def api_bulk_assign():
    if session.get('user_role') not in ('project_lead', 'quality_reviewer', 'admin'): return jsonify({"error": "Denied"}), 403
    f = request.files.get('file')
    if f:
        path = save_upload(f, 'csv')
        user = _get_user_data()
        res = enroll_user_op.bulk_assign_tasks("." + path, user['id'])
        if res['status'] == 'ok': return jsonify(res)
        return jsonify({"error": res.get("message", "Error in bulk assign")}), 400
    return jsonify({"error": "No file uploaded"}), 400

@users_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    user = _get_user_data()
    if not user: return redirect(url_for('users.index'))
    profile_data = enroll_user_op.get_profile(user['id'])
    return render_template("dashboards/profile.html", user=user, profile=profile_data)

@users_bp.route('/api/profile/update', methods=['POST'])
@login_required
def api_profile_update():
    user = _get_user_data()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    username = data.get('username', '').strip()
    job_title = data.get('job_title', '').strip()
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    if not username or len(username) < 3: return jsonify({"error": "Username short"}), 400
    new_hash = None
    if new_password:
        if not current_password: return jsonify({"error": "Current password required"}), 400
        if not bcrypt.checkpw(current_password.encode(), user['password'].encode()): return jsonify({"error": "Current password incorrect"}), 400
        if len(new_password) < 8: return jsonify({"error": "New password short"}), 400
        new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    result = enroll_user_op.update_profile(user['id'], username, job_title, new_hash)
    if result.get("status") == "ok":
        session['user_username'] = username
        return jsonify({"status": "ok", "username": username})
    return jsonify({"error": result.get("message", "Failed")}), 400

@users_bp.route('/api/admin/role_update', methods=['POST'])
@login_required
@admin_required
def api_admin_role():
    d = request.get_json()
    if enroll_user_op.admin_update_role(d.get('user_id'), d.get('role')): return jsonify({"status": "ok"})
    return jsonify({"error": "Failed to update role"}), 400

@users_bp.route('/api/admin/delete_user', methods=['POST'])
@login_required
@admin_required
def api_admin_del():
    d = request.get_json()
    if enroll_user_op.admin_delete_user(d.get('user_id')): return jsonify({"status": "ok"})
    return jsonify({"error": "Failed to delete user"}), 400

@users_bp.route('/api/admin/settings', methods=['POST'])
@login_required
@admin_required
def api_admin_settings():
    d = request.get_json()
    if enroll_user_op.admin_update_settings(d.get('domains'), d.get('whitelist_mode')): return jsonify({"status": "ok"})
    return jsonify({"error": "Failed to update settings"}), 400

@users_bp.route('/api/admin/whitelist', methods=['POST'])
@login_required
@admin_required
def api_admin_wl():
    f = request.files.get('file')
    if f:
        path = save_upload(f, 'csv')
        if enroll_user_op.admin_upload_whitelist("." + path): return jsonify({"status": "ok"})
    return jsonify({"error": "Failed to upload whitelist"}), 400

@users_bp.route('/api/admin/send_email', methods=['POST'])
@login_required
@admin_required
def api_admin_email():
    d = request.get_json()
    try:
        msg = Message(subject=d.get('subject'), sender=session.get('user_email'), recipients=[d.get('email')])
        msg.body = d.get('body')
        mail.send(msg)
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Admin Email Send Error: {e}")
        return jsonify({"error": "Failed to send email"}), 400

@users_bp.route('/api/admin/add_user', methods=['POST'])
@login_required
@admin_required
def api_admin_add_user():
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    role = data.get('role', '').strip()
    if not username or not email or not role: return jsonify({"error": "All fields are required."}), 400
    from routes.auth.utils.utils_signup import is_valid_email
    if not is_valid_email(email): return jsonify({"error": "Invalid email address."}), 400
    result = enroll_user_op.admin_add_user(username, email, role)
    if result.get("status") == "ok": return jsonify({"status": "ok"})
    return jsonify({"error": result.get("message", "Failed to add user.")}), 400

@users_bp.route('/settings')
@login_required
def settings_page():
    user = _get_user_data()
    if not user: return redirect(url_for('users.user_login'))
    
    # Fetch current settings from database
    settings = enroll_user_op.get_user_settings(user['id'])
    return render_template('dashboards/settings.html', user=user, settings=settings)

@users_bp.route('/api/user/settings', methods=['POST'])
@login_required
def api_update_user_settings():
    user = _get_user_data()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    theme = data.get('theme', 'system')
    notif_email = 1 if data.get('notif_email') else 0
    notif_review = 1 if data.get('notif_review') else 0
    notif_digest = 1 if data.get('notif_digest') else 0
    
    result = enroll_user_op.update_user_settings(user['id'], theme, notif_email, notif_review, notif_digest)
    
    # Save theme in the session so it loads instantly on refresh
    session['user_theme'] = theme 
    
    if result.get("status") == "ok":
        return jsonify({"status": "ok"})
    return jsonify({"error": result.get("message", "Failed to save settings")}), 400