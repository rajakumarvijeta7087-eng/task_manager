import mysql.connector
from mysql.connector import Error
from config import Config
from contextlib import contextmanager
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

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
        except Error as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def get_user_by_email(self, email):
        try:
            with self.connection() as db:
                cursor = db.cursor(dictionary=True, buffered=True)
                query = "SELECT * FROM auth WHERE email = %s"
                cursor.execute(query, (email,))
                return cursor.fetchone()
        except Exception:
            logger.exception("Error fetching user by email")
            raise

    def is_username_taken(self, username):
        try:
            with self.connection() as db:
                cursor = db.cursor()
                query = "SELECT 1 FROM auth WHERE username = %s LIMIT 1"
                cursor.execute(query, (username,))
                return cursor.fetchone() is not None
        except Exception:
            logger.exception(f"Error checking username {username}")
            return False

    def update_username(self, email, new_username):
        try:
            with self.connection() as db:
                cursor = db.cursor()
                query = "UPDATE auth SET username = %s WHERE email = %s"
                cursor.execute(query, (new_username, email))
                db.commit()
        except Exception:
            logger.exception(f"Error updating username for {email}")
            raise

    def update_user_password(self, email, new_password):
        try:
            with self.connection() as db:
                cursor = db.cursor()
                query = "UPDATE auth SET password = %s WHERE email = %s"
                cursor.execute(query, (new_password, email))
                db.commit()
        except Exception:
            logger.exception("Error updating password")
            raise

    def set_user_password(self, email, hashed_password):
        self.update_user_password(email, hashed_password)

    def insert_user_google(self, username, email, oauth_id, role):
        try:
            with self.connection() as db:
                cursor = db.cursor(buffered=True)
                query = "INSERT INTO auth (username, email, oauth_id, auth_type, is_verified, role) VALUES (%s, %s, %s, 'google', TRUE, %s)"
                cursor.execute(query, (username, email, oauth_id, role))
                db.commit()
        except Exception:
            logger.exception("Error inserting Google user")
            raise

    def user_signup_insert(self, username, password, email, role, job_title=None, is_verified=False):
        try:
            with self.connection() as db:
                cursor = db.cursor(buffered=True)
                query = "INSERT INTO auth (username, password, email, is_verified, auth_type, role, job_title) VALUES (%s, %s, %s, %s, 'manual', %s, %s)"
                cursor.execute(query, (username, password, email, is_verified, role, job_title))
                db.commit()
        except Exception:
            logger.exception("Error inserting manual signup user")
            raise

    def update_auth_type_to_both(self, email, oauth_id):
        try:
            with self.connection() as conn:
                cursor = conn.cursor(buffered=True)
                query = "UPDATE auth SET auth_type = 'both', oauth_id = %s WHERE email = %s"
                cursor.execute(query, (oauth_id, email))
                conn.commit()
                return True
        except Exception:
            logger.exception(f"Error updating auth_type to 'both' for email: {email}")
            return False

    def update_user_role(self, email, role):
        try:
            with self.connection() as db:
                cursor = db.cursor()
                query = "UPDATE auth SET role = %s WHERE email = %s"
                cursor.execute(query, (role, email))
                db.commit()
                return True
        except Exception:
            logger.exception(f"Error updating role for {email}")
            return False

    def update_last_active(self, email):
        try:
            with self.connection() as db:
                cursor = db.cursor()
                query = "UPDATE auth SET last_active = NOW() WHERE email = %s"
                cursor.execute(query, (email,))
                db.commit()
        except Exception:
            pass

    def update_cookie_consent(self, email, consent_data):
        try:
            with self.connection() as db:
                cursor = db.cursor()
                consent_json = json.dumps(consent_data)
                query = "UPDATE auth SET cookie_consent = %s WHERE email = %s"
                cursor.execute(query, (consent_json, email))
                db.commit()
        except Exception as e:
            logger.warning(f"DB: Failed to update cookie consent for {email}. Error: {e}")

    def get_cookie_consent(self, email):
        try:
            with self.connection() as db:
                cursor = db.cursor(dictionary=True)
                query = "SELECT cookie_consent FROM auth WHERE email = %s"
                cursor.execute(query, (email,))
                result = cursor.fetchone()
                if result and result.get('cookie_consent'):
                    if isinstance(result['cookie_consent'], dict):
                        return result['cookie_consent']
                    if isinstance(result['cookie_consent'], str):
                        return json.loads(result['cookie_consent'])
                    return result['cookie_consent']
                return None
        except Exception as e:
            logger.error(f"DB: Error fetching cookie consent: {e}")
            return None
