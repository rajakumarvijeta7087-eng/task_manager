import pyotp
import time
import re
from flask import session
from flask_mail import Message
import string
import random

OTP_VALIDITY_PERIOD = 300

def generate_user_code(role):
    prefix = {'project_lead': 'PL', 'quality_reviewer': 'QR', 'tasker': 'TK'}.get(role, 'US')
    chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    return f"{prefix}-{chars}"

def is_valid_email(email: str) -> bool:
    pattern = r"^[^@]+@[^@]+\.[^@]+$"
    return bool(re.fullmatch(pattern, email))

def is_password_secure(password: str) -> bool:
    special_chars = r"!@#$%^&*()-_=+[{]}\|;:'\",<.>/?`~"
    return (
        len(password) >= 8 and
        any(c.isupper() for c in password) and
        any(c.isdigit() for c in password) and
        any(c in special_chars for c in password)
    )

def generate_otp():
    otp_secret = pyotp.random_base32()
    otp_value = pyotp.TOTP(otp_secret, interval=OTP_VALIDITY_PERIOD).now()
    session['signup_otp'] = {
        'value': otp_value, 
        'expiry': time.time() + OTP_VALIDITY_PERIOD
    }
    return otp_value

def validate_otp(user_otp):
    otp_data = session.get('signup_otp')
    if not otp_data:
        return False, "Session expired. Please request a new OTP."
    if time.time() > otp_data['expiry']:
        return False, "OTP has expired."
    if user_otp != otp_data['value']:
        return False, "Invalid OTP. Please check and try again."
    return True, "Success"

def clear_signup_session():
    keys = [
        'user_signup_data', 'user_signup_otp_data', 'signup_otp', 
        'signup_otp_secret', 'user_signup_otp_last_sent', 
        'user_signup_otp_attempts', 'user_signup_username',
        'user_signup_email', 'user_signup_password'
    ]
    for key in keys:
        session.pop(key, None)

def send_signup_email_otp(username, email, otp_value, mail):
    try:
        msg = Message(
            subject='Your Verification Code',
            sender='rajakumarshyam9128@gmail.com',
            recipients=[email]
        )
        msg.html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; border: 1px solid #e4e4e7; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #000000; padding: 20px; text-align: center; color: #ffffff;">
                <h2 style="margin: 0; font-weight: 600; letter-spacing: 2px;">SHYAM PRACTICE PAPER</h2>
            </div>
            <div style="padding: 30px; background-color: #ffffff; color: #09090b;">
                <p style="font-size: 16px;">Hello <strong>{username}</strong>,</p>
                <p style="font-size: 15px; color: #71717a;">Please use the following OTP to verify your email address. This code is valid for 5 minutes.</p>
                <div style="margin: 30px 0; text-align: center;">
                    <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; background-color: #f4f4f5; padding: 15px 30px; border-radius: 8px; border: 1px solid #e4e4e7;">{otp_value}</span>
                </div>
            </div>
        </div>
        """
        mail.send(msg)
        return True
    except Exception:
        return False

def send_signup_success_email(username, email, role, pl_name, qr_name, user_code, dashboard_url, mail):
    try:
        msg = Message(
            subject='Welcome to TaskTrack - Setup Complete',
            sender='rajakumarshyam9128@gmail.com',
            recipients=[email]
        )
        team_html = ""
        if pl_name or qr_name:
            team_html += f"""
            <div style="margin-top: 20px; padding: 20px; background-color: #f4f4f5; border-radius: 8px; border: 1px solid #e4e4e7;">
                <h3 style="margin-top: 0; font-size: 16px; margin-bottom: 15px; border-bottom: 1px solid #e4e4e7; padding-bottom: 10px;">Your Team Assignment</h3>
            """
            if pl_name:
                team_html += f'<p style="margin: 5px 0; font-size: 14px;"><strong style="color: #71717a;">Project Lead:</strong> {pl_name}</p>'
            if qr_name:
                team_html += f'<p style="margin: 5px 0; font-size: 14px;"><strong style="color: #71717a;">Quality Reviewer:</strong> {qr_name}</p>'
            team_html += "</div>"
        role_display = role.replace('_', ' ').title()
        msg.html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; border: 1px solid #e4e4e7; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #000000; padding: 20px; text-align: center; color: #ffffff;">
                <h2 style="margin: 0; font-weight: 600; letter-spacing: 2px;">SHYAM PRACTICE PAPER</h2>
            </div>
            <div style="padding: 30px; background-color: #ffffff; color: #09090b;">
                <h2 style="margin-top: 0;">Welcome, {username}!</h2>
                <p style="font-size: 15px; color: #3f3f46;">Your account has been successfully created. You are registered as a <strong>{role_display}</strong>.</p>
                <p style="font-size: 15px; color: #3f3f46;">Your unique User Code is: <strong>{user_code}</strong></p>
                {team_html}
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e4e4e7; text-align: center;">
                    <a href="{dashboard_url}" style="background-color: #000000; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Go to Dashboard</a>
                </div>
            </div>
        </div>
        """
        mail.send(msg)
        return True
    except Exception:
        return False