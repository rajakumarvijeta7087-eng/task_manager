import mysql.connector
from config import Config
import csv

class UserOperation:
    def connection(self):
        return mysql.connector.connect(host=Config.DATABASE_HOST, port=Config.DATABASE_PORT, user=Config.DATABASE_USER, password=Config.DATABASE_PASSWORD, database=Config.DATABASE_NAME)

    def punch_in(self, user_id):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT id, punch_in, punch_out FROM attendance WHERE user_id = %s AND work_date = CURDATE()", (user_id,))
            existing = cursor.fetchone()
            if existing:
                if existing['punch_out'] is not None: return {'status': 'error', 'message': 'Shift completed for today. Cannot punch in again.'}
                return {'status': 'already_punched_in', 'punch_in': existing['punch_in'].strftime('%H:%M:%S')}
            cursor.execute("INSERT INTO attendance (user_id, punch_in, work_date) VALUES (%s, NOW(), CURDATE())", (user_id,))
            db.commit()
            cursor.execute("SELECT punch_in FROM attendance WHERE user_id = %s AND work_date = CURDATE()", (user_id,))
            return {'status': 'ok', 'punch_in': cursor.fetchone()['punch_in'].strftime('%H:%M:%S')}
        except Exception as e:
            if db: db.rollback()
            return {'status': 'error', 'message': str(e)}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def punch_out(self, user_id):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT id, punch_in, punch_out FROM attendance WHERE user_id = %s AND work_date = CURDATE()", (user_id,))
            existing = cursor.fetchone()
            if not existing or not existing['punch_in']: return {'status': 'error', 'message': 'Not punched in.'}
            if existing['punch_out'] is not None: return {'status': 'error', 'message': 'Already punched out.'}
            cursor.execute("UPDATE attendance SET punch_out = NOW(), total_minutes = TIMESTAMPDIFF(MINUTE, punch_in, NOW()) WHERE user_id = %s AND work_date = CURDATE()", (user_id,))
            db.commit()
            cursor.execute("SELECT punch_in, punch_out, total_minutes FROM attendance WHERE user_id = %s AND work_date = CURDATE()", (user_id,))
            row = cursor.fetchone()
            return {'status': 'ok', 'punch_in': row['punch_in'].strftime('%H:%M:%S'), 'punch_out': row['punch_out'].strftime('%H:%M:%S'), 'total_minutes': row['total_minutes']}
        except Exception as e:
            if db: db.rollback()
            return {'status': 'error', 'message': str(e)}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_attendance_status(self, user_id):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT punch_in, punch_out, total_minutes FROM attendance WHERE user_id = %s AND work_date = CURDATE()", (user_id,))
            row = cursor.fetchone()
            cursor.execute("SELECT work_date, punch_in, punch_out, total_minutes FROM attendance WHERE user_id = %s ORDER BY work_date DESC LIMIT 7", (user_id,))
            history = cursor.fetchall()
            for h in history:
                h['work_date'] = h['work_date'].strftime('%d %b %Y')
                h['punch_in'] = h['punch_in'].strftime('%H:%M') if h['punch_in'] else '--'
                h['punch_out'] = h['punch_out'].strftime('%H:%M') if h['punch_out'] else '--'
                hrs = h['total_minutes'] // 60 if h['total_minutes'] else 0
                mins = h['total_minutes'] % 60 if h['total_minutes'] else 0
                h['hours_display'] = f"{hrs}h {mins}m"
            if row:
                return {'is_punched_in': bool(row['punch_in'] and not row['punch_out']), 'punch_in': row['punch_in'].strftime('%H:%M:%S') if row['punch_in'] else None, 'punch_out': row['punch_out'].strftime('%H:%M:%S') if row['punch_out'] else None, 'total_minutes': row['total_minutes'] or 0, 'history': history}
            return {'is_punched_in': False, 'punch_in': None, 'punch_out': None, 'total_minutes': 0, 'history': history}
        except Exception:
            return {'is_punched_in': False, 'punch_in': None, 'punch_out': None, 'total_minutes': 0, 'history': []}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_full_attendance_history(self, user_id):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT work_date, punch_in, punch_out, total_minutes FROM attendance WHERE user_id = %s ORDER BY work_date DESC", (user_id,))
            history = cursor.fetchall()
            for h in history:
                h['work_date'] = h['work_date'].strftime('%d %b %Y')
                h['punch_in'] = h['punch_in'].strftime('%H:%M:%S') if h['punch_in'] else '--'
                h['punch_out'] = h['punch_out'].strftime('%H:%M:%S') if h['punch_out'] else '--'
                hrs = h['total_minutes'] // 60 if h['total_minutes'] else 0
                mins = h['total_minutes'] % 60 if h['total_minutes'] else 0
                h['hours_display'] = f"{hrs}h {mins}m"
                h['status'] = 'Present' if h['total_minutes'] else 'Incomplete'
            return history
        except Exception:
            return []
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def request_leave(self, user_id, leave_type, start_date, end_date, reason, leave_days, attachment_path):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor()
            cursor.execute("INSERT INTO leaves (user_id, leave_type, start_date, end_date, reason, leave_days, attachment, status) VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')", (user_id, leave_type, start_date, end_date, reason, leave_days, attachment_path))
            db.commit()
            return {"status": "ok"}
        except Exception as e:
            if db: db.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_my_leaves(self, user_id):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT id, leave_type, start_date, end_date, leave_days, status, reason FROM leaves WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
            leaves = cursor.fetchall()
            for l in leaves:
                l['start_date'] = l['start_date'].strftime('%d %b %Y')
                l['end_date'] = l['end_date'].strftime('%d %b %Y')
            return leaves
        except Exception:
            return []
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_pending_team_leaves(self, user_id, role):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            if role == 'quality_reviewer':
                cursor.execute("""
                    SELECT l.*, a.username, a.email FROM leaves l 
                    JOIN auth a ON l.user_id = a.id 
                    WHERE a.assigned_qr = %s AND l.status = 'pending' ORDER BY l.created_at ASC
                """, (user_id,))
            elif role == 'project_lead':
                cursor.execute("""
                    SELECT l.*, a.username, a.email FROM leaves l 
                    JOIN auth a ON l.user_id = a.id 
                    WHERE a.assigned_pl = %s AND l.status IN ('pending', 'pending_pl') ORDER BY l.created_at ASC
                """, (user_id,))
            else:
                return []
            leaves = cursor.fetchall()
            for l in leaves:
                l['start_date'] = l['start_date'].strftime('%d %b %Y')
                l['end_date'] = l['end_date'].strftime('%d %b %Y')
            return leaves
        except Exception:
            return []
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def process_leave_action(self, leave_id, action):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            new_status = ''
            if action == 'approve_qr': new_status = 'pending_pl'
            elif action == 'approve_pl': new_status = 'approved'
            elif action == 'reject': new_status = 'rejected'
            else: return {"status": "error", "message": "Invalid action"}
            
            cursor.execute("UPDATE leaves SET status = %s WHERE id = %s", (new_status, leave_id))
            
            cursor.execute("""
                SELECT l.*, a.username, a.email FROM leaves l 
                JOIN auth a ON l.user_id = a.id WHERE l.id = %s
            """, (leave_id,))
            leave_data = cursor.fetchone()
            db.commit()
            return {"status": "ok", "new_status": new_status, "leave_data": leave_data}
        except Exception as e:
            if db: db.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_all_user_tasks(self, user_id):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("""
                SELECT t.id, t.title, t.priority, t.status, t.due_date, p.name as project 
                FROM tasks t LEFT JOIN projects p ON t.project_id = p.id 
                WHERE t.assigned_to = %s ORDER BY t.created_at DESC
            """, (user_id,))
            tasks = cursor.fetchall()
            for t in tasks:
                if t['due_date']: t['due_date'] = t['due_date'].strftime('%d %b %Y')
            return tasks
        except Exception:
            return []
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_setting(self, key):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT setting_value FROM settings WHERE setting_key = %s", (key,))
            res = cursor.fetchone()
            return res['setting_value'] if res else None
        except Exception:
            return None
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def is_email_whitelisted(self, email):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor()
            cursor.execute("SELECT 1 FROM whitelist WHERE email = %s LIMIT 1", (email,))
            return cursor.fetchone() is not None
        except Exception:
            return False
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def admin_get_dashboard(self):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as t FROM auth")
            users_count = cursor.fetchone()['t']
            cursor.execute("SELECT COUNT(*) as t FROM tasks")
            tasks_count = cursor.fetchone()['t']
            
            cursor.execute("SELECT id, username, email, role, job_title, is_verified, IF(TIMESTAMPDIFF(MINUTE, last_active, NOW()) < 5, 1, 0) as is_live FROM auth WHERE role = 'project_lead' ORDER BY created_at DESC")
            pl_users = cursor.fetchall()
            
            cursor.execute("SELECT id, username, email, role, job_title, is_verified, IF(TIMESTAMPDIFF(MINUTE, last_active, NOW()) < 5, 1, 0) as is_live FROM auth WHERE role = 'quality_reviewer' ORDER BY created_at DESC")
            qr_users = cursor.fetchall()
            
            cursor.execute("SELECT id, username, email, role, job_title, is_verified, IF(TIMESTAMPDIFF(MINUTE, last_active, NOW()) < 5, 1, 0) as is_live FROM auth WHERE role = 'tasker' ORDER BY created_at DESC")
            tk_users = cursor.fetchall()

            cursor.execute("SELECT setting_key, setting_value FROM settings")
            st = {r['setting_key']: r['setting_value'] for r in cursor.fetchall()}
            return {'users_count': users_count, 'tasks_count': tasks_count, 'pl_users': pl_users, 'qr_users': qr_users, 'tk_users': tk_users, 'settings': st}
        except Exception:
            return {}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def admin_update_role(self, user_id, new_role):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor()
            cursor.execute("UPDATE auth SET role = %s WHERE id = %s", (new_role, user_id))
            db.commit()
            return True
        except Exception:
            if db: db.rollback()
            return False
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def admin_delete_user(self, user_id):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor()
            cursor.execute("DELETE FROM auth WHERE id = %s", (user_id,))
            db.commit()
            return True
        except Exception:
            if db: db.rollback()
            return False
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def admin_update_settings(self, domains, whitelist_mode):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor()
            cursor.execute("INSERT INTO settings (setting_key, setting_value) VALUES ('allowed_domains', %s) ON DUPLICATE KEY UPDATE setting_value = %s", (domains, domains))
            cursor.execute("INSERT INTO settings (setting_key, setting_value) VALUES ('whitelist_mode', %s) ON DUPLICATE KEY UPDATE setting_value = %s", (whitelist_mode, whitelist_mode))
            db.commit()
            return True
        except Exception:
            if db: db.rollback()
            return False
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def admin_upload_whitelist(self, file_path):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor()
            with open(file_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = row.get('Email', '').strip()
                    name = row.get('Name', '').strip()
                    if email:
                        cursor.execute("INSERT IGNORE INTO whitelist (email, username) VALUES (%s, %s)", (email, name))
            db.commit()
            return True
        except Exception:
            if db: db.rollback()
            return False
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def admin_add_user(self, username, email, role):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor()
            cursor.execute("SELECT 1 FROM auth WHERE email = %s LIMIT 1", (email,))
            if cursor.fetchone():
                return {"status": "error", "message": "Email already exists in the system."}
            cursor.execute("INSERT INTO auth (username, email, role, password, is_verified, auth_type) VALUES (%s, %s, %s, '', 1, 'manual')", (username, email, role))
            db.commit()
            return {"status": "ok"}
        except Exception as e:
            if db: db.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def bulk_assign_tasks(self, file_path, created_by):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            success_count = 0
            errors = []
            with open(file_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = row.get('Email', '').strip()
                    title = row.get('Task Name', '').strip()
                    desc = row.get('Description', '').strip()
                    due_date = row.get('End Date', '').strip()
                    if not email or not title: continue
                    cursor.execute("SELECT id FROM auth WHERE email = %s", (email,))
                    u = cursor.fetchone()
                    if not u:
                        errors.append(f"User {email} not found")
                        continue
                    cursor.execute("INSERT INTO tasks (title, description, created_by, assigned_to, status, due_date) VALUES (%s, %s, %s, %s, 'pending', %s)", (title, desc, created_by, u['id'], due_date if due_date else None))
                    success_count += 1
            db.commit()
            return {"status": "ok", "success": success_count, "errors": errors}
        except Exception as e:
            if db: db.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def assign_task(self, title, description, project_id, created_by, assigned_to, priority, due_date):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("INSERT INTO tasks (title, description, project_id, created_by, assigned_to, status, priority, due_date) VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s)", (title, description, project_id, created_by, assigned_to, priority, due_date))
            task_id = cursor.lastrowid
            cursor.execute("INSERT INTO activity_log (user_id, action_type, entity_type, entity_id, message) VALUES (%s, 'task_assigned', 'task', %s, %s)", (created_by, task_id, f"Task '{title}' assigned"))
            db.commit()
            return {"status": "ok", "task_id": task_id}
        except Exception as e:
            if db: db.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def submit_task(self, task_id, user_id, start_screenshot, end_screenshot, start_time, end_time):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("UPDATE tasks SET status = 'submitted', submitted_at = NOW(), start_screenshot = %s, end_screenshot = %s, start_time = %s, end_time = %s WHERE id = %s AND assigned_to = %s", (start_screenshot, end_screenshot, start_time, end_time, task_id, user_id))
            if cursor.rowcount == 0: return {"status": "error", "message": "Task not found."}
            cursor.execute("INSERT INTO activity_log (user_id, action_type, entity_type, entity_id, message) SELECT %s, 'task_submitted', 'task', %s, CONCAT('Submitted task: ', title) FROM tasks WHERE id = %s", (user_id, task_id, task_id))
            db.commit()
            return {"status": "ok"}
        except Exception as e:
            if db: db.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def review_task(self, task_id, reviewer_id, decision, note=''):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            status = 'approved' if decision == 'approve' else 'rejected'
            cursor.execute("UPDATE tasks SET status = %s, reviewed_by = %s, reviewed_at = NOW(), review_note = %s WHERE id = %s AND status = 'submitted'", (status, reviewer_id, note, task_id))
            if cursor.rowcount == 0: return {"status": "error", "message": "Task not found."}
            action = 'task_approved' if decision == 'approve' else 'task_rejected'
            cursor.execute("INSERT INTO activity_log (user_id, action_type, entity_type, entity_id, message) SELECT %s, %s, 'task', %s, CONCAT(%s, ': ', title) FROM tasks WHERE id = %s", (reviewer_id, action, task_id, 'Approved' if decision == 'approve' else 'Rejected', task_id))
            cursor.execute("INSERT INTO activity_log (user_id, action_type, entity_type, entity_id, message) SELECT assigned_to, %s, 'task', %s, CONCAT('Your task was ', %s, ': ', title) FROM tasks WHERE id = %s", (action, task_id, status, task_id))
            db.commit()
            return {"status": "ok"}
        except Exception as e:
            if db: db.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def update_profile(self, user_id, username, job_title, new_password_hash=None):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor()
            if new_password_hash: cursor.execute("UPDATE auth SET username = %s, job_title = %s, password = %s WHERE id = %s", (username, job_title, new_password_hash, user_id))
            else: cursor.execute("UPDATE auth SET username = %s, job_title = %s WHERE id = %s", (username, job_title, user_id))
            db.commit()
            return {"status": "ok"}
        except Exception as e:
            if db: db.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_profile(self, user_id):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT id, username, email, role, job_title, created_at, last_active FROM auth WHERE id = %s", (user_id,))
            row = cursor.fetchone()
            if row:
                if row.get('created_at'): row['created_at'] = row['created_at'].strftime('%d %b %Y')
                if row.get('last_active'): row['last_active'] = row['last_active'].strftime('%d %b %Y, %H:%M')
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE assigned_to = %s", (user_id,))
            row['total_tasks'] = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE assigned_to = %s AND status IN ('completed','approved')", (user_id,))
            row['completed_tasks'] = cursor.fetchone()['total']
            cursor.execute("SELECT SUM(total_minutes) as total FROM attendance WHERE user_id = %s", (user_id,))
            mins = cursor.fetchone()['total'] or 0
            row['total_hours'] = f"{mins // 60}h {mins % 60}m"
            return row
        except Exception:
            return None
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_project_lead_dashboard(self, user_id):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as total FROM projects WHERE created_by = %s", (user_id,))
            total_projects = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE created_by = %s AND status = 'completed'", (user_id,))
            completed_tasks = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE created_by = %s AND status IN ('pending', 'in_progress')", (user_id,))
            pending_tasks = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) as total FROM auth WHERE assigned_pl = %s", (user_id,))
            team_members = cursor.fetchone()['total']
            cursor.execute("""
                SELECT p.id, p.name, p.due_date, p.status, COUNT(t.id) as task_count, ROUND(IFNULL(SUM(CASE WHEN t.status IN ('completed','approved') THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(t.id), 0), 0), 0) as progress
                FROM projects p LEFT JOIN tasks t ON t.project_id = p.id WHERE p.created_by = %s AND p.status = 'active' GROUP BY p.id, p.name, p.due_date, p.status ORDER BY p.created_at DESC LIMIT 5
            """, (user_id,))
            active_projects = cursor.fetchall()
            for proj in active_projects:
                if proj['due_date']: proj['due_date'] = proj['due_date'].strftime('%d %b %Y')
            cursor.execute("""
                SELECT t.id, t.title, t.priority, t.status, t.due_date, a.username as assignee, p.name as project_name
                FROM tasks t LEFT JOIN auth a ON t.assigned_to = a.id LEFT JOIN projects p ON t.project_id = p.id WHERE t.created_by = %s ORDER BY t.created_at DESC LIMIT 10
            """, (user_id,))
            tasks = cursor.fetchall()
            for task in tasks:
                if task['due_date']: task['due_date'] = task['due_date'].strftime('%d %b %Y')
            cursor.execute("SELECT action_type, message, created_at FROM activity_log WHERE user_id = %s ORDER BY created_at DESC LIMIT 8", (user_id,))
            recent_activity = [{'message': item['message'], 'time': item['created_at'].strftime('%d %b, %H:%M'), 'type': 'success' if 'approved' in item['action_type'] or 'created' in item['action_type'] else 'warning'} for item in cursor.fetchall()]
            cursor.execute("SELECT id, username, email, job_title, user_code, IF(TIMESTAMPDIFF(MINUTE, last_active, NOW()) < 5, 1, 0) as is_live FROM auth WHERE role = 'quality_reviewer' AND assigned_pl = %s ORDER BY username", (user_id,))
            qr_list = cursor.fetchall()
            cursor.execute("SELECT id, username, email, job_title, user_code, IF(TIMESTAMPDIFF(MINUTE, last_active, NOW()) < 5, 1, 0) as is_live FROM auth WHERE role = 'tasker' AND assigned_pl = %s ORDER BY username", (user_id,))
            tasker_list = cursor.fetchall()
            attendance = self.get_attendance_status(user_id)
            return {'total_projects': total_projects, 'completed_tasks': completed_tasks, 'pending_tasks': pending_tasks, 'team_members': team_members, 'active_projects': active_projects, 'tasks': tasks, 'recent_activity': recent_activity, 'qr_list': qr_list, 'tasker_list': tasker_list, 'attendance': attendance}
        except Exception:
            return {'total_projects': 0, 'completed_tasks': 0, 'pending_tasks': 0, 'team_members': 0, 'active_projects': [], 'tasks': [], 'recent_activity': [], 'qr_list': [], 'tasker_list': [], 'attendance': {'is_punched_in': False, 'punch_in': None, 'punch_out': None, 'total_minutes': 0, 'history': []}}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_quality_reviewer_dashboard(self, user_id):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as total FROM tasks t JOIN auth a ON t.assigned_to = a.id WHERE t.status = 'submitted' AND a.assigned_qr = %s", (user_id,))
            pending_reviews = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE reviewed_by = %s AND status = 'approved' AND DATE(reviewed_at) = CURDATE()", (user_id,))
            approved_today = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE reviewed_by = %s AND status = 'rejected'", (user_id,))
            sent_back = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) as total_reviewed, SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as total_approved FROM tasks WHERE reviewed_by = %s AND status IN ('approved', 'rejected')", (user_id,))
            rate_row = cursor.fetchone()
            approval_rate = round(rate_row['total_approved'] * 100 / rate_row['total_reviewed'], 0) if rate_row['total_reviewed'] else 0
            cursor.execute("""
                SELECT t.id, t.title, t.priority, t.submitted_at, t.start_screenshot, t.end_screenshot, t.start_time, t.end_time, a.username as submitted_by, p.name as project
                FROM tasks t LEFT JOIN auth a ON t.assigned_to = a.id LEFT JOIN projects p ON t.project_id = p.id WHERE t.status = 'submitted' AND a.assigned_qr = %s ORDER BY t.submitted_at ASC LIMIT 10
            """, (user_id,))
            review_queue = cursor.fetchall()
            for item in review_queue:
                if item['submitted_at']: item['submitted_at'] = item['submitted_at'].strftime('%d %b, %H:%M')
                if item['start_time']: item['start_time'] = item['start_time'].strftime('%d %b, %H:%M')
                if item['end_time']: item['end_time'] = item['end_time'].strftime('%d %b, %H:%M')
            cursor.execute("""
                SELECT t.id, t.title as task_title, t.status as decision, t.reviewed_at as time, a.username as tasker_name
                FROM tasks t LEFT JOIN auth a ON t.assigned_to = a.id WHERE t.reviewed_by = %s AND t.status IN ('approved', 'rejected') ORDER BY t.reviewed_at DESC LIMIT 8
            """, (user_id,))
            decisions_raw = cursor.fetchall()
            recent_decisions = [{'task_title': item['task_title'], 'decision': item['decision'], 'tasker_name': item['tasker_name'], 'time': item['time'].strftime('%d %b, %H:%M') if item['time'] else ''} for item in decisions_raw]
            cursor.execute("SELECT a.username, a.job_title, a.user_code, IF(TIMESTAMPDIFF(MINUTE, a.last_active, NOW()) < 5, 1, 0) as is_live FROM auth a JOIN auth me ON me.assigned_pl = a.id WHERE me.id = %s", (user_id,))
            pl_info = cursor.fetchone()
            cursor.execute("SELECT id, username, email, job_title, user_code, IF(TIMESTAMPDIFF(MINUTE, last_active, NOW()) < 5, 1, 0) as is_live FROM auth WHERE role = 'tasker' AND assigned_qr = %s ORDER BY username", (user_id,))
            tasker_list = cursor.fetchall()
            attendance = self.get_attendance_status(user_id)
            return {'pending_reviews': pending_reviews, 'approved_today': approved_today, 'sent_back': sent_back, 'approval_rate': int(approval_rate), 'review_queue': review_queue, 'recent_decisions': recent_decisions, 'pl_info': pl_info, 'tasker_list': tasker_list, 'attendance': attendance}
        except Exception:
            return {'pending_reviews': 0, 'approved_today': 0, 'sent_back': 0, 'approval_rate': 0, 'review_queue': [], 'recent_decisions': [], 'pl_info': None, 'tasker_list': [], 'attendance': {'is_punched_in': False, 'punch_in': None, 'punch_out': None, 'total_minutes': 0, 'history': []}}
        finally:
            if cursor: cursor.close()
            if db: db.close()

    def get_tasker_dashboard(self, user_id):
        db = cursor = None
        try:
            db = self.connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE assigned_to = %s", (user_id,))
            assigned_tasks = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE assigned_to = %s AND status = 'in_progress'", (user_id,))
            in_progress = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE assigned_to = %s AND status IN ('completed','approved')", (user_id,))
            completed = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE assigned_to = %s AND status NOT IN ('completed', 'approved') AND due_date < CURDATE()", (user_id,))
            overdue = cursor.fetchone()['total']
            cursor.execute("""
                SELECT t.id, t.title, t.priority, t.status, t.due_date, t.review_note, p.name as project, r.username as reviewed_by_name
                FROM tasks t LEFT JOIN projects p ON t.project_id = p.id LEFT JOIN auth r ON t.reviewed_by = r.id
                WHERE t.assigned_to = %s AND t.status NOT IN ('completed', 'approved') ORDER BY t.due_date ASC LIMIT 6
            """, (user_id,))
            my_tasks = cursor.fetchall()
            for task in my_tasks:
                if task['due_date']: task['due_date'] = task['due_date'].strftime('%d %b %Y')
            cursor.execute("""
                SELECT t.id, t.title, t.priority, t.status, t.due_date, t.review_note, p.name as project, r.username as reviewed_by_name
                FROM tasks t LEFT JOIN projects p ON t.project_id = p.id LEFT JOIN auth r ON t.reviewed_by = r.id
                WHERE t.assigned_to = %s ORDER BY t.created_at DESC
            """, (user_id,))
            all_tasks = cursor.fetchall()
            for task in all_tasks:
                if task['due_date']: task['due_date'] = task['due_date'].strftime('%d %b %Y')
            cursor.execute("SELECT action_type, message, created_at FROM activity_log WHERE user_id = %s ORDER BY created_at DESC LIMIT 8", (user_id,))
            activity = [{'message': item['message'], 'time': item['created_at'].strftime('%d %b, %H:%M'), 'type': 'success' if 'approved' in item['action_type'] or 'completed' in item['action_type'] else 'info'} for item in cursor.fetchall()]
            attendance = self.get_attendance_status(user_id)
            cursor.execute("SELECT a.username, a.job_title, a.user_code, IF(TIMESTAMPDIFF(MINUTE, a.last_active, NOW()) < 5, 1, 0) as is_live FROM auth a JOIN auth me ON me.assigned_pl = a.id WHERE me.id = %s", (user_id,))
            pl_info = cursor.fetchone()
            cursor.execute("SELECT a.username, a.job_title, a.user_code, IF(TIMESTAMPDIFF(MINUTE, a.last_active, NOW()) < 5, 1, 0) as is_live FROM auth a JOIN auth me ON me.assigned_qr = a.id WHERE me.id = %s", (user_id,))
            qr_info = cursor.fetchone()
            return {'assigned_tasks': assigned_tasks, 'in_progress': in_progress, 'completed': completed, 'overdue': overdue, 'my_tasks': my_tasks, 'all_tasks': all_tasks, 'activity': activity, 'attendance': attendance, 'pl_info': pl_info, 'qr_info': qr_info}
        except Exception:
            return {'assigned_tasks': 0, 'in_progress': 0, 'completed': 0, 'overdue': 0, 'my_tasks': [], 'all_tasks': [], 'activity': [], 'attendance': {'is_punched_in': False, 'punch_in': None, 'punch_out': None, 'total_minutes': 0, 'history': []}, 'pl_info': None, 'qr_info': None}
        finally:
            if cursor: cursor.close()
            if db: db.close()