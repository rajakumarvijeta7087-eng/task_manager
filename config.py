import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:

    SECRET_KEY = os.environ.get('SECRET_KEY')
    CSRF_SESSION_KEY = os.environ.get('CSRF_SESSION_KEY')

    DATABASE_HOST = os.environ.get('DATABASE_HOST', 'switchback.proxy.rlwy.net')
    DATABASE_PORT = int(os.environ.get('DATABASE_PORT', 3306))
    DATABASE_USER = os.environ.get('DATABASE_USER', 'root')
    DATABASE_PASSWORD = os.environ.get('DATABASE_PASSWORD')
    DATABASE_NAME = os.environ.get('DATABASE_NAME')

    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_TIMEOUT = 15

    EMAIL_RATE_LIMIT = '5/hour'
    RECEIPT_TOKEN_EXPIRY_SECONDS = 300

    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_SAMESITE = 'Lax'
