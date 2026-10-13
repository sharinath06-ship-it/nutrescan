import sqlite3
import hashlib
import secrets
import smtplib
import os
from datetime import datetime, timedelta
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# DATABASE
# ============================================================

DB = "modules/database/nutriscan.db"


# ============================================================
# EMAIL CONFIGURATION
# ============================================================

SMTP_SERVER = os.getenv(
    "SMTP_SERVER",
    "smtp.gmail.com"
)

SMTP_PORT = int(
    os.getenv(
        "SMTP_PORT",
        "587"
    )
)

SMTP_EMAIL = os.getenv(
    "SMTP_EMAIL"
)

SMTP_PASSWORD = os.getenv(
    "SMTP_PASSWORD"
)


# ============================================================
# PASSWORD HASHING
# ============================================================

def hash_password(password):
    """
    Securely hash password using PBKDF2 + random salt.
    """

    salt = secrets.token_hex(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000
    ).hex()

    return f"{salt}${password_hash}"


def verify_password(password, stored_password):
    """
    Verify password against stored hash.

    Supports old plain-text passwords as well.
    """

    if not stored_password:
        return False

    # New hashed password
    if "$" in stored_password:

        try:

            salt, stored_hash = stored_password.split(
                "$",
                1
            )

            password_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                100000
            ).hex()

            return secrets.compare_digest(
                password_hash,
                stored_hash
            )

        except Exception:

            return False

    # Old plain-text password
    return secrets.compare_digest(
        password,
        stored_password
    )


# ============================================================
# SIGN UP
# ============================================================

def signup(name, email, password):

    name = name.strip()
    email = email.strip().lower()
    password = password.strip()

    if not name:
        return False

    if not email:
        return False

    if not password:
        return False

    if len(password) < 6:
        return False

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    try:

        hashed_password = hash_password(
            password
        )

        cursor.execute(
            """
            INSERT INTO users
            (name, email, password)
            VALUES (?, ?, ?)
            """,
            (
                name,
                email,
                hashed_password
            )
        )

        conn.commit()

        return True

    except sqlite3.IntegrityError:

        return False

    except Exception as e:

        print(
            "Signup Error:",
            e
        )

        return False

    finally:

        conn.close()


# ============================================================
# LOGIN
# ============================================================

def login(email, password):

    email = email.strip().lower()

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE email=?
            """,
            (email,)
        )

        user = cursor.fetchone()

        if user is None:
            return None

        stored_password = user[3]

        if verify_password(
            password,
            stored_password
        ):

            return user

        return None

    except Exception as e:

        print(
            "Login Error:",
            e
        )

        return None

    finally:

        conn.close()


# ============================================================
# CHECK EMAIL
# ============================================================

def email_exists(email):

    email = email.strip().lower()

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE email=?
            """,
            (email,)
        )

        result = cursor.fetchone()

        return result is not None

    finally:

        conn.close()


# ============================================================
# CREATE OTP TABLE COLUMNS
# ============================================================

def ensure_otp_columns():

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    try:

        cursor.execute(
            "PRAGMA table_info(users)"
        )

        columns = [
            row[1]
            for row in cursor.fetchall()
        ]

        if "otp_hash" not in columns:

            cursor.execute(
                """
                ALTER TABLE users
                ADD COLUMN otp_hash TEXT
                """
            )

        if "otp_expiry" not in columns:

            cursor.execute(
                """
                ALTER TABLE users
                ADD COLUMN otp_expiry TEXT
                """
            )

        if "otp_verified" not in columns:

            cursor.execute(
                """
                ALTER TABLE users
                ADD COLUMN otp_verified INTEGER DEFAULT 0
                """
            )

        conn.commit()

    except Exception as e:

        print(
            "OTP Database Setup Error:",
            e
        )

    finally:

        conn.close()


# Run automatically
ensure_otp_columns()


# ============================================================
# SEND EMAIL
# ============================================================

def send_otp_email(email, otp):

    if not SMTP_EMAIL:
        raise ValueError(
            "SMTP_EMAIL is missing in .env"
        )

    if not SMTP_PASSWORD:
        raise ValueError(
            "SMTP_PASSWORD is missing in .env"
        )

    message = EmailMessage()

    message["Subject"] = "NutriScan Password Reset OTP"

    message["From"] = SMTP_EMAIL

    message["To"] = email

    message.set_content(
        f"""
Hello,

Your NutriScan password reset OTP is:

{otp}

This OTP is valid for 10 minutes.

If you did not request a password reset,
please ignore this email.

Regards,
NutriScan Team
"""
    )

    with smtplib.SMTP(
        SMTP_SERVER,
        SMTP_PORT
    ) as server:

        server.starttls()

        server.login(
            SMTP_EMAIL,
            SMTP_PASSWORD
        )

        server.send_message(
            message
        )


# ============================================================
# GENERATE OTP
# ============================================================

def generate_otp(email):

    email = email.strip().lower()

    # Make sure account exists
    if not email_exists(email):

        raise ValueError(
            "Email address is not registered."
        )

    # Generate 6-digit OTP
    otp = str(
        secrets.randbelow(900000) + 100000
    )

    # Hash OTP before storing
    otp_hash = hashlib.sha256(
        otp.encode("utf-8")
    ).hexdigest()

    # OTP valid for 10 minutes
    expiry = (
        datetime.utcnow()
        + timedelta(minutes=10)
    ).isoformat()

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            UPDATE users
            SET
                otp_hash=?,
                otp_expiry=?,
                otp_verified=0
            WHERE email=?
            """,
            (
                otp_hash,
                expiry,
                email
            )
        )

        conn.commit()

    finally:

        conn.close()

    # Send email
    send_otp_email(
        email,
        otp
    )

    return True


# ============================================================
# VERIFY OTP
# ============================================================

def verify_otp(email, otp):

    email = email.strip().lower()
    otp = otp.strip()

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SELECT
                otp_hash,
                otp_expiry
            FROM users
            WHERE email=?
            """,
            (email,)
        )

        row = cursor.fetchone()

        if row is None:
            return False

        stored_hash = row[0]
        expiry_text = row[1]

        if not stored_hash or not expiry_text:
            return False

        # Check expiry
        try:

            expiry = datetime.fromisoformat(
                expiry_text
            )

        except Exception:

            return False

        if datetime.utcnow() > expiry:

            # Clear expired OTP
            cursor.execute(
                """
                UPDATE users
                SET
                    otp_hash=NULL,
                    otp_expiry=NULL,
                    otp_verified=0
                WHERE email=?
                """,
                (email,)
            )

            conn.commit()

            return False

        # Hash entered OTP
        entered_hash = hashlib.sha256(
            otp.encode("utf-8")
        ).hexdigest()

        # Compare safely
        if not secrets.compare_digest(
            entered_hash,
            stored_hash
        ):

            return False

        # OTP correct
        cursor.execute(
            """
            UPDATE users
            SET otp_verified=1
            WHERE email=?
            """,
            (email,)
        )

        conn.commit()

        return True

    finally:

        conn.close()


# ============================================================
# RESET PASSWORD
# ============================================================

def reset_password(email, new_password):

    email = email.strip().lower()
    new_password = new_password.strip()

    if not email:
        return False

    if len(new_password) < 6:
        return False

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    try:

        # ----------------------------------------------------
        # Check OTP verification
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                otp_verified
            FROM users
            WHERE email=?
            """,
            (email,)
        )

        row = cursor.fetchone()

        if row is None:
            return False

        otp_verified = row[0]

        # Password cannot be changed without OTP
        if otp_verified != 1:

            print(
                "Password reset blocked: OTP not verified."
            )

            return False

        # ----------------------------------------------------
        # Hash new password
        # ----------------------------------------------------

        hashed_password = hash_password(
            new_password
        )

        # ----------------------------------------------------
        # Update password
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE users
            SET
                password=?,
                otp_hash=NULL,
                otp_expiry=NULL,
                otp_verified=0
            WHERE email=?
            """,
            (
                hashed_password,
                email
            )
        )

        conn.commit()

        return cursor.rowcount > 0

    except Exception as e:

        print(
            "Password Reset Error:",
            e
        )

        return False

    finally:

        conn.close()