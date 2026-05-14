import mysql.connector
from mysql.connector import Error
from config import Config
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class UserOperation:
    def connection(self):
        try:
            conn = mysql.connector.connect(
                host=Config.DATABASE_HOST,
                port=Config.DATABASE_PORT,
                user=Config.DATABASE_USER,
                password=Config.DATABASE_PASSWORD,
                database=Config.DATABASE_NAME
            )
            return conn
        except Error as e:
            logger.critical(f"DATABASE CONNECTION ERROR: {e}")
            raise e

    def get_all_users_by_role(self, role):
        db = None
        cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, username, email, job_title FROM auth WHERE role = %s AND is_verified = 1 ORDER BY username",
                (role,)
            )
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"DB Error get_all_users_by_role: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def assign_task(self, title, description, project_id, created_by, assigned_to, priority, due_date):
        db = None
        cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("""
                INSERT INTO tasks (title, description, project_id, created_by, assigned_to, status, priority, due_date)
                VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s)
            """, (title, description, project_id, created_by, assigned_to, priority, due_date))
            task_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO activity_log (user_id, action_type, entity_type, entity_id, message)
                VALUES (%s, 'task_assigned', 'task', %s, %s)
            """, (created_by, task_id, f"Task '{title}' assigned"))
            db.commit()
            return task_id
        except Exception as e:
            logger.error(f"DB Error assign_task: {e}")
            if db: db.rollback()
            return None
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_projects_by_user(self, user_id):
        db = None
        cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, name FROM projects WHERE created_by = %s AND status = 'active' ORDER BY name",
                (user_id,)
            )
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"DB Error get_projects_by_user: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def punch_in(self, user_id):
        db = None
        cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, punch_in, punch_out FROM attendance WHERE user_id = %s AND work_date = CURDATE()",
                (user_id,)
            )
            existing = cursor.fetchone()
            if existing and existing['punch_in'] and not existing['punch_out']:
                return {'status': 'already_punched_in', 'punch_in': existing['punch_in'].strftime('%H:%M:%S')}
            if existing:
                cursor.execute(
                    "UPDATE attendance SET punch_in = NOW(), punch_out = NULL, total_minutes = 0 WHERE user_id = %s AND work_date = CURDATE()",
                    (user_id,)
                )
            else:
                cursor.execute(
                    "INSERT INTO attendance (user_id, punch_in, work_date) VALUES (%s, NOW(), CURDATE())",
                    (user_id,)
                )
            db.commit()
            cursor.execute(
                "SELECT punch_in FROM attendance WHERE user_id = %s AND work_date = CURDATE()",
                (user_id,)
            )
            row = cursor.fetchone()
            return {'status': 'ok', 'punch_in': row['punch_in'].strftime('%H:%M:%S')}
        except Exception as e:
            logger.error(f"DB Error punch_in: {e}")
            if db: db.rollback()
            return {'status': 'error'}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def punch_out(self, user_id):
        db = None
        cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, punch_in, punch_out FROM attendance WHERE user_id = %s AND work_date = CURDATE()",
                (user_id,)
            )
            existing = cursor.fetchone()
            if not existing or not existing['punch_in']:
                return {'status': 'not_punched_in'}
            if existing['punch_out']:
                return {'status': 'already_punched_out'}
            cursor.execute("""
                UPDATE attendance
                SET punch_out = NOW(),
                    total_minutes = TIMESTAMPDIFF(MINUTE, punch_in, NOW())
                WHERE user_id = %s AND work_date = CURDATE()
            """, (user_id,))
            db.commit()
            cursor.execute(
                "SELECT punch_in, punch_out, total_minutes FROM attendance WHERE user_id = %s AND work_date = CURDATE()",
                (user_id,)
            )
            row = cursor.fetchone()
            return {
                'status': 'ok',
                'punch_in': row['punch_in'].strftime('%H:%M:%S'),
                'punch_out': row['punch_out'].strftime('%H:%M:%S'),
                'total_minutes': row['total_minutes']
            }
        except Exception as e:
            logger.error(f"DB Error punch_out: {e}")
            if db: db.rollback()
            return {'status': 'error'}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_attendance_status(self, user_id):
        db = None
        cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute(
                "SELECT punch_in, punch_out, total_minutes FROM attendance WHERE user_id = %s AND work_date = CURDATE()",
                (user_id,)
            )
            row = cursor.fetchone()
            cursor.execute("""
                SELECT work_date, punch_in, punch_out, total_minutes
                FROM attendance
                WHERE user_id = %s
                ORDER BY work_date DESC
                LIMIT 7
            """, (user_id,))
            history = cursor.fetchall()
            for h in history:
                h['work_date'] = h['work_date'].strftime('%d %b %Y')
                h['punch_in'] = h['punch_in'].strftime('%H:%M') if h['punch_in'] else '--'
                h['punch_out'] = h['punch_out'].strftime('%H:%M') if h['punch_out'] else '--'
                hrs = h['total_minutes'] // 60
                mins = h['total_minutes'] % 60
                h['hours_display'] = f"{hrs}h {mins}m"
            if row:
                return {
                    'is_punched_in': bool(row['punch_in'] and not row['punch_out']),
                    'punch_in': row['punch_in'].strftime('%H:%M:%S') if row['punch_in'] else None,
                    'punch_out': row['punch_out'].strftime('%H:%M:%S') if row['punch_out'] else None,
                    'total_minutes': row['total_minutes'] or 0,
                    'history': history
                }
            return {'is_punched_in': False, 'punch_in': None, 'punch_out': None, 'total_minutes': 0, 'history': history}
        except Exception as e:
            logger.error(f"DB Error get_attendance_status: {e}")
            return {'is_punched_in': False, 'punch_in': None, 'punch_out': None, 'total_minutes': 0, 'history': []}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def submit_task(self, task_id, user_id, start_screenshot, end_screenshot, start_time, end_time):
        db = None
        cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("""
                UPDATE tasks
                SET status = 'submitted',
                    submitted_at = NOW(),
                    start_screenshot = %s,
                    end_screenshot = %s,
                    start_time = %s,
                    end_time = %s
                WHERE id = %s AND assigned_to = %s
            """, (start_screenshot, end_screenshot, start_time, end_time, task_id, user_id))
            cursor.execute("""
                INSERT INTO activity_log (user_id, action_type, entity_type, entity_id, message)
                SELECT %s, 'task_submitted', 'task', %s, CONCAT('Submitted task: ', title)
                FROM tasks WHERE id = %s
            """, (user_id, task_id, task_id))
            db.commit()
            return True
        except Exception as e:
            logger.error(f"DB Error submit_task: {e}")
            if db: db.rollback()
            return False
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def review_task(self, task_id, reviewer_id, decision, note=''):
        db = None
        cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            status = 'approved' if decision == 'approve' else 'rejected'
            cursor.execute("""
                UPDATE tasks
                SET status = %s, reviewed_by = %s, reviewed_at = NOW(), review_note = %s
                WHERE id = %s AND status = 'submitted'
            """, (status, reviewer_id, note, task_id))
            action = 'task_approved' if decision == 'approve' else 'task_rejected'
            cursor.execute("""
                INSERT INTO activity_log (user_id, action_type, entity_type, entity_id, message)
                SELECT %s, %s, 'task', %s, CONCAT(%s, ': ', title)
                FROM tasks WHERE id = %s
            """, (reviewer_id, action, task_id, 'Approved' if decision == 'approve' else 'Rejected', task_id))
            cursor.execute("""
                INSERT INTO activity_log (user_id, action_type, entity_type, entity_id, message)
                SELECT assigned_to, %s, 'task', %s, CONCAT('Your task was ', %s, ': ', title)
                FROM tasks WHERE id = %s
            """, (action, task_id, status, task_id))
            db.commit()
            return True
        except Exception as e:
            logger.error(f"DB Error review_task: {e}")
            if db: db.rollback()
            return False
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_task_detail(self, task_id):
        db = None
        cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("""
                SELECT t.*, a.username as assignee_name, r.username as reviewer_name,
                       p.name as project_name, c.username as creator_name
                FROM tasks t
                LEFT JOIN auth a ON t.assigned_to = a.id
                LEFT JOIN auth r ON t.reviewed_by = r.id
                LEFT JOIN auth c ON t.created_by = c.id
                LEFT JOIN projects p ON t.project_id = p.id
                WHERE t.id = %s
            """, (task_id,))
            row = cursor.fetchone()
            if row:
                for f in ['due_date', 'submitted_at', 'reviewed_at', 'start_time', 'end_time', 'created_at']:
                    if row.get(f):
                        row[f] = row[f].strftime('%d %b %Y, %H:%M') if hasattr(row[f], 'strftime') else str(row[f])
            return row
        except Exception as e:
            logger.error(f"DB Error get_task_detail: {e}")
            return None
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def update_profile(self, user_id, username, job_title, new_password_hash=None):
        db = None
        cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            if new_password_hash:
                cursor.execute(
                    "UPDATE auth SET username = %s, job_title = %s, password = %s WHERE id = %s",
                    (username, job_title, new_password_hash, user_id)
                )
            else:
                cursor.execute(
                    "UPDATE auth SET username = %s, job_title = %s WHERE id = %s",
                    (username, job_title, user_id)
                )
            db.commit()
            return True
        except Exception as e:
            logger.error(f"DB Error update_profile: {e}")
            if db: db.rollback()
            return False
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_profile(self, user_id):
        db = None
        cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, username, email, role, job_title, created_at, last_active FROM auth WHERE id = %s",
                (user_id,)
            )
            row = cursor.fetchone()
            if row and row.get('created_at'):
                row['created_at'] = row['created_at'].strftime('%d %b %Y')
            cursor.execute(
                "SELECT COUNT(*) as total FROM tasks WHERE assigned_to = %s", (user_id,)
            )
            row['total_tasks'] = cursor.fetchone()['total']
            cursor.execute(
                "SELECT COUNT(*) as total FROM tasks WHERE assigned_to = %s AND status IN ('completed','approved')", (user_id,)
            )
            row['completed_tasks'] = cursor.fetchone()['total']
            cursor.execute(
                "SELECT SUM(total_minutes) as total FROM attendance WHERE user_id = %s", (user_id,)
            )
            mins = cursor.fetchone()['total'] or 0
            row['total_hours'] = f"{mins // 60}h {mins % 60}m"
            return row
        except Exception as e:
            logger.error(f"DB Error get_profile: {e}")
            return None
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_project_lead_dashboard(self, user_id):
        db = None
        cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as total FROM projects WHERE created_by = %s", (user_id,))
            total_projects = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE created_by = %s AND status = 'completed'", (user_id,))
            completed_tasks = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE created_by = %s AND status IN ('pending', 'in_progress')", (user_id,))
            pending_tasks = cursor.fetchone()['total']
            cursor.execute("""
                SELECT COUNT(DISTINCT pm.user_id) as total
                FROM project_members pm
                JOIN projects p ON pm.project_id = p.id
                WHERE p.created_by = %s
            """, (user_id,))
            team_members = cursor.fetchone()['total']
            cursor.execute("""
                SELECT p.id, p.name, p.due_date, p.status,
                    COUNT(t.id) as task_count,
                    ROUND(IFNULL(SUM(CASE WHEN t.status IN ('completed','approved') THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(t.id), 0), 0), 0) as progress
                FROM projects p
                LEFT JOIN tasks t ON t.project_id = p.id
                WHERE p.created_by = %s AND p.status = 'active'
                GROUP BY p.id, p.name, p.due_date, p.status
                ORDER BY p.created_at DESC
                LIMIT 5
            """, (user_id,))
            active_projects = cursor.fetchall()
            for proj in active_projects:
                if proj['due_date']:
                    proj['due_date'] = proj['due_date'].strftime('%d %b %Y')
            cursor.execute("""
                SELECT t.id, t.title, t.priority, t.status, t.due_date,
                    a.username as assignee, p.name as project_name
                FROM tasks t
                LEFT JOIN auth a ON t.assigned_to = a.id
                LEFT JOIN projects p ON t.project_id = p.id
                WHERE t.created_by = %s
                ORDER BY t.created_at DESC
                LIMIT 10
            """, (user_id,))
            tasks = cursor.fetchall()
            for task in tasks:
                if task['due_date']:
                    task['due_date'] = task['due_date'].strftime('%d %b %Y')
            cursor.execute("""
                SELECT action_type, message, created_at
                FROM activity_log
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 8
            """, (user_id,))
            activity_raw = cursor.fetchall()
            recent_activity = []
            for item in activity_raw:
                atype = item['action_type']
                dot_type = 'success' if 'approved' in atype or 'created' in atype else 'warning'
                recent_activity.append({
                    'message': item['message'],
                    'time': item['created_at'].strftime('%d %b, %H:%M'),
                    'type': dot_type
                })
            cursor.execute(
                "SELECT id, username, email, job_title FROM auth WHERE role = 'quality_reviewer' AND is_verified = 1 ORDER BY username",
                ()
            )
            qr_list = cursor.fetchall()
            cursor.execute(
                "SELECT id, username, email, job_title FROM auth WHERE role = 'tasker' AND is_verified = 1 ORDER BY username",
                ()
            )
            tasker_list = cursor.fetchall()
            return {
                'total_projects': total_projects,
                'completed_tasks': completed_tasks,
                'pending_tasks': pending_tasks,
                'team_members': team_members,
                'active_projects': active_projects,
                'tasks': tasks,
                'recent_activity': recent_activity,
                'qr_list': qr_list,
                'tasker_list': tasker_list
            }
        except Exception as e:
            logger.error(f"DB Error get_project_lead_dashboard: {e}")
            return {
                'total_projects': 0, 'completed_tasks': 0,
                'pending_tasks': 0, 'team_members': 0,
                'active_projects': [], 'tasks': [], 'recent_activity': [],
                'qr_list': [], 'tasker_list': []
            }
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_quality_reviewer_dashboard(self, user_id):
        db = None
        cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE status = 'submitted'")
            pending_reviews = cursor.fetchone()['total']
            cursor.execute("""
                SELECT COUNT(*) as total FROM tasks
                WHERE reviewed_by = %s AND status = 'approved' AND DATE(reviewed_at) = CURDATE()
            """, (user_id,))
            approved_today = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE reviewed_by = %s AND status = 'rejected'", (user_id,))
            sent_back = cursor.fetchone()['total']
            cursor.execute("""
                SELECT COUNT(*) as total_reviewed,
                    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as total_approved
                FROM tasks WHERE reviewed_by = %s AND status IN ('approved', 'rejected')
            """, (user_id,))
            rate_row = cursor.fetchone()
            approval_rate = round(rate_row['total_approved'] * 100 / rate_row['total_reviewed'], 0) if rate_row['total_reviewed'] else 0
            cursor.execute("""
                SELECT t.id, t.title, t.priority, t.submitted_at,
                    t.start_screenshot, t.end_screenshot, t.start_time, t.end_time,
                    a.username as submitted_by, p.name as project
                FROM tasks t
                LEFT JOIN auth a ON t.assigned_to = a.id
                LEFT JOIN projects p ON t.project_id = p.id
                WHERE t.status = 'submitted'
                ORDER BY t.submitted_at ASC
                LIMIT 10
            """)
            review_queue = cursor.fetchall()
            for item in review_queue:
                if item['submitted_at']:
                    item['submitted_at'] = item['submitted_at'].strftime('%d %b, %H:%M')
                if item['start_time']:
                    item['start_time'] = item['start_time'].strftime('%d %b, %H:%M')
                if item['end_time']:
                    item['end_time'] = item['end_time'].strftime('%d %b, %H:%M')
            cursor.execute("""
                SELECT t.id, t.title as task_title, t.status as decision, t.reviewed_at as time,
                    a.username as tasker_name
                FROM tasks t
                LEFT JOIN auth a ON t.assigned_to = a.id
                WHERE t.reviewed_by = %s AND t.status IN ('approved', 'rejected')
                ORDER BY t.reviewed_at DESC
                LIMIT 8
            """, (user_id,))
            decisions_raw = cursor.fetchall()
            recent_decisions = []
            for item in decisions_raw:
                recent_decisions.append({
                    'task_title': item['task_title'],
                    'decision': item['decision'],
                    'tasker_name': item['tasker_name'],
                    'time': item['time'].strftime('%d %b, %H:%M') if item['time'] else ''
                })
            cursor.execute("""
                SELECT t.id, t.title, t.priority, t.submitted_at,
                    t.start_screenshot, t.end_screenshot, t.start_time, t.end_time,
                    a.username as submitted_by, p.name as project
                FROM tasks t
                LEFT JOIN auth a ON t.assigned_to = a.id
                LEFT JOIN projects p ON t.project_id = p.id
                WHERE t.status = 'submitted'
                ORDER BY t.submitted_at ASC
            """)
            submissions = cursor.fetchall()
            for sub in submissions:
                if sub['submitted_at']:
                    sub['submitted_at'] = sub['submitted_at'].strftime('%d %b %Y, %H:%M')
                if sub['start_time']:
                    sub['start_time'] = sub['start_time'].strftime('%d %b, %H:%M')
                if sub['end_time']:
                    sub['end_time'] = sub['end_time'].strftime('%d %b, %H:%M')
            cursor.execute(
                "SELECT id, username, email, job_title FROM auth WHERE role = 'project_lead' AND is_verified = 1 ORDER BY username"
            )
            pl_list = cursor.fetchall()
            cursor.execute(
                "SELECT id, username, email, job_title FROM auth WHERE role = 'tasker' AND is_verified = 1 ORDER BY username"
            )
            tasker_list = cursor.fetchall()
            return {
                'pending_reviews': pending_reviews,
                'approved_today': approved_today,
                'sent_back': sent_back,
                'approval_rate': int(approval_rate),
                'review_queue': review_queue,
                'recent_decisions': recent_decisions,
                'submissions': submissions,
                'pl_list': pl_list,
                'tasker_list': tasker_list
            }
        except Exception as e:
            logger.error(f"DB Error get_quality_reviewer_dashboard: {e}")
            return {
                'pending_reviews': 0, 'approved_today': 0,
                'sent_back': 0, 'approval_rate': 0,
                'review_queue': [], 'recent_decisions': [], 'submissions': [],
                'pl_list': [], 'tasker_list': []
            }
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_tasker_dashboard(self, user_id):
        db = None
        cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE assigned_to = %s", (user_id,))
            assigned_tasks = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE assigned_to = %s AND status = 'in_progress'", (user_id,))
            in_progress = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE assigned_to = %s AND status IN ('completed','approved')", (user_id,))
            completed = cursor.fetchone()['total']
            cursor.execute("""
                SELECT COUNT(*) as total FROM tasks
                WHERE assigned_to = %s AND status NOT IN ('completed', 'approved') AND due_date < CURDATE()
            """, (user_id,))
            overdue = cursor.fetchone()['total']
            cursor.execute("""
                SELECT t.id, t.title, t.priority, t.status, t.due_date, t.review_note,
                    p.name as project, r.username as reviewed_by_name
                FROM tasks t
                LEFT JOIN projects p ON t.project_id = p.id
                LEFT JOIN auth r ON t.reviewed_by = r.id
                WHERE t.assigned_to = %s AND t.status NOT IN ('completed', 'approved')
                ORDER BY t.due_date ASC
                LIMIT 6
            """, (user_id,))
            my_tasks = cursor.fetchall()
            for task in my_tasks:
                if task['due_date']:
                    task['due_date'] = task['due_date'].strftime('%d %b %Y')
            cursor.execute("""
                SELECT t.id, t.title, t.priority, t.status, t.due_date, t.review_note,
                    p.name as project, r.username as reviewed_by_name
                FROM tasks t
                LEFT JOIN projects p ON t.project_id = p.id
                LEFT JOIN auth r ON t.reviewed_by = r.id
                WHERE t.assigned_to = %s
                ORDER BY t.created_at DESC
            """, (user_id,))
            all_tasks = cursor.fetchall()
            for task in all_tasks:
                if task['due_date']:
                    task['due_date'] = task['due_date'].strftime('%d %b %Y')
            cursor.execute("""
                SELECT action_type, message, created_at
                FROM activity_log WHERE user_id = %s ORDER BY created_at DESC LIMIT 8
            """, (user_id,))
            activity_raw = cursor.fetchall()
            activity = []
            for item in activity_raw:
                atype = item['action_type']
                dot_type = 'success' if 'approved' in atype or 'completed' in atype else 'info'
                activity.append({
                    'message': item['message'],
                    'time': item['created_at'].strftime('%d %b, %H:%M'),
                    'type': dot_type
                })
            attendance = self.get_attendance_status(user_id)
            cursor.execute(
                "SELECT id, username, email, job_title FROM auth WHERE role = 'project_lead' AND is_verified = 1 ORDER BY username"
            )
            pl_list = cursor.fetchall()
            cursor.execute(
                "SELECT id, username, email, job_title FROM auth WHERE role = 'quality_reviewer' AND is_verified = 1 ORDER BY username"
            )
            qr_list = cursor.fetchall()
            return {
                'assigned_tasks': assigned_tasks,
                'in_progress': in_progress,
                'completed': completed,
                'overdue': overdue,
                'my_tasks': my_tasks,
                'all_tasks': all_tasks,
                'activity': activity,
                'attendance': attendance,
                'pl_list': pl_list,
                'qr_list': qr_list
            }
        except Exception as e:
            logger.error(f"DB Error get_tasker_dashboard: {e}")
            return {
                'assigned_tasks': 0, 'in_progress': 0,
                'completed': 0, 'overdue': 0,
                'my_tasks': [], 'all_tasks': [], 'activity': [],
                'attendance': {'is_punched_in': False, 'punch_in': None, 'punch_out': None, 'total_minutes': 0, 'history': []},
                'pl_list': [], 'qr_list': []
            }
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_dashboard_stats(self, user_id, role):
        try:
            if role == 'project_lead':
                data = self.get_project_lead_dashboard(user_id)
                return {
                    'total_projects': data['total_projects'],
                    'completed_tasks': data['completed_tasks'],
                    'pending_tasks': data['pending_tasks'],
                    'team_members': data['team_members']
                }
            elif role == 'quality_reviewer':
                data = self.get_quality_reviewer_dashboard(user_id)
                return {
                    'pending_reviews': data['pending_reviews'],
                    'approved_today': data['approved_today'],
                    'sent_back': data['sent_back'],
                    'approval_rate': data['approval_rate']
                }
            elif role == 'tasker':
                data = self.get_tasker_dashboard(user_id)
                return {
                    'assigned_tasks': data['assigned_tasks'],
                    'in_progress': data['in_progress'],
                    'completed': data['completed'],
                    'overdue': data['overdue']
                }
            return {}
        except Exception as e:
            logger.error(f"DB Error get_dashboard_stats: {e}")
            return {}
