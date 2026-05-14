from flask_mail import Mail, Message
import time
from flask import session
import pyotp

mail = Mail()

def send_forgot_otp_email(email, mail):
    if 'user_forgot_otp_secret' not in session:
        session['user_forgot_otp_secret'] = pyotp.random_base32()

    totp = pyotp.TOTP(session['user_forgot_otp_secret'], interval=300)
    otp = totp.now()
    otp_expiry = time.time() + 300
    session['user_forgot_otp'] = {'value': otp, 'expiry': otp_expiry}
    session['user_forgot_otp_last_sent'] = time.time()

    msg = Message('Reset Password OTP',
                  sender='rajakumarshyam9128@gmail.com',
                  recipients=[email])
    
    msg.html = f"""
    <html><body>
      <div class="header">Reset Password OTP</div>
      <p>Use the OTP below to reset your password:</p>
      <div class="otp-box">{otp}</div>
    </body></html>
    """

    mail.send(msg)