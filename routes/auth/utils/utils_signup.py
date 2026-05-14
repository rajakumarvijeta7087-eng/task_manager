import pyotp
import time
import re
from flask import session
from flask_mail import Message

OTP_VALIDITY_PERIOD = 300

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
            subject='Signup OTP Verification',
            sender='rajakumarshyam9128@gmail.com',
            recipients=[email]
        )

        msg.html = f"""
        <html>
        <body>
            <h2>Verify Your Email</h2>
            <p>Hello {username}, use OTP below:</p>
            <h3>{otp_value}</h3>
            <p>This OTP expires in 5 minutes.</p>
        </body>
        </html>
        """

        mail.send(msg)

        print(f"OTP email sent successfully to {email}")

        return True

    except Exception as e:
        print(f"OTP MAIL ERROR: {str(e)}")

        return False


def send_signup_success_email(username, email, mail):
    try:
        msg = Message(
            subject='Welcome!',
            sender='rajakumarshyam9128@gmail.com',
            recipients=[email]
        )

        msg.html = f"""
        <html>
        <body>
            <h2>Welcome {username}!</h2>
            <p>Your account has been created successfully.</p>
        </body>
        </html>
        """

        mail.send(msg)

        print(f"Welcome email sent successfully to {email}")

        return True

    except Exception as e:
        print(f"SUCCESS MAIL ERROR: {str(e)}")

        return False
