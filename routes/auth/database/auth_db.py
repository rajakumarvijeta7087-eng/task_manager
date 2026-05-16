import mysql.connector
from mysql.connector import Error
from config import Config
from contextlib import contextmanager

class AuthOperation:
    @contextmanager
    def connection(self):
        conn = None
        try:
            conn = mysql.connector.connect(
                port=int(Config.DATABASE_PORT),
                connection_timeout=10,
                host=Config.DATABASE_HOST,
                user=Config.DATABASE_USER,
                password=Config.DATABASE_PASSWORD,
                database=Config.DATABASE_NAME
            )
            yield conn
        except Error:
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def get_user_by_email(self, email):
        try:
            with self.connection() as db:
                cursor = db.cursor(dictionary=True, buffered=True)
                cursor.execute("SELECT * FROM auth WHERE email = %s", (email,))
                return cursor.fetchone()
        except Exception:
            raise

    def get_user_by_id(self, user_id):
        try:
            with self.connection() as db:
                cursor = db.cursor(dictionary=True, buffered=True)
                cursor.execute("SELECT * FROM auth WHERE id = %s", (user_id,))
                return cursor.fetchone()
        except Exception:
            return None

    def get_active_users_by_role(self, role):
        try:
            with self.connection() as db:
                cursor = db.cursor(dictionary=True, buffered=True)
                cursor.execute("SELECT id, username, email FROM auth WHERE role = %s AND is_verified = 1 ORDER BY username", (role,))
                return cursor.fetchall()
        except Exception:
            return []

    def is_username_taken(self, username):
        try:
            with self.connection() as db:
                cursor = db.cursor()
                cursor.execute("SELECT 1 FROM auth WHERE username = %s LIMIT 1", (username,))
                return cursor.fetchone() is not None
        except Exception:
            return False

    def update_username(self, email, new_username):
        try:
            with self.connection() as db:
                cursor = db.cursor()
                cursor.execute("UPDATE auth SET username = %s WHERE email = %s", (new_username, email))
                db.commit()
        except Exception:
            raise

    def update_user_password(self, email, new_password):
        try:
            with self.connection() as db:
                cursor = db.cursor()
                cursor.execute("UPDATE auth SET password = %s WHERE email = %s", (new_password, email))
                db.commit()
        except Exception:
            raise

    def set_user_password(self, email, hashed_password):
        self.update_user_password(email, hashed_password)

    def user_signup_insert(self, user_code, username, password, email, role, job_title=None, is_verified=False, assigned_pl=None, assigned_qr=None):
        try:
            with self.connection() as db:
                cursor = db.cursor(buffered=True)
                query = "INSERT INTO auth (user_code, username, password, email, is_verified, auth_type, role, job_title, assigned_pl, assigned_qr) VALUES (%s, %s, %s, %s, %s, 'manual', %s, %s, %s, %s)"
                cursor.execute(query, (user_code, username, password, email, is_verified, role, job_title, assigned_pl, assigned_qr))
                db.commit()
        except Exception:
            raise

    def update_user_role(self, email, role):
        try:
            with self.connection() as db:
                cursor = db.cursor()
                cursor.execute("UPDATE auth SET role = %s WHERE email = %s", (role, email))
                db.commit()
                return True
        except Exception:
            return False

    def update_last_active(self, email):
        try:
            with self.connection() as db:
                cursor = db.cursor()
                cursor.execute("UPDATE auth SET last_active = NOW() WHERE email = %s", (email,))
                db.commit()
        except Exception:
            pass

    def update_user_code(self, email, user_code):
        try:
            with self.connection() as db:
                cursor = db.cursor()
                cursor.execute("UPDATE auth SET user_code = %s WHERE email = %s", (user_code, email))
                db.commit()
                return True
        except Exception:
            return False

    def get_setting(self, key):
        try:
            with self.connection() as db:
                cursor = db.cursor(dictionary=True)
                cursor.execute("SELECT setting_value FROM settings WHERE setting_key = %s", (key,))
                res = cursor.fetchone()
                return res['setting_value'] if res else None
        except Exception:
            return None

    def is_email_whitelisted(self, email):
        try:
            with self.connection() as db:
                cursor = db.cursor()
                cursor.execute("SELECT 1 FROM whitelist WHERE email = %s LIMIT 1", (email,))
                return cursor.fetchone() is not None
        except Exception:
            return False