"""
Gmail SMTP email service for NutriScan.
Used to send OTP codes for password reset.

Configuration (in .env file):
    GMAIL_USER=your@gmail.com
    GMAIL_APP_PASSWORD=your_16_digit_app_password
"""
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip()

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def is_configured():
    """Check if Gmail SMTP is properly configured."""
    return bool(GMAIL_USER) and bool(GMAIL_APP_PASSWORD)


def send_otp_email(to_email, otp_code, user_name=""):
    """
    Send a password reset OTP email via Gmail SMTP.

    Args:
        to_email: Recipient email address
        otp_code: The 6-digit OTP code
        user_name: Optional user name for personalization

    Returns:
        (success: bool, message: str)
    """
    if not is_configured():
        return False, (
            "Gmail is not configured. Set GMAIL_USER and "
            "GMAIL_APP_PASSWORD in .env"
        )

    greeting = f"Hi {user_name}," if user_name else "Hi,"

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2e7d32;">🥗 NutriScan Password Reset</h2>
        <p>{greeting}</p>
        <p>We received a request to reset your NutriScan account password.</p>
        <p>Your verification code is:</p>
        <div style="background: #f5f5f5; padding: 20px; text-align: center; border-radius: 8px; margin: 20px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #1a1a1a;">{otp_code}</span>
        </div>
        <p>This code will expire in <strong>10 minutes</strong>.</p>
        <p>If you did not request a password reset, you can safely ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #888; font-size: 12px;">This is an automated message from NutriScan. Please do not reply.</p>
    </div>
    """

    text_content = (
        f"{greeting}\n\n"
        f"Your NutriScan password reset code is: {otp_code}\n"
        "This code will expire in 10 minutes.\n"
    )

    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = "NutriScan - Password Reset OTP"
        message["From"] = GMAIL_USER
        message["To"] = to_email
        message.attach(MIMEText(text_content, "plain"))
        message.attach(MIMEText(html_content, "html"))

        context = ssl.create_default_context()

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, [to_email], message.as_string())

        return True, "OTP email sent successfully."

    except smtplib.SMTPAuthenticationError:
        return False, (
            "Gmail login failed. The app password is wrong or "
            "2-Step Verification is not enabled."
        )
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"
