"""
Supabase database module for NutriScan.
Uses Supabase when available, falls back to local JSON storage when not.
"""
import os
import json
import base64
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

_supabase_client = None
_use_supabase = None  # None = not tested, True = working, False = fallback

# Local fallback storage path
FALLBACK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FALLBACK_USERS = os.path.join(FALLBACK_DIR, "users.json")
FALLBACK_SCANS = os.path.join(FALLBACK_DIR, "scans.json")


def _ensure_fallback_dir():
    os.makedirs(FALLBACK_DIR, exist_ok=True)


def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def _save_json(path, data):
    _ensure_fallback_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_supabase():
    """Get or create Supabase client."""
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


def is_configured():
    """Check if Supabase is properly configured."""
    return bool(SUPABASE_URL) and bool(SUPABASE_KEY)


def _test_supabase_connection():
    """Test if Supabase is reachable."""
    global _use_supabase
    if _use_supabase is not None:
        return _use_supabase
    try:
        sb = get_supabase()
        sb.table("users").select("id").limit(1).execute()
        _use_supabase = True
    except Exception:
        _use_supabase = False
    return _use_supabase


def create_user(name, email, password_hash):
    """Create a new user. Returns (success, message)."""
    if _test_supabase_connection():
        try:
            supabase = get_supabase()
            result = supabase.table("users").insert({
                "name": name.strip(),
                "email": email.lower().strip(),
                "password_hash": password_hash
            }).execute()
            if result.data:
                return True, "Account created successfully."
            return False, "Failed to create account."
        except Exception as e:
            error_str = str(e)
            if "duplicate" in error_str.lower() or "unique" in error_str.lower():
                return False, "An account with this email already exists."
            # Fall through to fallback on connection errors
            if "connect" in error_str.lower() or "resolve" in error_str.lower():
                global _use_supabase
                _use_supabase = False
            else:
                return False, str(e)

    # Fallback: local JSON storage
    users = _load_json(FALLBACK_USERS, [])
    email_lower = email.lower().strip()
    if any(u["email"] == email_lower for u in users):
        return False, "An account with this email already exists."
    users.append({
        "id": len(users) + 1,
        "name": name.strip(),
        "email": email_lower,
        "password_hash": password_hash
    })
    _save_json(FALLBACK_USERS, users)
    return True, "Account created successfully."


def authenticate_user(email, password, verify_password_func):
    """Authenticate user. Returns user dict or None."""
    if _test_supabase_connection():
        try:
            supabase = get_supabase()
            result = supabase.table("users").select("*").eq("email", email.lower().strip()).execute()
            if not result.data:
                return None
            user = result.data[0]
            if verify_password_func(password, user["password_hash"]):
                return {"id": user["id"], "name": user["name"], "email": user["email"]}
            return None
        except Exception:
            global _use_supabase
            _use_supabase = False

    # Fallback: local JSON storage
    users = _load_json(FALLBACK_USERS, [])
    email_lower = email.lower().strip()
    for user in users:
        if user["email"] == email_lower:
            if verify_password_func(password, user["password_hash"]):
                return {"id": user["id"], "name": user["name"], "email": user["email"]}
            return None
    return None


def change_password(email, new_password_hash):
    """Change user password. Returns True/False."""
    if _test_supabase_connection():
        try:
            supabase = get_supabase()
            result = supabase.table("users").update({
                "password_hash": new_password_hash
            }).eq("email", email.lower().strip()).execute()
            return bool(result.data)
        except Exception:
            global _use_supabase
            _use_supabase = False

    # Fallback: local JSON storage
    users = _load_json(FALLBACK_USERS, [])
    email_lower = email.lower().strip()
    for user in users:
        if user["email"] == email_lower:
            user["password_hash"] = new_password_hash
            _save_json(FALLBACK_USERS, users)
            return True
    return False


def user_exists(email):
    """Check if user exists."""
    if _test_supabase_connection():
        try:
            supabase = get_supabase()
            result = supabase.table("users").select("id").eq("email", email.lower().strip()).execute()
            return bool(result.data)
        except Exception:
            global _use_supabase
            _use_supabase = False

    # Fallback: local JSON storage
    users = _load_json(FALLBACK_USERS, [])
    email_lower = email.lower().strip()
    return any(u["email"] == email_lower for u in users)


def get_user_name(email):
    """Get user name by email."""
    if _test_supabase_connection():
        try:
            supabase = get_supabase()
            result = supabase.table("users").select("name").eq("email", email.lower().strip()).execute()
            if result.data:
                return result.data[0]["name"]
            return ""
        except Exception:
            global _use_supabase
            _use_supabase = False

    # Fallback: local JSON storage
    users = _load_json(FALLBACK_USERS, [])
    email_lower = email.lower().strip()
    for user in users:
        if user["email"] == email_lower:
            return user.get("name", "")
    return ""


def save_scan_history(user_email, image_name, image_data, ocr_text, matched, keyword_matches, ai_result):
    """Save scan. Returns (success, message)."""
    if _test_supabase_connection():
        try:
            supabase = get_supabase()
            scan_time = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
            image_b64 = base64.b64encode(image_data).decode("utf-8") if image_data else None
            result = supabase.table("scan_history").insert({
                "user_email": user_email,
                "scan_time": scan_time,
                "image_name": image_name,
                "image_data": image_b64,
                "ocr_text": ocr_text,
                "matched_json": json.dumps(matched, ensure_ascii=False),
                "keyword_matches_json": json.dumps(keyword_matches, ensure_ascii=False),
                "ai_result": ai_result or ""
            }).execute()
            if result.data:
                return True, result.data[0]["id"]
            return False, "Failed to save scan"
        except Exception:
            global _use_supabase
            _use_supabase = False

    # Fallback: local JSON storage
    scans = _load_json(FALLBACK_SCANS, [])
    scan_id = len(scans) + 1
    scans.append({
        "id": scan_id,
        "user_email": user_email,
        "scan_time": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "image_name": image_name,
        "image_data": base64.b64encode(image_data).decode("utf-8") if image_data else None,
        "ocr_text": ocr_text,
        "matched_json": json.dumps(matched, ensure_ascii=False),
        "keyword_matches_json": json.dumps(keyword_matches, ensure_ascii=False),
        "ai_result": ai_result or ""
    })
    _save_json(FALLBACK_SCANS, scans)
    return True, scan_id


def get_scan_history(user_email):
    """Get scan history for user. Returns list of tuples."""
    if _test_supabase_connection():
        try:
            supabase = get_supabase()
            result = supabase.table("scan_history").select("*").eq("user_email", user_email).order("id", desc=True).execute()
            scans = []
            for row in result.data:
                image_data = None
                if row.get("image_data"):
                    try:
                        image_data = base64.b64decode(row["image_data"])
                    except Exception:
                        pass
                scans.append((
                    row["id"], row["scan_time"], row.get("image_name"), image_data,
                    row.get("ocr_text", ""), row.get("matched_json", "[]"),
                    row.get("keyword_matches_json", "[]"), row.get("ai_result", "")
                ))
            return scans
        except Exception:
            global _use_supabase
            _use_supabase = False

    # Fallback: local JSON storage
    scans = _load_json(FALLBACK_SCANS, [])
    user_scans = [s for s in scans if s["user_email"] == user_email]
    user_scans.sort(key=lambda x: x["id"], reverse=True)
    result = []
    for row in user_scans:
        image_data = None
        if row.get("image_data"):
            try:
                image_data = base64.b64decode(row["image_data"])
            except Exception:
                pass
        result.append((
            row["id"], row["scan_time"], row.get("image_name"), image_data,
            row.get("ocr_text", ""), row.get("matched_json", "[]"),
            row.get("keyword_matches_json", "[]"), row.get("ai_result", "")
        ))
    return result
