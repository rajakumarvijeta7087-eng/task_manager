from flask import flash, jsonify, redirect, render_template, request, session, url_for, make_response
from routes.index.databases.index_handler_db import UserOperation as EnrollUserOperation
from routes.auth.database.auth_db import AuthOperation
from routes import users_bp
import logging
import bcrypt
from functools import wraps

enroll_user_op = EnrollUserOperation()
auth_op = AuthOperation()

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

ROLE_TEMPLATES = {
    'project_lead': 'dashboards/project_lead.html',
    'quality_reviewer': 'dashboards/quality_reviewer.html',
    'tasker': 'dashboards/tasker.html',
}

ROLE_ENDPOINTS = {
    'project_lead': 'users.dashboard_project_lead',
    'quality_reviewer': 'users.dashboard_quality_reviewer',
    'tasker': 'users.dashboard_tasker',
}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_email') or not session.get('user_username'):
            flash("Please log in to continue.", "login_error")
            return redirect(url_for('users.user_login', next=request.url))
        return f(*args, **kwargs)
    return decorated


def _get_user_data():
    email = session.get('user_email')
    if not email:
        return None
    try:
        return auth_op.get_user_by_email(email)
    except Exception as e:
        logger.error(f"Failed to fetch user data: {e}")
        return None


@users_bp.route('/', methods=['GET'])
def index():
    try:
        user_email = session.get('user_email')
        user_role = session.get('user_role')
        if user_email and user_role:
            endpoint = ROLE_ENDPOINTS.get(user_role)
            if endpoint:
                return redirect(url_for(endpoint))
        return redirect(url_for('users.user_login'))
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        return render_template("auth/error.html", error_message="Something went wrong.")


@users_bp.route('/dashboard/project-lead')
@login_required
def dashboard_project_lead():
    try:
        if session.get('user_role') != 'project_lead':
            flash("Access denied.", "error")
            return redirect(url_for('users.index'))
        user = _get_user_data()
        if not user:
            flash("Could not load your profile.", "error")
            return redirect(url_for('users.user_login'))
        dashboard_data = enroll_user_op.get_project_lead_dashboard(user['id'])
        return render_template(
            ROLE_TEMPLATES['project_lead'],
            user=user,
            dashboard=dashboard_data,
            role_label="Project Lead",
            role_icon="🎯"
        )
    except Exception as e:
        import traceback
        logger.error(f"Project Lead Dashboard Error: {e}")
        logger.error(traceback.format_exc())
        return render_template("auth/error.html", error_message="Could not load dashboard.")


@users_bp.route('/dashboard/quality-reviewer')
@login_required
def dashboard_quality_reviewer():
    try:
        if session.get('user_role') != 'quality_reviewer':
            flash("Access denied.", "error")
            return redirect(url_for('users.index'))
        user = _get_user_data()
        if not user:
            flash("Could not load your profile.", "error")
            return redirect(url_for('users.user_login'))
        dashboard_data = enroll_user_op.get_quality_reviewer_dashboard(user['id'])
        return render_template(
            ROLE_TEMPLATES['quality_reviewer'],
            user=user,
            dashboard=dashboard_data,
            role_label="Quality Reviewer",
            role_icon="🔍"
        )
    except Exception as e:
        logger.error(f"Quality Reviewer Dashboard Error: {e}")
        return render_template("auth/error.html", error_message="Could not load dashboard.")


@users_bp.route('/dashboard/tasker')
@login_required
def dashboard_tasker():
    try:
        if session.get('user_role') != 'tasker':
            flash("Access denied.", "error")
            return redirect(url_for('users.index'))
        user = _get_user_data()
        if not user:
            flash("Could not load your profile.", "error")
            return redirect(url_for('users.user_login'))
        dashboard_data = enroll_user_op.get_tasker_dashboard(user['id'])
        return render_template(
            ROLE_TEMPLATES['tasker'],
            user=user,
            dashboard=dashboard_data,
            role_label="Tasker",
            role_icon="⚡"
        )
    except Exception as e:
        logger.error(f"Tasker Dashboard Error: {e}")
        return render_template("auth/error.html", error_message="Could not load dashboard.")


@users_bp.route('/api/attendance/punch-in', methods=['POST'])
@login_required
def api_punch_in():
    try:
        user = _get_user_data()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        result = enroll_user_op.punch_in(user['id'])
        return jsonify(result)
    except Exception as e:
        logger.error(f"Punch In Error: {e}")
        return jsonify({"status": "error"}), 500


@users_bp.route('/api/attendance/punch-out', methods=['POST'])
@login_required
def api_punch_out():
    try:
        user = _get_user_data()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        result = enroll_user_op.punch_out(user['id'])
        return jsonify(result)
    except Exception as e:
        logger.error(f"Punch Out Error: {e}")
        return jsonify({"status": "error"}), 500


@users_bp.route('/api/attendance/status', methods=['GET'])
@login_required
def api_attendance_status():
    try:
        user = _get_user_data()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        result = enroll_user_op.get_attendance_status(user['id'])
        return jsonify(result)
    except Exception as e:
        logger.error(f"Attendance Status Error: {e}")
        return jsonify({"status": "error"}), 500


@users_bp.route('/api/task/submit', methods=['POST'])
@login_required
def api_task_submit():
    try:
        user = _get_user_data()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json()
        task_id = data.get('task_id')
        start_screenshot = data.get('start_screenshot', '')
        end_screenshot = data.get('end_screenshot', '')
        start_time = data.get('start_time', '')
        end_time = data.get('end_time', '')
        if not task_id:
            return jsonify({"error": "Task ID required"}), 400
        result = enroll_user_op.submit_task(task_id, user['id'], start_screenshot, end_screenshot, start_time, end_time)
        return jsonify({"status": "ok" if result else "error"})
    except Exception as e:
        logger.error(f"Task Submit Error: {e}")
        return jsonify({"error": "Could not submit task"}), 500


@users_bp.route('/api/task/review', methods=['POST'])
@login_required
def api_task_review():
    try:
        if session.get('user_role') != 'quality_reviewer':
            return jsonify({"error": "Access denied"}), 403
        user = _get_user_data()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json()
        task_id = data.get('task_id')
        decision = data.get('decision')
        note = data.get('note', '')
        if not task_id or decision not in ('approve', 'reject'):
            return jsonify({"error": "Invalid request"}), 400
        result = enroll_user_op.review_task(task_id, user['id'], decision, note)
        return jsonify({"status": "ok" if result else "error"})
    except Exception as e:
        logger.error(f"Task Review Error: {e}")
        return jsonify({"error": "Could not review task"}), 500


@users_bp.route('/api/task/detail/<int:task_id>', methods=['GET'])
@login_required
def api_task_detail(task_id):
    try:
        task = enroll_user_op.get_task_detail(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404
        return jsonify(task)
    except Exception as e:
        logger.error(f"Task Detail Error: {e}")
        return jsonify({"error": "Could not fetch task"}), 500


@users_bp.route('/api/task/assign', methods=['POST'])
@login_required
def api_task_assign():
    try:
        if session.get('user_role') not in ('project_lead', 'quality_reviewer'):
            return jsonify({"error": "Access denied"}), 403
        user = _get_user_data()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json()
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        project_id = data.get('project_id')
        assigned_to = data.get('assigned_to')
        priority = data.get('priority', 'medium')
        due_date = data.get('due_date')
        if not title or not assigned_to:
            return jsonify({"error": "Title and assignee required"}), 400
        task_id = enroll_user_op.assign_task(title, description, project_id, user['id'], assigned_to, priority, due_date)
        return jsonify({"status": "ok" if task_id else "error", "task_id": task_id})
    except Exception as e:
        logger.error(f"Task Assign Error: {e}")
        return jsonify({"error": "Could not assign task"}), 500


@users_bp.route('/api/projects/list', methods=['GET'])
@login_required
def api_projects_list():
    try:
        user = _get_user_data()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        projects = enroll_user_op.get_projects_by_user(user['id'])
        return jsonify(projects)
    except Exception as e:
        logger.error(f"Projects List Error: {e}")
        return jsonify([]), 500


@users_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    try:
        user = _get_user_data()
        if not user:
            flash("Could not load profile.", "error")
            return redirect(url_for('users.index'))
        profile_data = enroll_user_op.get_profile(user['id'])
        return render_template("dashboards/profile.html", user=user, profile=profile_data)
    except Exception as e:
        logger.error(f"Profile Error: {e}")
        return render_template("auth/error.html", error_message="Could not load profile.")


@users_bp.route('/api/profile/update', methods=['POST'])
@login_required
def api_profile_update():
    try:
        user = _get_user_data()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json()
        username = data.get('username', '').strip()
        job_title = data.get('job_title', '').strip()
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        if not username or len(username) < 3:
            return jsonify({"error": "Username must be at least 3 characters"}), 400
        new_hash = None
        if new_password:
            if not current_password:
                return jsonify({"error": "Current password required"}), 400
            if not bcrypt.checkpw(current_password.encode(), user['password'].encode()):
                return jsonify({"error": "Current password is incorrect"}), 400
            if len(new_password) < 8:
                return jsonify({"error": "New password must be at least 8 characters"}), 400
            new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        result = enroll_user_op.update_profile(user['id'], username, job_title, new_hash)
        if result:
            session['user_username'] = username
            return jsonify({"status": "ok", "username": username})
        return jsonify({"error": "Update failed"}), 500
    except Exception as e:
        logger.error(f"Profile Update Error: {e}")
        return jsonify({"error": "Could not update profile"}), 500


@users_bp.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    try:
        user = _get_user_data()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        role = session.get('user_role')
        stats = enroll_user_op.get_dashboard_stats(user['id'], role)
        return jsonify({"status": "ok", "data": stats})
    except Exception as e:
        logger.error(f"Dashboard Stats API Error: {e}")
        return jsonify({"error": "Could not fetch stats"}), 500