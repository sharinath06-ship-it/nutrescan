import streamlit as st
import pandas as pd
import hashlib
import secrets
import re
import os
import tempfile
import json
import io
import logging
from datetime import datetime
from difflib import SequenceMatcher
from dotenv import load_dotenv

load_dotenv()
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from PIL import Image

# ============================================================
# LOCAL AI ANALYSIS (fully offline, no internet needed)
# ============================================================

try:
    from modules.ai import ask_ai
    AI_AVAILABLE = True
    AI_ERROR = ""
except Exception as e:
    AI_AVAILABLE = False
    AI_ERROR = str(e)


# ============================================================
# EMAIL SERVICE (SendGrid)
# ============================================================

try:
    from modules.email_service import send_otp_email, is_configured
    EMAIL_AVAILABLE = True
    EMAIL_ERROR = ""
except Exception as e:
    EMAIL_AVAILABLE = False
    EMAIL_ERROR = str(e)


# ============================================================
# SUPABASE DATABASE
# ============================================================

try:
    from modules.supabase_db import (
        is_configured as supabase_configured,
        create_user as sb_create_user,
        authenticate_user as sb_authenticate_user,
        change_password as sb_change_password,
        user_exists as sb_user_exists,
        get_user_name as sb_get_user_name,
        save_scan_history as sb_save_scan_history,
        get_scan_history as sb_get_scan_history,
    )
    SUPABASE_AVAILABLE = True
    SUPABASE_ERROR = ""
except Exception as e:
    SUPABASE_AVAILABLE = False
    SUPABASE_ERROR = str(e)


# ============================================================
# OPTIONAL PADDLEOCR
# ============================================================

try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
except Exception as e:
    PADDLE_AVAILABLE = False
    PADDLE_ERROR = str(e)
    logging.getLogger(__name__).warning("PaddleOCR unavailable: %s", e)

# RapidOCR = same PP-OCR reading models, much faster runtime (~1.5 sec/scan)
try:
    from rapidocr_onnxruntime import RapidOCR
    RAPID_AVAILABLE = True
    RAPID_ERROR = ""
except Exception as e:
    RAPID_AVAILABLE = False
    RAPID_ERROR = str(e)
    logging.getLogger(__name__).warning("RapidOCR unavailable: %s", e)

# Either engine is enough to scan
OCR_AVAILABLE = RAPID_AVAILABLE or PADDLE_AVAILABLE


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="NutriScan",
    page_icon="logo.png",
    layout="centered"
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_DIR = os.path.join(
    BASE_DIR,
    "database"
)

CSV_PATH = os.path.join(
    DATABASE_DIR,
    "ingredients.csv"
)

# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "page": "Home",
    "logged_in": False,
    "user": None,
    "otp": None,
    "reset_email": "",
    "otp_verified": False,
    "analysis_result": None,
    "ocr_text": "",
}

for key, value in DEFAULTS.items():

    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# STAY-LOGGED-IN (survives mobile page refreshes)
# ------------------------------------------------------------
# Mobile browsers sometimes fully reload the page while opening
# the photo picker, which normally creates a fresh session and
# logs the user out. A restore token carried in the URL lets any
# new session bring the login and the last scan straight back.
# ============================================================

# st.cache_resource keeps this dict alive across every rerun AND
# every browser session (a plain dict would be wiped each rerun).
@st.cache_resource
def _login_token_store():
    return {}


_LOGIN_TOKENS = _login_token_store()


def issue_login_token(user):
    """Create a server-side restore token for this user."""
    import secrets
    import time as _time

    token = secrets.token_urlsafe(24)
    _LOGIN_TOKENS[token] = {
        "user": user,
        "ts": _time.time(),
        "snapshot": {},
    }

    # Keep the store small (oldest 50 removed if it grows past 100)
    if len(_LOGIN_TOKENS) > 100:
        oldest = sorted(
            _LOGIN_TOKENS, key=lambda k: _LOGIN_TOKENS[k]["ts"]
        )[:50]
        for old in oldest:
            _LOGIN_TOKENS.pop(old, None)

    return token


def drop_login_token(token):
    """Forget a restore token (called on logout)."""
    if token:
        _LOGIN_TOKENS.pop(token, None)
    try:
        if "auto_login" in st.query_params:
            del st.query_params["auto_login"]
    except Exception:
        pass


# Restore login + last screen after a page reload
try:
    _restore_token = st.query_params.get("auto_login", "")
    if _restore_token and not st.session_state.get("logged_in"):
        _record = _LOGIN_TOKENS.get(_restore_token)
        if _record:
            st.session_state.logged_in = True
            st.session_state.user = _record["user"]
            st.session_state.login_token = _restore_token

            _snap = _record.get("snapshot") or {}
            st.session_state.page = _snap.get("page", "Scan")
            if _snap.get("analysis_result"):
                st.session_state.analysis_result = _snap["analysis_result"]
                st.session_state.ocr_text = _snap["analysis_result"].get(
                    "ocr_text", ""
                )
            if _snap.get("nutribot_messages") is not None:
                st.session_state.nutribot_messages = _snap[
                    "nutribot_messages"
                ]
            if _snap.get("smart_swap_product_name"):
                st.session_state.smart_swap_product_name = _snap[
                    "smart_swap_product_name"
                ]
except Exception:
    pass


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Main title - Clean white */
    .main-title {
        text-align: center;
        font-family: 'Inter', sans-serif;
        font-size: 48px;
        font-weight: 700;
        margin-bottom: 5px;
        color: #ffffff;
    }

    /* Subtitle */
    .subtitle {
        text-align: center;
        font-family: 'Inter', sans-serif;
        font-size: 18px;
        font-weight: 300;
        color: #a0a0a0;
        margin-bottom: 25px;
    }

    /* Main container - Pure black */
    .stApp {
        background: #000000;
        min-height: 100vh;
    }

    /* Sidebar - Pure black */
    .stSidebar {
        background: #000000;
        border-right: 1px solid #222222;
    }

    /* Cards - Pure black */
    .stCard, .stContainer {
        background: #000000;
        border: 1px solid #222222;
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
    }

    /* Buttons - Dark with white text */
    .stButton > button {
        background: #1a1a1a;
        color: #ffffff;
        border: 1px solid #333333;
        border-radius: 8px;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        background: #2a2a2a;
        border-color: #555555;
    }

    /* Input fields - Pure black */
    .stTextInput > div > input {
        background: #000000;
        border: 1px solid #333333;
        border-radius: 8px;
        color: #ffffff;
        font-family: 'Inter', sans-serif;
    }

    /* Selectbox - Pure black */
    .stSelectbox > div > div {
        background: #000000;
        border: 1px solid #333333;
        border-radius: 8px;
        color: #ffffff;
    }

    /* Expander - Pure black */
    .stExpander {
        border: 1px solid #222222;
        border-radius: 8px;
        background: #000000;
    }

    /* Metrics - Pure black */
    .stMetric {
        background: #000000;
        border-radius: 8px;
        padding: 15px;
        border: 1px solid #222222;
    }

    .stMetric label {
        color: #a0a0a0;
        font-family: 'Inter', sans-serif;
        font-weight: 500;
    }

    .stMetric .css-1fv8s86 {
        color: #ffffff;
        font-size: 24px;
        font-weight: 700;
    }

    /* Alerts */
    .stAlert {
        border-radius: 8px;
        border: 1px solid;
        font-family: 'Inter', sans-serif;
    }

    /* Tables */
    .stTable {
        border: 1px solid #333333;
        border-radius: 8px;
    }

    /* Divider */
    hr {
        border: none;
        height: 1px;
        background: #333333;
        margin: 20px 0;
    }

    /* Chat messages */
    .stChatMessage {
        background: #1a1a1a;
        border: 1px solid #333333;
        border-radius: 8px;
    }

    /* File uploader */
    .stFileUploader {
        background: #1a1a1a;
        border: 1px dashed #444444;
        border-radius: 8px;
    }

    /* Progress bar */
    .stProgress > div > div {
        background: #ffffff;
    }

    /* Radio buttons */
    .stRadio > label > div {
        color: #ffffff;
    }

    /* Checkbox */
    .stCheckbox > label > div {
        color: #ffffff;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background: #1a1a1a;
        color: #a0a0a0;
        border-radius: 8px 8px 0 0;
        border: 1px solid #333333;
    }

    .stTabs [aria-selected="true"] {
        background: #ffffff;
        color: #0a0a0a;
    }

    /* Number input */
    .stNumberInput > div > input {
        background: #1a1a1a;
        border: 1px solid #444444;
        border-radius: 8px;
        color: #ffffff;
    }

    /* Time input */
    .stTimeInput > div > input {
        background: #1a1a1a;
        border: 1px solid #444444;
        border-radius: 8px;
        color: #ffffff;
    }

    /* Multiselect */
    .stMultiSelect > div > div {
        background: #1a1a1a;
        border: 1px solid #444444;
        border-radius: 8px;
        color: #ffffff;
    }

    /* Text area */
    .stTextArea > div > textarea {
        background: #1a1a1a;
        border: 1px solid #444444;
        border-radius: 8px;
        color: #ffffff;
    }

    /* Download button */
    .stDownloadButton > button {
        background: #ffffff;
        color: #0a0a0a;
        border: none;
        border-radius: 8px;
        font-weight: 600;
    }

    /* Status */
    .stStatus {
        background: #1a1a1a;
        border: 1px solid #333333;
        border-radius: 8px;
    }

    /* Spinner text */
    .stSpinner > div {
        border-color: #ffffff transparent transparent transparent;
    }

    /* ---------- MOBILE / SMALL SCREENS ---------- */
    @media (max-width: 768px) {
        .main-title {
            font-size: 30px;
        }

        .subtitle {
            font-size: 14px;
        }

        .grade-box {
            padding: 14px 8px !important;
        }

        .grade-num {
            font-size: 36px !important;
        }

        .stButton > button {
            width: 100%;
            padding: 12px;
        }

        /* prevent horizontal scrolling */
        .stApp {
            overflow-x: hidden;
        }
    }

    /* Text color overrides */
    .stMarkdown, .stText, .stCaption {
        color: #e0e0e0;
    }

    /* Label color */
    .stLabel {
        color: #a0a0a0;
    }

    /* Success/Info/Warning/Error text */
    .stSuccess, .stInfo, .stWarning, .stError {
        color: #e0e0e0;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    """Legacy SQLite function - kept for compatibility. Not used with Supabase."""
    pass


def save_scan_history(user_email, image_name, image_data, ocr_text, matched, keyword_matches, ai_result):
    return sb_save_scan_history(user_email, image_name, image_data, ocr_text, matched, keyword_matches, ai_result)


def get_scan_history(user_email):
    return sb_get_scan_history(user_email)


def make_scan_pdf(scan, user_name, user_email, nutribot_messages=None):
    scan_id, scan_time, image_name, image_data, ocr_text, matched_json, keyword_json, ai_result = scan
    matched = json.loads(matched_json or "[]")
    keywords = json.loads(keyword_json or "[]")
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("NutriTitle", parent=styles["Title"], alignment=TA_CENTER, fontSize=20, spaceAfter=12)
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8, leading=10)
    story = [
        Paragraph("NutriScan Food Analysis Report", title),
        Paragraph(f"<b>User:</b> {user_name}", styles["BodyText"]),
        Paragraph(f"<b>Email:</b> {user_email}", styles["BodyText"]),
        Paragraph(f"<b>Scan date &amp; time:</b> {scan_time}", styles["BodyText"]),
        Paragraph(f"<b>Image:</b> {image_name or 'Food image'}", styles["BodyText"]),
        Spacer(1, 12)
    ]
    if image_data:
        try:
            story.extend([RLImage(io.BytesIO(image_data), width=240, height=180, kind="proportional"), Spacer(1, 12)])
        except Exception:
            pass
    story.append(Paragraph("Detected Ingredients", styles["Heading2"]))
    if matched:
        data = [["Ingredient", "Category", "Match %"]]
        for item in matched:
            data.append([str(item.get("ingredient", item.get("ingredient_name", ""))), str(item.get("category", "")), str(item.get("match_score", ""))])
        table = Table(data, repeatRows=1, colWidths=[220, 150, 70])
        table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.lightgrey), ("GRID", (0,0), (-1,-1), 0.5, colors.grey), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 8), ("VALIGN", (0,0), (-1,-1), "TOP")]))
        story.extend([table, Spacer(1, 12)])
    else:
        story.append(Paragraph("No ingredients were confidently matched.", styles["BodyText"]))
    if keywords:
        story.append(Paragraph("High-concern screening matches", styles["Heading2"]))
        for item in keywords:
            story.append(Paragraph("• " + str(item), styles["BodyText"]))
    story.append(Paragraph("AI Ingredient Analysis", styles["Heading2"]))
    safe_ai = (ai_result or "No AI analysis available.").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
    story.append(Paragraph(safe_ai, small))

    # ----------------------------------------------------
    # NUTRIBOT CONVERSATION (this session's chat, if any)
    # ----------------------------------------------------
    chat = [m for m in (nutribot_messages or []) if str(m.get("content", "")).strip()]
    if chat:
        story.append(Paragraph("NutriBot Health Assistant - Conversation", styles["Heading2"]))
        for m in chat:
            raw = str(m.get("content", ""))
            safe_msg = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
            if m.get("role") == "user":
                story.append(Paragraph(f"<b>You:</b> {safe_msg}", styles["BodyText"]))
            else:
                story.append(Paragraph(f"<b>NutriBot:</b> {safe_msg}", small))
            story.append(Spacer(1, 6))

    story.append(Paragraph("OCR Text", styles["Heading2"]))
    safe_ocr = (ocr_text or "No OCR text available.").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
    story.append(Paragraph(safe_ocr, small))
    doc.build(story)
    return buffer.getvalue()


# ============================================================
# PASSWORD HASH
# ============================================================

def hash_password(password):

    salt = secrets.token_hex(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000
    ).hex()

    return salt + ":" + password_hash


def verify_password(password, stored):

    try:

        salt, original_hash = stored.split(":")

        new_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000
        ).hex()

        return secrets.compare_digest(
            new_hash,
            original_hash
        )

    except Exception:

        return False


# ============================================================
# SIGNUP
# ============================================================

def create_user(name, email, password):
    return sb_create_user(name, email, hash_password(password))


# ============================================================
# LOGIN
# ============================================================

def authenticate_user(email, password):
    return sb_authenticate_user(email, password, verify_password)


# ============================================================
# RESET PASSWORD
# ============================================================

def change_password(email, new_password):
    return sb_change_password(email, hash_password(new_password))


# ============================================================
# LOAD INGREDIENT CSV
# ============================================================

@st.cache_data
def load_ingredients():

    if not os.path.exists(CSV_PATH):

        return None

    try:

        df = pd.read_csv(
            CSV_PATH,
            encoding="utf-8-sig"
        )

    except UnicodeDecodeError:

        df = pd.read_csv(
            CSV_PATH,
            encoding="latin-1"
        )

    df.columns = [
        str(column).strip().lower()
        for column in df.columns
    ]

    required = {
        "ingredient",
        "aliases",
        "category"
    }

    missing = required - set(df.columns)

    if missing:

        raise ValueError(
            "CSV is missing columns: "
            + ", ".join(missing)
        )

    df = df.fillna("")

    return df


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(text):

    text = str(text).lower()

    text = text.replace(
        "\n",
        " "
    )

    text = re.sub(
        r"[^a-z0-9\s\-]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# SPLIT ALIASES
# ============================================================

def get_aliases(value):

    if not value:
        return []

    parts = re.split(
        r"[,;|/]",
        str(value)
    )

    return [
        normalize_text(x)
        for x in parts
        if normalize_text(x)
    ]


# ============================================================
# PADDLE OCR
# ============================================================

_OCR_INSTANCE = None


@st.cache_resource
def get_ocr():
    """Get or create singleton PaddleOCR instance for faster repeated scans."""

    global _OCR_INSTANCE

    if not PADDLE_AVAILABLE:

        raise RuntimeError(
            "PaddleOCR could not be imported:\n"
            + PADDLE_ERROR
        )

    if _OCR_INSTANCE is not None:
        return _OCR_INSTANCE

    import logging
    logging.getLogger("paddleocr").setLevel(logging.ERROR)
    logging.getLogger("ppocr").setLevel(logging.ERROR)

    # PaddleOCR 3.x API - optimized for speed, oneDNN disabled for compatibility
    _OCR_INSTANCE = PaddleOCR(
        lang="en",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False,
        device="cpu",
    )

    return _OCR_INSTANCE


_RAPID_INSTANCE = None


@st.cache_resource
def get_rapid_ocr():
    """Fast OCR engine (ONNX Runtime) - primary scanner, ~1.5 sec per image."""
    global _RAPID_INSTANCE

    if not RAPID_AVAILABLE:
        raise RuntimeError(
            "RapidOCR could not be imported:\n" + RAPID_ERROR
        )

    if _RAPID_INSTANCE is not None:
        return _RAPID_INSTANCE

    import logging
    logging.getLogger("rapidocr").setLevel(logging.ERROR)

    _RAPID_INSTANCE = RapidOCR()
    return _RAPID_INSTANCE


def _warmup_ocr():
    """Load the OCR models in the background so the first scan is instant."""
    try:
        if RAPID_AVAILABLE:
            # Load engine AND run one tiny scan so all runtime
            # initialization happens now, not during the first user scan
            engine = get_rapid_ocr()
            try:
                import numpy as np
                engine(np.zeros((32, 200, 3), dtype=np.uint8))
            except Exception:
                pass
        elif PADDLE_AVAILABLE:
            get_ocr()
    except Exception:
        pass


# ============================================================
# EXTRACT TEXT FROM PADDLE RESULT
# ============================================================

def extract_text_from_result(result):

    texts = []

    def process_object(obj):

        if obj is None:
            return

        # ----------------------------------------------------
        # Dictionary
        # ----------------------------------------------------

        if isinstance(obj, dict):

            # Common PaddleOCR 3.x field
            if "rec_texts" in obj:

                value = obj["rec_texts"]

                if isinstance(value, (list, tuple)):

                    for item in value:

                        if item:

                            texts.append(
                                str(item)
                            )

                elif value:

                    texts.append(
                        str(value)
                    )

            # Nested result
            for key, value in obj.items():

                if key == "rec_texts":
                    continue

                if isinstance(
                    value,
                    (dict, list, tuple)
                ):

                    process_object(value)

            return

        # ----------------------------------------------------
        # List / Tuple
        # ----------------------------------------------------

        if isinstance(
            obj,
            (list, tuple)
        ):

            for item in obj:

                # Old style:
                # [box, (text, score)]

                if (
                    isinstance(item, (list, tuple))
                    and len(item) >= 2
                ):

                    possible_text = item[1]

                    if isinstance(
                        possible_text,
                        (list, tuple)
                    ) and possible_text:

                        first = possible_text[0]

                        if isinstance(
                            first,
                            str
                        ):

                            texts.append(first)
                            continue

                process_object(item)

            return

        # ----------------------------------------------------
        # Paddle result object
        # ----------------------------------------------------

        try:

            if hasattr(
                obj,
                "rec_texts"
            ):

                value = obj.rec_texts

                if value is not None:

                    if isinstance(
                        value,
                        (list, tuple)
                    ):

                        for item in value:

                            if item:

                                texts.append(
                                    str(item)
                                )

                    else:

                        texts.append(
                            str(value)
                        )

                    return

        except Exception:
            pass

        # ----------------------------------------------------
        # JSON property
        # ----------------------------------------------------

        try:

            if hasattr(
                obj,
                "json"
            ):

                json_value = obj.json

                if callable(json_value):

                    json_value = json_value()

                if isinstance(
                    json_value,
                    str
                ):

                    import json

                    json_value = json.loads(
                        json_value
                    )

                process_object(
                    json_value
                )

        except Exception:
            pass

    process_object(result)

    # Remove duplicates while preserving order
    final_text = []

    for text in texts:

        text = str(text).strip()

        if text and text not in final_text:

            final_text.append(text)

    return final_text


# ============================================================
# OCR IMAGE
# ============================================================

@st.cache_data(show_spinner=False, max_entries=32)
def _cached_ocr(image_bytes, suffix):
    """
    OCR a normalized image. Cached by image bytes so the same image is
    not processed repeatedly during Streamlit reruns.
    Primary: RapidOCR (fast, ~1.5 sec). Fallback: PaddleOCR.
    """
    temp_path = None

    try:
        # Phone photos can be several MB and thousands of pixels wide.
        # OCR is much faster when the image is resized before inference.
        image = Image.open(io.BytesIO(image_bytes))
        image = image.convert("L")

        # 900px keeps label text readable while staying fast
        max_side = 900
        width, height = image.size

        if max(width, height) > max_side:
            scale = max_side / float(max(width, height))
            new_size = (
                max(1, int(width * scale)),
                max(1, int(height * scale)),
            )
            image = image.resize(new_size, Image.Resampling.BILINEAR)

        optimized = io.BytesIO()
        image.save(optimized, format="JPEG", quality=80, optimize=True)
        optimized_bytes = optimized.getvalue()

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".jpg"
        ) as temp:
            temp.write(optimized_bytes)
            temp_path = temp.name

        # ------------------------------------------------
        # PRIMARY: RapidOCR (same PP-OCR models, ~1.5 sec)
        # ------------------------------------------------
        if RAPID_AVAILABLE:
            try:
                engine = get_rapid_ocr()
                result, _elapse = engine(temp_path)

                texts = []

                if result:
                    for item in result:
                        # item = [box, text, score]
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            txt = item[1]
                            if txt:
                                texts.append(str(txt).strip())

                # Deduplicate while preserving order
                final_texts = []
                for t in texts:
                    if t and t not in final_texts:
                        final_texts.append(t)

                if final_texts:
                    return final_texts, None

                # No text found - give PaddleOCR a second chance below

            except Exception:
                pass  # Fall through to PaddleOCR

        # ------------------------------------------------
        # FALLBACK: PaddleOCR (original engine)
        # ------------------------------------------------
        if PADDLE_AVAILABLE:
            ocr = get_ocr()
            result = ocr.predict(temp_path)
            texts = extract_text_from_result(result)
            return texts, None

        return [], "No OCR engine is available."

    except Exception as e:
        return [], str(e)

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def run_ocr(uploaded_file):
    """Fast OCR wrapper with fallback to faster method if PaddleOCR fails."""
    image_bytes = uploaded_file.getvalue()

    if not image_bytes:
        return [], "The uploaded image is empty."

    suffix = os.path.splitext(uploaded_file.name)[1].lower() or ".jpg"

    # Run OCR in a background thread with a hard timeout.
    # NOTE: no `with` block here on purpose - exiting a ThreadPoolExecutor
    # context waits for the running thread, which caused the old "stuck
    # forever" bug even after a timeout.
    import concurrent.futures

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_cached_ocr, image_bytes, suffix)

    try:
        # 45 second timeout (first scan may load the model, then ~1-2 sec)
        return future.result(timeout=45)
    except concurrent.futures.TimeoutError:
        return [], "OCR timed out. Please try again with a clearer image."
    except Exception as e:
        # Fallback to faster Tesseract OCR
        try:
            return _fast_tesseract_ocr(image_bytes)
        except Exception:
            return [], f"OCR error: {str(e)}"
    finally:
        # Never block waiting for a hung OCR thread
        executor.shutdown(wait=False)


def _fast_tesseract_ocr(image_bytes):
    """Fast fallback OCR using Tesseract (much faster than PaddleOCR)."""
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes))
        image = image.convert("L")

        # Resize for faster processing
        max_side = 800
        width, height = image.size
        if max(width, height) > max_side:
            scale = max_side / float(max(width, height))
            new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            image = image.resize(new_size, Image.Resampling.BILINEAR)

        text = pytesseract.image_to_string(image, lang='eng')
        texts = [t.strip() for t in text.split('\n') if t.strip()]
        return texts, None
    except ImportError:
        raise RuntimeError("Tesseract not available. Install with: pip install pytesseract")
    except Exception as e:
        raise RuntimeError(f"Tesseract OCR failed: {str(e)}")


# ============================================================
# HARMFUL / HIGH-CONCERN KEYWORDS
#
# These are screening keywords, NOT a medical diagnosis.
# The CSV remains the main ingredient database.
# ============================================================

HIGH_CONCERN_KEYWORDS = {

    "trans fat": "Trans fat",
    "partially hydrogenated": "Partially hydrogenated oil",
    "hydrogenated oil": "Hydrogenated oil",

    "sodium nitrite": "Sodium nitrite",
    "sodium nitrate": "Sodium nitrate",

    "potassium bromate": "Potassium bromate",

    "azodicarbonamide": "Azodicarbonamide",

    "bht": "BHT",
    "bha": "BHA",

    "tbhq": "TBHQ",

    "propyl gallate": "Propyl gallate",

    "tartrazine": "Tartrazine",

    "sunset yellow": "Sunset Yellow",
    "yellow 5": "Yellow 5",

    "allura red": "Allura Red",
    "red 40": "Red 40",

    "brilliant blue": "Brilliant Blue",
    "blue 1": "Blue 1",

    "monosodium glutamate": "Monosodium glutamate",
    "msg": "MSG",

    "high fructose corn syrup": "High-fructose corn syrup",

    "acesulfame potassium": "Acesulfame potassium",
    "acesulfame k": "Acesulfame potassium",

    "saccharin": "Saccharin",

    "sucralose": "Sucralose",

    "aspartame": "Aspartame",

    "sodium benzoate": "Sodium benzoate",

    "potassium sorbate": "Potassium sorbate",

    "sulfur dioxide": "Sulfur dioxide",
    "sulphur dioxide": "Sulfur dioxide",

    "sodium metabisulfite": "Sodium metabisulfite",

    "carrageenan": "Carrageenan",

    "sodium acid pyrophosphate":
        "Sodium acid pyrophosphate",

    "disodium inosinate":
        "Disodium inosinate",

    "disodium guanylate":
        "Disodium guanylate",
}


# ============================================================
# CATEGORY SCREENING
# ============================================================

def category_level(category):

    value = normalize_text(category)

    high_words = [
        "trans",
        "hydrogenated",
        "nitrite",
        "nitrate",
        "bromate",
        "preservative"
    ]

    caution_words = [
        "sweetener",
        "artificial",
        "colour",
        "color",
        "flavour",
        "flavor",
        "additive",
        "oil",
        "fat",
        "sugar",
        "salt",
        "preservative"
    ]

    for word in high_words:

        if word in value:

            return "high"

    for word in caution_words:

        if word in value:

            return "caution"

    return "info"


# ============================================================
# MATCH INGREDIENTS AGAINST CSV
# ============================================================

@st.cache_data(show_spinner=False)
def _prepare_ingredient_index(dataframe):
    """
    Prepare normalized ingredient/alias candidates once.
    This avoids rebuilding aliases for every scan.
    """
    index = []

    for _, row in dataframe.iterrows():
        ingredient = str(row["ingredient"]).strip()

        if not ingredient:
            continue

        category = str(row["category"]).strip()
        aliases = get_aliases(row["aliases"])

        candidates = [normalize_text(ingredient)] + aliases
        candidates = list(dict.fromkeys(x for x in candidates if x))

        index.append(
            {
                "ingredient": ingredient,
                "aliases": row["aliases"],
                "category": category,
                "candidates": candidates,
            }
        )

    return index


def _fuzzy_similarity(a, b):
    """Fast similarity helper using rapidfuzz (C++ backed)."""
    from rapidfuzz import fuzz
    return fuzz.ratio(a, b)


def match_ingredients(ocr_text, dataframe):
    """
    Match OCR text against the ingredient database.

    Exact substring matching is done first. Fuzzy matching uses rapidfuzz
    (C++ backed, 10-100x faster than SequenceMatcher) and is limited to
    plausible OCR tokens/windows.
    """
    normalized_ocr = normalize_text(ocr_text)

    if not normalized_ocr:
        return []

    words = normalized_ocr.split()

    # Build comparison pieces: single words + multi-word windows
    comparison_pieces = list(dict.fromkeys(words))

    max_window = 4
    for window_size in range(2, max_window + 1):
        if len(words) >= window_size:
            comparison_pieces.extend(
                " ".join(words[i:i + window_size])
                for i in range(len(words) - window_size + 1)
            )

    comparison_pieces = list(dict.fromkeys(comparison_pieces))

    # Pre-filter: only keep pieces with length >= 3 for fuzzy matching
    fuzzy_pieces = [p for p in comparison_pieces if len(p) > 3]

    index = _prepare_ingredient_index(dataframe)
    results = []

    for item in index:
        best_score = 0
        matched_text = ""

        # Exact match: very fast.
        for candidate in item["candidates"]:
            if candidate in normalized_ocr:
                best_score = 100
                matched_text = candidate
                break

        # Fuzzy matching only when exact matching failed.
        if best_score < 100:
            for candidate in item["candidates"]:
                if len(candidate) <= 3:
                    continue

                candidate_words = candidate.split()

                if len(candidate_words) > 1:
                    pieces = [
                        piece
                        for piece in fuzzy_pieces
                        if len(piece.split()) == len(candidate_words)
                    ]
                else:
                    pieces = [
                        piece
                        for piece in fuzzy_pieces
                        if len(piece.split()) == 1
                    ]

                for piece in pieces:
                    length_ratio = min(len(candidate), len(piece)) / max(
                        len(candidate), len(piece)
                    )

                    if length_ratio < 0.55:
                        continue

                    score = _fuzzy_similarity(candidate, piece)

                    if score > best_score:
                        best_score = score
                        matched_text = piece

        if best_score >= 82:
            results.append(
                {
                    "ingredient": item["ingredient"],
                    "aliases": item["aliases"],
                    "category": item["category"],
                    "match_score": round(best_score, 1),
                    "matched_text": matched_text,
                }
            )

    # Remove duplicates.
    unique = {}

    for item in results:
        key = normalize_text(item["ingredient"])

        if (
            key not in unique
            or item["match_score"] > unique[key]["match_score"]
        ):
            unique[key] = item

    return list(unique.values())


# ============================================================
# DIRECT HIGH-CONCERN SEARCH
# ============================================================

def find_high_concern_keywords(
    ocr_text
):

    normalized = normalize_text(
        ocr_text
    )

    found = []

    for keyword, display_name in (
        HIGH_CONCERN_KEYWORDS.items()
    ):

        if keyword in normalized:

            found.append(
                display_name
            )

    return found


# ============================================================
# ANALYZE RISK
# ============================================================

def analyze_risk(
    matched,
    keyword_matches
):

    high = []
    caution = []

    for item in matched:

        level = category_level(
            item["category"]
        )

        if level == "high":

            high.append(
                item["ingredient"]
            )

        elif level == "caution":

            caution.append(
                item["ingredient"]
            )

    for item in keyword_matches:

        if item not in high:

            high.append(item)

    if high:

        return "HIGH CONCERN", high, caution

    if caution:

        return "CAUTION", high, caution

    return "NO FLAG FOUND", high, caution


# ============================================================
# DISPLAY RESULTS
# ============================================================

def calculate_grade(matched, keyword_matches):
    """Calculate a health grade (A, B, C, D, E) based on matched ingredients."""
    high_count = 0
    caution_count = 0

    for item in matched:
        level = category_level(item["category"])
        if level == "high":
            high_count += 1
        elif level == "caution":
            caution_count += 1

    high_count += len(keyword_matches)
    total_flagged = high_count + caution_count

    if high_count >= 3:
        return "E", "Critical - Multiple high-concern ingredients detected", "#ff0000"
    elif high_count >= 2:
        return "D", "Poor - Two high-concern ingredients detected", "#ff6600"
    elif high_count >= 1:
        return "C", "Fair - One high-concern ingredient detected", "#ffcc00"
    elif caution_count >= 3:
        return "B", "Good - Some caution ingredients detected", "#99cc00"
    elif caution_count >= 1:
        return "A-", "Very Good - Minor concerns only", "#66cc00"
    else:
        return "A", "Excellent - No concerning ingredients found", "#00cc00"


def display_analysis(
    ocr_text,
    matched,
    keyword_matches
):

    status, high, caution = analyze_risk(
        matched,
        keyword_matches
    )

    grade, grade_desc, grade_color = calculate_grade(matched, keyword_matches)

    st.divider()

    # Grade display
    st.markdown(
        f"""
        <div class="grade-box" style="padding: 20px; border-radius: 15px; text-align: center; background-color: {grade_color}22; border: 3px solid {grade_color};">
            <div class="grade-num" style="font-size: 48px; font-weight: bold; color: {grade_color};">{grade}</div>
            <div style="font-size: 16px; color: {grade_color};">{grade_desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader(
        "📊 NutriScan Result"
    )

    if status == "HIGH CONCERN":

        st.error(
            "🔴 HIGH CONCERN INGREDIENTS DETECTED"
        )

        st.write(
            "Potentially concerning ingredients "
            "were identified in the scanned text."
        )

        for item in high:

            st.write(
                "🔴 **" + item + "**"
            )

    elif status == "CAUTION":

        st.warning(
            "🟠 INGREDIENTS REQUIRING CAUTION"
        )

        for item in caution:

            st.write(
                "🟠 **" + item + "**"
            )

    else:

        st.success(
            "🟢 NO FLAGGED INGREDIENTS FOUND"
        )

        st.write(
            "No ingredients in the current screening "
            "database were confidently identified."
        )

    # --------------------------------------------------------
    # DATABASE MATCHES
    # --------------------------------------------------------

    if matched:

        st.subheader(
            "🧾 Matched Ingredients"
        )

        for item in matched:

            with st.expander(
                item.get("ingredient", "Unknown")
            ):

                st.write(
                    "**Category:**",
                    item.get("category", "N/A")
                )

                st.write(
                    "**Aliases:**",
                    item.get("aliases") or "None"
                )

                st.write(
                    "**Match score:**",
                    str(
                        item.get("match_score", 0)
                    ) + "%"
                )

                st.write(
                    "**OCR match:**",
                    item.get("matched_text", "")
                )

    # --------------------------------------------------------
    # DIRECT KEYWORD MATCHES
    # --------------------------------------------------------

    if keyword_matches:

        st.subheader(
            "⚠️ High-concern screening matches"
        )

        for item in keyword_matches:

            st.write(
                "🔴 " + item
            )

    # --------------------------------------------------------
    # OCR TEXT
    # --------------------------------------------------------

    with st.expander(
        "📄 View complete OCR text"
    ):

        st.text(
            ocr_text
        )

    # --------------------------------------------------------
    # PRODUCT-SPECIFIC HEALTHY ALTERNATIVES
    # --------------------------------------------------------
    st.divider()
    st.subheader(" Product-Specific Healthy Alternatives")
    st.caption("Enter a product name to see targeted healthy alternatives")

    product_input = st.text_input(
        "Enter product name (e.g., chips, biscuit, noodles, soft drink)",
        key="product_alt_input",
        placeholder="e.g., chips, biscuit, noodles, soft drink"
    )

    if product_input.strip():
        product_name = product_input.strip().lower()
        alternatives = get_product_specific_alternatives(product_name)

        if alternatives:
            st.markdown(f"**Alternatives for: {product_name.title()}**")
            for name, group, reason in alternatives:
                with st.container(border=True):
                    st.markdown(f"**{name}**")
                    st.caption(f"Category: {group}")
                    st.write(reason)
        else:
            st.info(f"No specific alternatives found for '{product_name}'. Try: chips, biscuit, noodles, soft drink, chocolate, cake, juice, etc.")
    else:
        st.info("Enter a product name above to see specific healthy alternatives.")


# ============================================================
# NUTRISCAN SMART FOOD SWAP — COMPREHENSIVE ALTERNATIVES
# ============================================================


# ============================================================
# PRODUCT-SPECIFIC ALTERNATIVES
# ============================================================

PRODUCT_SPECIFIC_ALTERNATIVES = {
    "chips": [
        ("Ragi (finger millet) chips", "Millets", "Homemade ragi chips are rich in fiber, calcium, and iron. Baked ragi chips with minimal salt are a great alternative to potato chips."),
        ("Roasted makhana (fox nuts)", "Whole foods", "Makhana is low in fat and high in protein. Roasted with a pinch of rock salt, it's a perfect crunchy snack."),
        ("Roasted chana (chickpeas)", "Pulses", "Roasted chickpeas are high in plant protein and fiber. They keep you full longer than chips."),
        ("Vegetable chips (beetroot, carrot, sweet potato)", "Vegetables", "Homemade vegetable chips retain nutrients and fiber that potato chips lack. Bake instead of fry."),
        ("Puffed rice (muri) with peanuts", "Whole grains", "Light, low-calorie puffed rice mix with roasted peanuts and mild spices is a traditional Indian snack."),
        ("Jowar (sorghum) puffs", "Millets", "Jowar puffs are gluten-free and rich in fiber. Much lighter than fried chips."),
    ],
    "biscuit": [
        ("Ragi biscuits", "Millets", "Ragi biscuits are calcium-rich and fiber-dense. Look for low-sugar versions or make at home."),
        ("Oats biscuits", "Whole grains", "Oats biscuits provide soluble fiber (beta-glucan) which helps with satiety and digestion."),
        ("Whole wheat (atta) biscuits", "Whole grains", "Whole wheat biscuits retain the bran and germ, providing more fiber than refined flour biscuits."),
        ("Homemade ragi cookies", "Millets", "Made with ragi flour, jaggery, and ghee — a wholesome alternative to commercial biscuits."),
        ("Makhana cookies", "Whole foods", "Cookies made with makhana flour are light, nutritious, and naturally gluten-free."),
    ],
    "noodles": [
        ("Millet noodles (ragi/jowar)", "Millets", "Ragi or jowar noodles are rich in fiber, calcium, and iron. Cook with vegetables for a complete meal."),
        ("Whole wheat noodles", "Whole grains", "Whole wheat noodles have more fiber and nutrients than refined flour noodles."),
        ("Vegetable-based noodles (zucchini, carrot)", "Vegetables", "Zucchini or carrot noodles (zoodles) are low-carb, nutrient-dense alternatives."),
        ("Homemade vegetable upma", "Whole grains", "Upma made with rava or broken wheat, loaded with vegetables, is a wholesome meal."),
        ("Millet khichdi with vegetables", "Millets & Pulses", "Khichdi made with moong dal and ragi or jowar, with mixed vegetables — a complete, balanced meal."),
    ],
    "soft drink": [
        ("Fresh coconut water", "Natural hydration", "Coconut water is nature's electrolyte drink — hydrating, low in sugar, and rich in potassium."),
        ("Homemade lemonade (nimbu pani)", "Fruits", "Fresh lemon water with a pinch of salt and jaggery is refreshing and provides vitamin C."),
        ("Buttermilk (chaas)", "Dairy", "Spiced buttermilk aids digestion, provides probiotics, and is naturally low in sugar."),
        ("Fresh fruit juice (no added sugar)", "Fruits", "Freshly squeezed fruit juice retains vitamins and fiber. Dilute with water for less sugar."),
        ("Herbal tea (hot or iced)", "Natural beverages", "Unsweetened herbal teas like chamomile, peppermint, or hibiscus are antioxidant-rich."),
    ],
    "chocolate": [
        ("Dark chocolate (70%+ cocoa)", "Better sweets", "Dark chocolate with high cocoa content has less sugar and more antioxidants. Choose minimally processed."),
        ("Dates and nuts roll", "Fruits & Nuts", "Homemade dates rolls with nuts and seeds provide natural sweetness with fiber, protein, and healthy fats."),
        ("Fruit and nut energy balls", "Fruits & Nuts", "Blended dates, oats, nuts, and seeds — no added sugar, packed with nutrients."),
        ("Homemade ragi laddu", "Millets", "Ragi flour, ghee, jaggery, and nuts — a nutrient-dense traditional sweet."),
    ],
    "cake": [
        ("Ragi cake", "Millets", "Cakes made with ragi flour are calcium-rich and have a lower glycemic index than maida cakes."),
        ("Whole wheat cake", "Whole grains", "Whole wheat cakes retain fiber and B vitamins lost in refined flour."),
        ("Homemade ghee-based cake", "Ghee", "Cakes made with pure ghee instead of vanaspati or margarine are healthier and more flavorful."),
        ("Steamed dhokla (besan)", "Vegetarian", "Steamed dhokla made from chickpea flour is high in protein and low in fat."),
    ],
    "juice": [
        ("Fresh whole fruit", "Fruits", "Whole fruit retains more intact fiber than juice or fruit drinks."),
        ("Coconut water", "Natural hydration", "Coconut water is nature's electrolyte drink — hydrating and low in sugar."),
        ("Vegetable juice (carrot, beetroot)", "Vegetables", "Fresh vegetable juice without added sugar provides vitamins and minerals."),
        ("Buttermilk (chaas)", "Dairy", "Spiced buttermilk aids digestion and is naturally low in sugar."),
    ],
    "bread": [
        ("Whole wheat (atta) bread", "Whole grains", "100% whole wheat bread retains fiber, B vitamins, and minerals. Avoid bread with added sugar."),
        ("Millet roti (ragi/jowar/bajra)", "Millets", "Fresh millet rotis are gluten-free, fiber-rich, and have a lower glycemic index than bread."),
        ("Multigrain bread (no maida)", "Whole grains", "Multigrain bread with visible seeds and grains provides more fiber and nutrients."),
        ("Homemade ragi dosa", "Millets", "Ragi dosa is fermented (better gut health) and rich in calcium and iron."),
    ],
    "sugar": [
        ("Jaggery (gur)", "Natural sweetener", "Jaggery retains iron, potassium, and magnesium lost in refined sugar. Use in moderation."),
        ("Dates (khajur)", "Fruits", "Dates provide natural sweetness along with fiber, potassium, and iron."),
        ("Organic honey", "Natural sweetener", "Raw honey contains antioxidants and enzymes. Avoid for infants under 1 year."),
        ("Stevia (natural, zero-calorie)", "Natural sweetener", "Stevia is a zero-calorie, plant-based sweetener that doesn't raise blood sugar."),
    ],
    "ketchup": [
        ("Homemade tomato chutney", "Vegetables", "Fresh tomato chutney with garlic, ginger, and spices — no added sugar or preservatives."),
        ("Tamarind chutney (imli)", "Traditional", "Tamarind chutney with jaggery and spices is tangy, flavorful, and preservative-free."),
        ("Coconut chutney", "Vegetarian", "Coconut chutney with green chili, ginger, and curry leaves — a South Indian classic."),
        ("Mint-coriander chutney", "Herbs", "Fresh mint, coriander, green chili, and lemon — packed with chlorophyll and vitamin C."),
    ],
    "ice cream": [
        ("Homemade kulfi with nuts", "Dairy", "Traditional kulfi is denser and uses full milk with nuts — no artificial emulsifiers."),
        ("Fresh fruit sorbet", "Fruits", "Blended frozen fruits (mango, berry) without added sugar — refreshing and vitamin-rich."),
        ("Yogurt-based frozen dessert", "Dairy", "Frozen Greek yogurt with honey and fruits — probiotic and protein-rich."),
        ("Coconut milk ice cream", "Plant-based", "Coconut milk-based ice cream is dairy-free and rich in healthy fats."),
    ],
    "corn flakes": [
        ("Ragi porridge", "Millets", "Ragi porridge is calcium-rich and keeps you full much longer than corn flakes."),
        ("Oats with milk and fruits", "Whole grains", "Oats provide soluble fiber (beta-glucan) and sustained energy."),
        ("Vegetable poha", "Whole grains", "Poha with vegetables, peanuts, and curry leaves is a wholesome Indian breakfast."),
        ("Homemade muesli (no added sugar)", "Whole grains & Nuts", "Muesli with rolled oats, nuts, seeds, and dried fruits — high in fiber."),
        ("Upma with vegetables", "Whole grains & Vegetables", "Rava upma with mixed vegetables is savory, filling, and nutritious."),
    ],
    "milk": [
        ("Desi cow A2 milk", "Dairy", "A2 milk from indigenous cows is easier to digest and richer in omega-3 fatty acids."),
        ("Homemade turmeric milk (haldi doodh)", "Traditional", "Warm milk with turmeric, black pepper, and a touch of ghee is anti-inflammatory and immunity-boosting."),
        ("Buttermilk (chaas)", "Dairy", "Buttermilk is probiotic-rich, aids digestion, and is lighter than whole milk."),
        ("Ragi porridge (with milk)", "Millets", "Ragi porridge with milk is calcium-rich and a complete meal — great for all ages."),
    ],
    "rice": [
        ("Brown rice", "Whole grains", "Brown rice retains the bran layer, providing more fiber, magnesium, and B vitamins than white rice."),
        ("Hand-pounded red rice", "Traditional grains", "Red rice is rich in antioxidants and fiber. A traditional South Indian choice."),
        ("Millet rice (ragi, jowar, bajra)", "Millets", "Cooked millets are gluten-free, high in fiber, and have a lower glycemic index."),
        ("Quinoa", "Pseudocereals", "Quinoa is a complete protein with all essential amino acids. Light and easy to digest."),
    ],
    "oil": [
        ("Cold-pressed mustard oil", "Traditional oils", "Traditional oil with good omega-3 to omega-6 ratio. Ideal for Indian cooking."),
        ("Cold-pressed coconut oil", "Traditional oils", "Rich in MCTs, good for South Indian cooking and baking."),
        ("Cow ghee (in moderation)", "Traditional fats", "Ghee has a high smoke point and is rich in vitamins A, D, E, K. Use sparingly."),
        ("Cold-pressed sesame (til) oil", "Traditional oils", "Sesame oil is rich in antioxidants and has a nutty flavor."),
    ],
    "paneer": [
        ("Homemade paneer from cow milk", "Dairy", "Homemade paneer is free from preservatives and has superior taste and texture."),
        ("Tofu (soy paneer)", "Vegetarian protein", "Tofu is a complete protein, lower in fat than paneer, and rich in calcium."),
        ("Chana (chickpea) curry", "Pulses", "Chickpea curry is high in plant protein and fiber — a hearty alternative to paneer dishes."),
    ],
    "jam": [
        ("Fresh fruit chutney", "Fruits", "Homemade chutney with minimal jaggery and spices — no preservatives or artificial colors."),
        ("Mashed banana with ghee", "Fruits", "Ripe banana mashed with a teaspoon of ghee is a natural, nutrient-dense spread."),
        ("Dates and nut butter", "Fruits & Nuts", "Blended dates with almond or peanut butter — no added sugar, rich in fiber and protein."),
        ("Homemade apple sauce", "Fruits", "Stewed apples with cinnamon — naturally sweet, no added sugar needed."),
    ],
    "pasta": [
        ("Whole wheat pasta", "Whole grains", "Whole wheat pasta has more fiber and nutrients than refined flour pasta."),
        ("Millet pasta (ragi/jowar)", "Millets", "Millet-based pasta is rich in fiber, calcium, and iron."),
        ("Vegetable pasta (zucchini)", "Vegetables", "Zucchini noodles (zoodles) are low-carb, nutrient-dense alternatives."),
        ("Chickpea pasta", "Pulses", "Chickpea pasta is high in plant protein and fiber — gluten-free option."),
    ],
    "sauce": [
        ("Homemade tomato sauce", "Vegetables", "Fresh tomato sauce with garlic and herbs — no added sugar or preservatives."),
        ("Pesto (basil, nuts)", "Herbs & Nuts", "Homemade pesto with basil, nuts, and olive oil — rich in healthy fats."),
        ("Coconut chutney", "Vegetarian", "Coconut chutney with green chili and curry leaves — South Indian classic."),
        ("Mint chutney", "Herbs", "Fresh mint, coriander, green chili, and lemon — packed with chlorophyll."),
    ],
    "yogurt": [
        ("Homemade curd (dahi)", "Dairy", "Homemade curd is probiotic-rich and free from added sugar or stabilizers."),
        ("Greek yogurt (unsweetened)", "Dairy", "Greek yogurt is higher in protein and lower in sugar than flavored yogurt."),
        ("Buttermilk (chaas)", "Dairy", "Buttermilk aids digestion, provides probiotics, and is naturally light."),
    ],
    "flour": [
        ("Whole wheat flour (atta)", "Whole grains", "Stone-ground atta retains more nutrients than roller-milled flour."),
        ("Ragi flour (finger millet)", "Millets", "Ragi flour is calcium-rich and gluten-free. Use for rotis, dosas, and porridge."),
        ("Jowar flour (sorghum)", "Millets", "Jowar is high in fiber and iron. Great for rotis and bhakris."),
        ("Bajra flour (pearl millet)", "Millets", "Bajra is warming in winter and rich in iron and fiber."),
    ],
    "salt": [
        ("Rock salt (sendha namak)", "Mineral", "Rock salt contains trace minerals and is less processed than table salt."),
        ("Pink Himalayan salt", "Mineral", "Pink salt contains trace minerals. Use in moderation like any salt."),
        ("Sea salt", "Mineral", "Sea salt is less processed than table salt. Use in moderation."),
    ],
    "honey": [
        ("Organic raw honey", "Natural sweetener", "Raw honey contains antioxidants and enzymes. Avoid for infants under 1 year."),
        ("Dates (khajur)", "Fruits", "Dates provide natural sweetness along with fiber, potassium, and iron."),
        ("Jaggery (gur)", "Natural sweetener", "Jaggery retains iron, potassium, and magnesium lost in refined sugar."),
    ],
    "butter": [
        ("Desi cow ghee", "Traditional fats", "Ghee has a high smoke point and is rich in vitamins A, D, E, K."),
        ("Cold-pressed coconut oil", "Traditional oils", "Coconut oil contains MCTs and is good for high-heat cooking."),
        ("Homemade white butter", "Dairy", "Homemade white butter is free from preservatives. Use in moderation."),
    ],
    "cereal": [
        ("Plain oats", "Whole grains", "Oats provide soluble fiber (beta-glucan) and sustained energy."),
        ("Ragi porridge", "Millets", "Ragi porridge is calcium-rich and keeps you full much longer."),
        ("Vegetable poha", "Whole grains", "Poha with vegetables, peanuts, and curry leaves is a wholesome breakfast."),
        ("Homemade muesli", "Whole grains & Nuts", "Muesli with rolled oats, nuts, seeds, and dried fruits — high in fiber."),
    ],
    "soup": [
        ("Homemade vegetable soup", "Vegetables", "Fresh vegetable soup with minimal salt — no MSG or preservatives."),
        ("Dal soup (moong)", "Pulses", "Moong dal soup is easy to digest, high in protein, and light on the stomach."),
        ("Ragi soup", "Millets", "Ragi soup is calcium-rich and a comforting, nutritious option."),
    ],
    "salad": [
        ("Sprouted moong salad", "Pulses", "Sprouting increases vitamin C and makes minerals more bioavailable."),
        ("Cucumber tomato salad", "Vegetables", "Fresh salad with cucumber, tomato, lemon, and mint — hydrating and light."),
        ("Chana salad", "Pulses", "Chickpea salad with onions, tomatoes, and spices — high in plant protein."),
    ],
    "pickle": [
        ("Homemade lemon pickle", "Fruits", "Homemade lemon pickle with minimal salt — no artificial colors or preservatives."),
        ("Homemade mango pickle", "Fruits", "Traditional mango pickle made with oil and spices — no preservatives."),
        ("Fermented vegetable pickle", "Vegetables", "Fermented pickles provide probiotics and aid digestion."),
    ],
    "water": [
        ("Coconut water", "Natural hydration", "Coconut water is nature's electrolyte drink — hydrating and low in sugar."),
        ("Buttermilk (chaas)", "Dairy", "Spiced buttermilk aids digestion and is naturally low in sugar."),
        ("Lemon water (nimbu pani)", "Fruits", "Fresh lemon water with a pinch of salt is refreshing and provides vitamin C."),
    ],
    "sprouts": [
        ("Sprouted moong", "Pulses", "Sprouting increases vitamin C and makes minerals more bioavailable."),
        ("Sprouted chana", "Pulses", "Sprouted chickpeas are high in protein and fiber."),
        ("Mixed sprouts salad", "Pulses", "Mixed sprouts with cucumber, tomato, and lemon — a nutrient-dense meal."),
    ],
    "curry": [
        ("Homemade dal curry", "Pulses", "Moong dal or toor dal curry — high in protein and fiber."),
        ("Chana masala", "Pulses", "Chickpea curry cooked with onions, tomatoes, and spices — hearty and nutritious."),
        ("Vegetable curry", "Vegetables", "Mixed vegetable curry with minimal oil — packed with vitamins."),
    ],
    "roti": [
        ("Ragi roti", "Millets", "Ragi roti is calcium-rich and gluten-free. Great for all ages."),
        ("Jowar bhakri", "Millets", "Jowar bhakri is high in fiber and iron — a traditional Indian flatbread."),
        ("Bajra roti", "Millets", "Bajra roti is warming in winter and rich in iron and fiber."),
    ],
    "tea": [
        ("Herbal tea (chamomile)", "Herbal", "Unsweetened herbal teas are antioxidant-rich and caffeine-free."),
        ("Green tea", "Natural", "Green tea contains antioxidants (catechins) and is naturally low in calories."),
        ("Masala chai (no sugar)", "Traditional", "Spiced tea without added sugar — warming and antioxidant-rich."),
    ],
    "coffee": [
        ("Black coffee (no sugar)", "Natural", "Black coffee without added sugar is low in calories and rich in antioxidants."),
        ("Herbal coffee substitute", "Herbal", "Caffeine-free alternatives like chicory root coffee — gentle on digestion."),
    ],
    "soda": [
        ("Sparkling water (unsweetened)", "Hydration", "Unsweetened sparkling water hydrates without added sugar."),
        ("Coconut water", "Natural hydration", "Coconut water is nature's electrolyte drink — hydrating and low in sugar."),
        ("Buttermilk (chaas)", "Dairy", "Spiced buttermilk aids digestion and is naturally low in sugar."),
    ],
    "energy drink": [
        ("Coconut water", "Natural hydration", "Coconut water is nature's electrolyte drink — hydrating and low in sugar."),
        ("Buttermilk (chaas)", "Dairy", "Spiced buttermilk aids digestion and is naturally low in sugar."),
        ("Green tea", "Natural", "Green tea provides gentle energy with antioxidants — no crash."),
    ],
}


def get_product_specific_alternatives(product_name):
    """Get product-specific alternatives based on the product name entered by user."""
    name = product_name.lower().strip()
    if not name:
        return []

    # Direct match
    if name in PRODUCT_SPECIFIC_ALTERNATIVES:
        return PRODUCT_SPECIFIC_ALTERNATIVES[name]

    # Partial match
    for key, alternatives in PRODUCT_SPECIFIC_ALTERNATIVES.items():
        if key in name or name in key:
            return alternatives

    # Word match
    words = name.split()
    for word in words:
        if len(word) > 3:
            for key, alternatives in PRODUCT_SPECIFIC_ALTERNATIVES.items():
                if word in key:
                    return alternatives

    return []


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## 🥗 NutriScan"
    )

    st.caption(
        "Food Ingredient Analyzer"
    )

    st.divider()

    if st.session_state.logged_in:

        st.success(
            "👤 "
            + st.session_state.user["name"]
        )

        if st.button(
            "🏠 Home",
            width="stretch",
            key="btn_1"
        ):

            st.session_state.page = "Home"
            st.rerun()

        if st.button(
            "🔍 Scan Food",
            width="stretch",
            key="btn_2"
        ):

            st.session_state.page = "Scan"
            st.rerun()

        if st.button(
            "🕘 Scan History",
            width="stretch",
            key="btn_3"
        ):

            st.session_state.page = "History"
            st.rerun()

        if st.button(
            "💧 Hydration Calculator",
            width="stretch",
            key="btn_4"
        ):

            st.session_state.page = "Hydration"
            st.rerun()

        if st.button(
            "Diet Recommendation",
            width="stretch",
            key="btn_diet_loggedin"
        ):

            st.session_state.page = "Diet"
            st.rerun()

        if st.button(
            "👤 Account",
            width="stretch",
            key="btn_5"
        ):

            st.session_state.page = "Account"
            st.rerun()

        st.divider()

        if st.button(
            "🚪 Logout",
            width="stretch",
            key="btn_6"
        ):

            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.page = "Home"
            st.session_state.analysis_result = None
            drop_login_token(st.session_state.get("login_token"))
            st.session_state.login_token = None
            st.rerun()

    else:

        if st.button(
            "🏠 Home",
            width="stretch",
            key="btn_7"
        ):

            st.session_state.page = "Home"
            st.rerun()

        if st.button(
            "🔐 Login",
            width="stretch",
            key="btn_8"
        ):

            st.session_state.page = "Login"
            st.rerun()

        if st.button(
            "💧 Hydration Calculator",
            width="stretch",
            key="btn_9"
        ):

            st.session_state.page = "Hydration"
            st.rerun()

        if st.button(
            "🥗 Diet Recommendation",
            width="stretch",
            key="btn_diet"
        ):

            st.session_state.page = "Diet"
            st.rerun()

        if st.button(
            "📝 Sign Up",
            width="stretch",
            key="btn_12"
        ):

            st.session_state.page = "Signup"
            st.rerun()


# ============================================================
# HOME
# ============================================================

if st.session_state.page == "Home":

    st.markdown(
        '<div class="main-title">NutriScan</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Understand what is inside your food.'
        '</div>',
        unsafe_allow_html=True
    )

    st.write(
        """
        NutriScan scans packaged-food ingredient lists,
        extracts the text using OCR, and compares the
        detected ingredients with your ingredient database.
        """
    )

    st.divider()

    # Database status
    from modules.supabase_db import _test_supabase_connection
    if _test_supabase_connection():
        st.success("🟢 Database: Supabase (Cloud)")
    else:
        st.info(" Database: Local Storage (Supabase will auto-connect in cloud)")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "📷 Scan Food",
            width="stretch",
            key="btn_13"
        ):

            if st.session_state.logged_in:

                st.session_state.page = "Scan"

            else:

                st.session_state.page = "Login"

            st.rerun()

    with col2:

        if st.button(
            "🔐 Login",
            width="stretch",
            key="btn_14"
        ):

            st.session_state.page = "Login"
            st.rerun()

    st.divider()

    # CSV check
    if os.path.exists(CSV_PATH):

        try:

            df = load_ingredients()

            st.success(
                "🟢 Ingredient database connected"
            )

            st.info(
                f"Database contains "
                f"**{len(df)} ingredients**."
            )

        except Exception as e:

            st.error(
                "CSV error: " + str(e)
            )

    else:

        st.error(
            "ingredients.csv was not found."
        )

        st.info(
            "Put ingredients.csv inside the "
            "'database' folder next to app.py."
        )

    if RAPID_AVAILABLE:

        st.success(
            "🟢 Fast OCR engine is available (~1.5 sec per scan)"
        )

    elif PADDLE_AVAILABLE:

        st.success(
            "🟢 PaddleOCR is available"
        )

    else:

        st.error(
            "🔴 No OCR engine could be imported."
        )

    if EMAIL_AVAILABLE and is_configured():
        st.success(
            "🟢 Email service is configured"
        )
    elif EMAIL_AVAILABLE:
        st.warning(
            "🟡 Email service available but not configured"
        )
    else:
        st.error(
            "🔴 Email service could not be imported."
        )


# ============================================================
# SIGNUP
# ============================================================

elif st.session_state.page == "Signup":

    st.title(
        "📝 Create Account"
    )

    name = st.text_input(
        "Full Name"
    )

    email = st.text_input(
        "Email"
    )

    password = st.text_input(
        "Password",
        type="password"
    )

    confirm = st.text_input(
        "Confirm Password",
        type="password"
    )

    if st.button(
        "Create Account",
        width="stretch",
        key="btn_15"
    ):

        email = email.lower().strip()

        if not name or not email or not password:

            st.error(
                "Please fill in all fields."
            )

        elif password != confirm:

            st.error(
                "Passwords do not match."
            )

        elif len(password) < 6:

            st.error(
                "Password must contain at least 6 characters."
            )

        else:

            success, message = create_user(
                name,
                email,
                password
            )

            if success:

                st.success(
                    message
                )

                st.session_state.page = "Login"

                st.rerun()

            else:

                st.error(
                    message
                )


# ============================================================
# LOGIN
# ============================================================

elif st.session_state.page == "Login":

    st.title(
        "🔐 Login"
    )

    email = st.text_input(
        "Email"
    )

    password = st.text_input(
        "Password",
        type="password"
    )

    if st.button(
        "Login",
        width="stretch",
        key="btn_16"
    ):

        if not email or not password:

            st.error(
                "Enter email and password."
            )

        else:

            user = authenticate_user(
                email,
                password
            )

            if user:

                st.session_state.logged_in = True
                st.session_state.user = user
                st.session_state.page = "Scan"

                # Stay logged in even if the phone reloads the page:
                # the token lives in the URL and restores this session.
                try:
                    _token = issue_login_token(user)
                    st.session_state.login_token = _token
                    st.query_params["auto_login"] = _token
                except Exception:
                    pass

                st.success(
                    "Login successful."
                )

                st.rerun()

            else:

                st.error(
                    "Invalid email or password."
                )

    st.divider()

    if st.button(
        "🔑 Forgot Password?",
        key="btn_17"
    ):

        st.session_state.page = "Forgot"
        st.rerun()

    if st.button(
        "📝 Create new account",
        key="btn_18"
    ):

        st.session_state.page = "Signup"
        st.rerun()


# ============================================================
# FORGOT PASSWORD
# ============================================================

elif st.session_state.page == "Forgot":

    st.title(
        "🔑 Forgot Password"
    )

    st.write(
        "Enter the email registered with NutriScan."
    )

    email = st.text_input(
        "Registered Email"
    )

    if st.button(
        "Generate OTP",
        width="stretch",
        key="btn_19"
    ):

        user = sb_user_exists(email)

        if not user:

            st.error(
                "No account found with this email."
            )

        elif not EMAIL_AVAILABLE or not is_configured():

            st.warning(
                "Password reset email is not configured. "
                "Ask the app administrator to add GMAIL_USER and "
                "GMAIL_APP_PASSWORD in the app's Streamlit secrets."
            )

        else:

            otp = str(
                secrets.randbelow(900000)
                + 100000
            )

            user_name = sb_get_user_name(email)
            success, message = send_otp_email(
                email.lower().strip(),
                otp,
                user_name
            )
            if success:
                st.session_state.otp = otp
                st.session_state.reset_email = (
                    email.lower().strip()
                )
                st.session_state.otp_verified = False
                st.success(
                    "OTP sent! Please check your email."
                )
                st.session_state.page = "Verify OTP"
            else:
                st.session_state.otp = None
                st.session_state.reset_email = ""
                st.session_state.otp_verified = False
                st.error(
                    "Failed to send OTP email: " + message
                )


# ============================================================
# VERIFY OTP
# ============================================================

elif st.session_state.page == "Verify OTP":

    st.title(
        "📩 Verify OTP"
    )

    st.write(
        "OTP for: "
        + st.session_state.reset_email
    )

    otp_input = st.text_input(
        "Enter 6-digit OTP",
        max_chars=6
    )

    if st.button(
        "Verify OTP",
        width="stretch",
        key="btn_20"
    ):

        if (
            st.session_state.otp
            and otp_input == st.session_state.otp
        ):

            st.session_state.otp_verified = True
            st.session_state.otp = None
            st.session_state.page = "Reset Password"

            st.success(
                "OTP verified."
            )

            st.rerun()

        else:

            st.error(
                "Invalid OTP."
            )


# ============================================================
# RESET PASSWORD
# ============================================================

elif st.session_state.page == "Reset Password":

    st.title(
        "🔐 Reset Password"
    )

    new_password = st.text_input(
        "New Password",
        type="password"
    )

    confirm = st.text_input(
        "Confirm New Password",
        type="password"
    )

    if st.button(
        "Reset Password",
        width="stretch",
        key="btn_21"
    ):

        if not st.session_state.otp_verified:

            st.error(
                "OTP verification required."
            )

        elif len(new_password) < 6:

            st.error(
                "Password must contain at least 6 characters."
            )

        elif new_password != confirm:

            st.error(
                "Passwords do not match."
            )

        else:

            success = change_password(
                st.session_state.reset_email,
                new_password
            )

            if success:

                st.success(
                    "Password reset successfully."
                )

                st.session_state.otp_verified = False
                st.session_state.reset_email = ""
                st.session_state.page = "Login"

                st.rerun()

            else:

                st.error(
                    "Unable to reset password."
                )


# ============================================================
# SCAN
# ============================================================

elif st.session_state.page == "Scan":

    st.title(
        "🔍 Scan Food"
    )

    if not st.session_state.logged_in:

        st.warning(
            "Please login first."
        )

        st.session_state.page = "Login"

        st.rerun()

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    try:

        df = load_ingredients()

    except Exception as e:

        st.error(
            "Database error: " + str(e)
        )

        st.stop()

    if df is None:

        st.error(
            "ingredients.csv was not found."
        )

        st.info(
            "Create this file:\n\n"
            "NutriScan/database/ingredients.csv"
        )

        st.stop()

    # --------------------------------------------------------
    # OCR CHECK
    # --------------------------------------------------------

    if not OCR_AVAILABLE:

        st.error(
            "OCR engine is not available."
        )

        st.code(
            "pip install rapidocr-onnxruntime paddleocr"
        )

        st.stop()

    # Preload the OCR model in the background so scanning starts instantly
    if not st.session_state.get("ocr_warmup_started", False):
        st.session_state.ocr_warmup_started = True
        import threading
        threading.Thread(target=_warmup_ocr, daemon=True).start()

    st.write(
        "📷 Take a photo directly, or upload a clear picture of the ingredient list."
    )

    # --------------------------------------------------------
    # MOBILE-FRIENDLY UPLOAD FORM
    # --------------------------------------------------------
    # Streamlit only sends the selected file to Python when the form
    # is submitted. This prevents the page from repeatedly processing
    # or appearing to refresh while a user is selecting an image.
    with st.form("scan_form", clear_on_submit=False):
        uploaded_file = st.file_uploader(
            "Choose food image",
            type=[
                "jpg",
                "jpeg",
                "png",
                "webp"
            ],
            help="For fastest results, use a clear photo focused on the ingredient list."
        )

        # Camera option works best on phones: no switching to the
        # gallery app means the page does not reload/refresh.
        camera_file = st.camera_input(
            "Or take a photo now (best on mobile)",
            help="Point your camera at the ingredient list and capture it."
        )

        analyze_clicked = st.form_submit_button(
            "🔎 Analyze Food",
            width="stretch"
        )

    if analyze_clicked:
        # Camera photo wins if both were provided
        active_file = camera_file if camera_file is not None else uploaded_file

        # Prevent double-clicks while scanning
        if st.session_state.get("is_scanning", False):
            # Check if scan has been running too long (stuck)
            import time
            scan_start = st.session_state.get("scan_start_time", 0)
            if scan_start and (time.time() - scan_start) > 60:  # 1 minute
                # Reset stuck scan
                st.session_state.is_scanning = False
                st.session_state.scan_start_time = 0
                st.warning("Previous scan was stuck. Starting new scan...")
            else:
                st.warning("⏳ Scan already in progress. Please wait...")
                st.stop()

        if not active_file:
            st.warning("Please take a photo or choose a food image first.")
            st.stop()

        image_bytes = active_file.getvalue()

        if not image_bytes:
            st.error("The selected image is empty.")
            st.stop()

        # Set scanning flag + start time (so stuck scans auto-reset)
        import time
        st.session_state.is_scanning = True
        st.session_state.scan_start_time = time.time()

        try:
            # ----------------------------------------------------
            # SHOW IMAGE ONLY AFTER SUBMISSION
            # ----------------------------------------------------
            try:
                image = Image.open(io.BytesIO(image_bytes))
                st.image(
                    image,
                    caption="Selected Food Image",
                    width="stretch"
                )
            except Exception:
                st.error("Unable to open image.")
                st.stop()

            st.divider()

            # ----------------------------------------------------
            # FAST OCR with progress indicator
            # ----------------------------------------------------
            scan_status = st.status("Step 1/4: Reading text from image...", state="running")
            texts, ocr_error = run_ocr(active_file)

            if ocr_error:
                scan_status.update(label="OCR failed", state="error")
                st.error("OCR Error:")
                st.code(ocr_error)
                st.info(
                    "Try a clear, close photo of the ingredient list."
                )
                st.stop()

            ocr_text = "\n".join(texts)
            st.session_state.ocr_text = ocr_text

            if not ocr_text.strip():
                scan_status.update(label="No text found", state="error")
                st.warning("OCR did not detect readable text.")
                st.info(
                    "Try a clearer, closer photo of the ingredient list."
                )
                st.stop()

            scan_status.update(label=f"Step 2/4: Found {len(texts)} text fragments", state="running")

            # Start a fresh NutriBot conversation for each new scan.
            st.session_state.nutribot_messages = []
            st.session_state.show_food_alternatives = False
            st.session_state.alternative_query = ""
            st.session_state.smart_swap_product_name = ""

            # ----------------------------------------------------
            # MATCH INGREDIENTS
            # ----------------------------------------------------
            scan_status.update(label="Step 3/4: Matching ingredients...", state="running")
            matched = match_ingredients(
                ocr_text,
                df
            )
            scan_status.update(label=f"Found {len(matched)} matching ingredients", state="running")

            # ----------------------------------------------------
            # HIGH-CONCERN KEYWORDS
            # ----------------------------------------------------
            keyword_matches = find_high_concern_keywords(ocr_text)
            scan_status.update(label="Step 4/4: Scan complete!", state="complete")

        finally:
            # Always reset scanning flag
            st.session_state.is_scanning = False
            st.session_state.scan_start_time = 0

        # ----------------------------------------------------
        # SAVE RESULT (without AI - AI runs in background)
        # ----------------------------------------------------
        save_ok, save_message = save_scan_history(
            st.session_state.user["email"],
            active_file.name,
            image_bytes,
            ocr_text,
            matched,
            keyword_matches,
            ""  # AI result saved later
        )

        if save_ok:
            st.success("✅ Scan saved to your history.")

        # ----------------------------------------------------
        # START AI ANALYSIS IN BACKGROUND WITH FAST PATH
        # ----------------------------------------------------
        import concurrent.futures

        def _run_ai_background():
            """Build the ingredient analysis fully offline (instant)."""
            if not matched:
                return (
                    "No ingredients were confidently matched "
                    "from the scanned image, so no analysis was "
                    "generated."
                )

            try:
                return ask_ai(matched, keyword_matches)
            except Exception as e:
                return (
                    "The local analysis engine could not build "
                    "this report.\n\n"
                    f"Technical detail: {str(e)}"
                )

        # Store the matched data for AI context
        st.session_state._ai_matched = matched
        st.session_state._ai_ocr_text = ocr_text

        # Launch AI in background
        if "ai_executor" not in st.session_state:
            st.session_state.ai_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        st.session_state.ai_future = st.session_state.ai_executor.submit(_run_ai_background)

        # ----------------------------------------------------
        # SHOW LOCAL RESULTS IMMEDIATELY WITH PROGRESS
        # ----------------------------------------------------
        st.session_state.analysis_result = {
            "ocr_text": ocr_text,
            "matched": matched,
            "keyword_matches": keyword_matches,
            "ai_result": "⏳ AI analysis in progress..."
        }

        # AI status is shown by the live "AI Analysis" section below,
        # which updates itself without stored widgets or full reloads.


    # Results must live outside the Analyze button block: Streamlit reruns the
    # script on chat input and text changes. Session state keeps the scan alive.
    result = st.session_state.get("analysis_result")
    if result and result.get("ocr_text"):
        ocr_text = result.get("ocr_text", "")
        matched = result.get("matched", [])
        keyword_matches = result.get("keyword_matches", [])
        ai_result = result.get("ai_result", "")

        st.divider()
        st.subheader(" Scan Results")
        display_analysis(ocr_text, matched, keyword_matches)


        # ----------------------------------------------------
        # AI RESULTS - a small section that refreshes BY ITSELF
        # (Streamlit fragment) instead of reloading the whole page.
        # This removes the "page refreshing" feeling on mobile.
        # ----------------------------------------------------
        @st.fragment(run_every=3)
        def _render_ai_analysis():
            fut = st.session_state.get("ai_future")
            if fut is not None and fut.done():
                try:
                    st.session_state.analysis_result["ai_result"] = fut.result()
                except Exception as e:
                    st.session_state.analysis_result["ai_result"] = (
                        f"AI analysis failed: {str(e)}"
                    )
                st.session_state.ai_future = None

            ai = (st.session_state.get("analysis_result") or {}).get(
                "ai_result", ""
            )
            st.divider()
            st.subheader("AI Ingredient Analysis")
            if ai and not ai.startswith("⏳"):
                st.markdown(ai)
            else:
                st.info(
                    "⏳ AI analysis in progress... the result will appear "
                    "here automatically, without reloading the page."
                )

        _render_ai_analysis()

        # Keep ai_result fresh for the NutriBot context below
        ai_result = (st.session_state.get("analysis_result") or {}).get(
            "ai_result", ai_result
        )

        st.divider()
        st.subheader(" Ask NutriBot — Your Health Assistant")

        st.warning(
            "⚠️ MEDICAL DISCLAIMER: NutriBot provides general health and nutrition information only. "
            "It does NOT provide medical advice, diagnosis, or treatment. "
            "Always consult a qualified doctor or healthcare professional for medical concerns, "
            "before making dietary changes, or if you have existing health conditions. "
            "In case of emergency, call your local emergency services immediately.",
            icon="⚠️",
        )

        st.caption(
            "Ask about: nutrition, ingredients, healthy alternatives, diet tips, "
            "hydration, millets, fruits, vegetables, ghee, vegetarianism, "
            "weight management, immunity, digestion, or general wellness."
        )

        # Show collected scan data
        product_name = st.session_state.get("smart_swap_product_name", "")
        with st.expander("📊 Collected Scan Data", expanded=False):
            grade, grade_desc, grade_color = calculate_grade(matched, keyword_matches)
            st.markdown(f"**Grade:** {grade} — {grade_desc}")
            st.markdown(f"**Product:** {product_name or 'Not specified'}")
            st.markdown(f"**Matched Ingredients:** {len(matched)}")
            if matched:
                for item in matched:
                    st.write(f"- {item.get('ingredient', 'Unknown')} ({item.get('category', 'N/A')}) — {item.get('match_score', 0)}% match")
            st.markdown(f"**Concern Keywords:** {', '.join(keyword_matches) if keyword_matches else 'None'}")

        if "nutribot_messages" not in st.session_state:
            st.session_state.nutribot_messages = []

        for msg in st.session_state.nutribot_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        question = st.chat_input(
            "Ask about health, nutrition, ingredients, alternatives...",
            key="nutribot_chat_input",
        )
        if question:
            st.session_state.nutribot_messages.append({"role": "user", "content": question})
            conversation = "\n\n".join(
                f"{m['role'].upper()}: {m['content']}"
                for m in st.session_state.nutribot_messages[-8:]
            )
            product_name = st.session_state.get("smart_swap_product_name", "")

            # Calculate grade for context
            grade, grade_desc, grade_color = calculate_grade(matched, keyword_matches)

            # Format matched ingredients for better AI understanding
            matched_ingredients_text = ""
            if matched:
                matched_ingredients_text = "\n".join([
                    f"- {item.get('ingredient', 'Unknown')} (Category: {item.get('category', 'N/A')}, Match: {item.get('match_score', 0)}%)"
                    for item in matched
                ])
            else:
                matched_ingredients_text = "No ingredients matched."

            # Format concern keywords
            concern_keywords_text = ", ".join(keyword_matches) if keyword_matches else "None"

            context = (
                "You are NutriBot, a comprehensive health and nutrition assistant for NutriScan. "
                "You provide evidence-based information on: nutrition, food ingredients, healthy alternatives, "
                "Indian superfoods (millets, fruits, vegetables, ghee, pulses), vegetarian nutrition, "
                "hydration, immunity, digestion, weight management, and general wellness.\n\n"
                "GUIDELINES:\n"
                "- Provide accurate, science-based health and nutrition information\n"
                "- Reference ICMR, WHO, and established nutritional guidelines where relevant\n"
                "- Promote whole foods, millets, fruits, vegetables, and balanced vegetarian diets\n"
                "- Suggest practical, affordable Indian food alternatives\n"
                "- Be specific and actionable in your recommendations\n"
                "- If information is insufficient or uncertain, clearly state the limitations\n"
                "- Never diagnose diseases, prescribe treatments, or replace professional medical advice\n"
                "- If the user asks about a medical condition, recommend consulting a doctor\n"
                "- Always include a brief health disclaimer for medical topics\n"
                "- Use simple, clear language that anyone can understand\n\n"
                f"Current scan context:\n"
                f"Product: {product_name}\n"
                f"Health Grade: {grade} ({grade_desc})\n"
                f"OCR text: {ocr_text[:6000]}\n\n"
                f"Matched ingredients ({len(matched)} found):\n{matched_ingredients_text}\n\n"
                f"High-concern keywords detected: {concern_keywords_text}\n\n"
                f"AI analysis: {str(ai_result)[:3000]}\n\n"
                f"Conversation history:\n{conversation}\n\n"
                "Answer the user's latest question helpfully and safely. "
                "You can analyze the grade, explain why the product received it, "
                "suggest healthier alternatives, and provide general health guidance."
            )
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                with st.spinner("NutriBot is preparing a health-focused answer..."):
                    answer = None
                    brain_used = None

                    # --------------------------------------------
                    # LAYER 1: Ollama local AI (no internet needed)
                    # --------------------------------------------
                    if not answer:
                        try:
                            from modules.offline_brain import ask_ollama
                            answer = ask_ollama(question, context[:2500])
                            brain_used = "ollama"
                        except Exception:
                            answer = None

                    # --------------------------------------------
                    # LAYER 2: built-in knowledge base (always works)
                    # --------------------------------------------
                    if not answer:
                        try:
                            from modules.offline_brain import offline_answer
                            answer = offline_answer(
                                question,
                                grade=grade,
                                matched=matched,
                                keywords=keyword_matches,
                            )
                            if answer:
                                brain_used = "offline"
                        except Exception:
                            answer = None

                    if not answer:
                        answer = (
                            "I couldn't answer that right now. "
                            "Please try rephrasing your question, or ask me "
                            "about nutrition, ingredients, sugar, salt, "
                            "protein, millets, diabetes or heart health."
                        )

                    if brain_used == "ollama":
                        answer += "\n\n*💻 Answered by local offline AI*"
                    elif brain_used == "offline":
                        answer += "\n\n*📚 Answered from built-in health guide (offline)*"

                    if any(word in question.lower() for word in ["disease", "pain", "symptom", "medicine", "treatment", "diagnosis", "cancer", "diabetes", "blood pressure", "heart"]):
                        answer += "\n\n⚠️ **Reminder:** This is general information only. Please consult a qualified healthcare professional for medical advice."
                st.markdown(answer)
            st.session_state.nutribot_messages.append({"role": "assistant", "content": answer})




# ============================================================
# DIET RECOMMENDATION
# ============================================================

elif st.session_state.page == "Diet":

    st.title("Diet Recommendation")
    st.caption("Personalized nutrition based on ICMR and WHO guidelines")

    st.divider()

    st.markdown("### Enter Your Details")

    col1, col2, col3 = st.columns(3)

    with col1:
        diet_age = st.number_input("Age (years)", min_value=1, max_value=120, value=25, step=1)

    with col2:
        diet_gender = st.selectbox("Gender", ["Male", "Female"])

    with col3:
        diet_disease = st.selectbox("Health Condition", ["None", "Diabetes", "Hypertension", "Anemia", "Obesity", "Heart Disease", "Kidney Disease", "Thyroid"])

    st.divider()

    if st.button("Get My Diet Plan", width="stretch", key="btn_diet_plan"):

        from modules.diet_recommender import get_nutrient_requirements, get_diet_recommendations, get_foods_to_avoid

        disease = None if diet_disease == "None" else diet_disease

        nutrients = get_nutrient_requirements(diet_age, diet_gender, disease)
        recommendations = get_diet_recommendations(diet_age, diet_gender, disease)
        foods_to_avoid = get_foods_to_avoid(disease)

        st.divider()
        st.markdown("### Your Daily Nutrient Requirements")

        nut_cols = st.columns(4)
        nut_items = [
            ("Calories", f"{nutrients['calories']} kcal"),
            ("Protein", f"{nutrients['protein']} g"),
            ("Fiber", f"{nutrients['fiber']} g"),
            ("Iron", f"{nutrients['iron']} mg"),
            ("Calcium", f"{nutrients['calcium']} mg"),
            ("Vitamin C", f"{nutrients['vitamin_c']} mg"),
            ("Vitamin A", f"{nutrients['vitamin_a']} mcg"),
            ("Folic Acid", f"{nutrients['folic_acid']} mcg"),
            ("Zinc", f"{nutrients['zinc']} mg"),
            ("Vitamin D", f"{nutrients['vitamin_d']} mcg"),
        ]

        for i, (label, value) in enumerate(nut_items):
            with nut_cols[i % 4]:
                st.metric(label, value)

        st.divider()
        st.markdown("### Your Personalized Diet Plan")

        for category, details in recommendations.items():
            with st.container(border=True):
                st.markdown(f"**{category.replace('_', ' ').title()}** — {details['servings']} servings")
                st.caption(details["note"])
                for ex in details["examples"]:
                    st.write(f"- {ex}")

        st.divider()
        st.markdown("### Foods to Avoid")

        for food in foods_to_avoid:
            st.write(f"- {food}")

        st.divider()
        st.info("These recommendations are based on ICMR and WHO guidelines. Individual needs may vary. Consult a healthcare provider or nutritionist for personalized advice.")


# ============================================================
# HISTORY
# ============================================================

elif st.session_state.page == "History":

    st.title(" Scan History")

    if not st.session_state.logged_in:
        st.warning("Please login first.")
        st.session_state.page = "Login"
        st.rerun()

    user = st.session_state.user
    scans = get_scan_history(user["email"])

    if not scans:
        st.info("No previous scans have been stored yet.")
    else:
        st.write(f"You have {len(scans)} stored scan(s).")
        for scan in scans:
            scan_id, scan_time, image_name, image_data, ocr_text, matched_json, keyword_json, ai_result = scan
            matched = json.loads(matched_json or "[]")

            # PDF download button - always visible outside expander
            try:
                pdf_data = make_scan_pdf(
                    scan,
                    user["name"],
                    user["email"],
                    st.session_state.get("nutribot_messages", []),
                )
                if pdf_data:
                    st.download_button(
                        "📄 Download PDF Report",
                        data=pdf_data,
                        file_name=f"NutriScan_Report_{scan_id}.pdf",
                        mime="application/pdf",
                        key=f"download_scan_{scan_id}",
                        width="stretch"
                    )
                else:
                    st.warning("Could not generate PDF report for this scan.")
            except Exception as e:
                st.error(f"PDF generation failed: {str(e)}")

            with st.expander(f"📷 {image_name or 'Food image'} — {scan_time}"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    if image_data:
                        st.image(image_data, width="stretch")
                with c2:
                    st.write("**Scan date & time:**", scan_time)
                    st.write("**Ingredients detected:**", len(matched))
                if ai_result:
                    st.subheader(" AI Ingredient Analysis")
                    st.markdown(ai_result)
                with st.expander("📄 OCR Text"):
                    st.text(ocr_text or "No OCR text stored.")

# ============================================================
# ACCOUNT
# ============================================================

elif st.session_state.page == "Account":

    st.title(
        "👤 My Account"
    )

    if not st.session_state.logged_in:

        st.warning(
            "Please login first."
        )

        st.session_state.page = "Login"
        st.rerun()

    user = st.session_state.user

    st.write(
        "**Name:**",
        user["name"]
    )

    st.write(
        "**Email:**",
        user["email"]
    )

    st.divider()

    if st.button(
        "🚪 Logout",
        width="stretch",
        key="btn_22"
    ):

        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.page = "Home"
        st.session_state.analysis_result = None
        drop_login_token(st.session_state.get("login_token"))
        st.session_state.login_token = None

        st.rerun()


# ============================================================
# HYDRATION CALCULATOR
# ============================================================

elif st.session_state.page == "Hydration":

    st.title(" Hydration Calculator")
    st.caption("Based on ICMR and WHO scientific guidelines")

    st.divider()

    st.markdown("### Enter your details")

    col1, col2, col3 = st.columns(3)

    with col1:
        weight = st.number_input("Weight (kg)", min_value=20, max_value=200, value=60, step=1)

    with col2:
        gender = st.selectbox("Gender", ["Male", "Female"])

    with col3:
        age = st.number_input("Age (years)", min_value=1, max_value=120, value=25, step=1)

    col4, col5, col6 = st.columns(3)

    with col4:
        activity = st.selectbox("Activity Level", ["Sedentary (office work, little exercise)", "Moderate (walking, light exercise 3-5 days/week)", "Active (daily exercise or physical job)", "Very Active (intense exercise daily or physical labor)"])

    with col5:
        climate = st.selectbox("Climate", ["Normal (moderate temperature)", "Hot / Humid", "Cold / Dry", "Very Hot (summer in India, 40°C+)"])

    with col6:
        health_conditions = st.multiselect("Health Conditions", ["None", "Pregnant", "Breastfeeding", "Fever", "Diarrhea/Vomiting", "Kidney disease", "Heart disease"])

    st.divider()

    if st.button("Calculate My Water Needs", width="stretch", key="btn_23"):

        # ICMR Formula: 35 ml per kg body weight (baseline)
        base_water_ml = weight * 35

        # Gender adjustment (WHO guidelines)
        if gender == "Male":
            base_water_ml *= 1.1
        else:
            base_water_ml *= 0.95

        # Age adjustment
        if age > 55:
            base_water_ml *= 0.95
        elif age > 30:
            base_water_ml *= 1.0

        # Activity level multiplier
        activity_multiplier = {
            "Sedentary (office work, little exercise)": 1.0,
            "Moderate (walking, light exercise 3-5 days/week)": 1.2,
            "Active (daily exercise or physical job)": 1.4,
            "Very Active (intense exercise daily or physical labor)": 1.6,
        }
        base_water_ml *= activity_multiplier.get(activity, 1.0)

        # Climate adjustment
        climate_addition = {
            "Normal (moderate temperature)": 0,
            "Hot / Humid": 500,
            "Cold / Dry": 200,
            "Very Hot (summer in India, 40°C+)": 1000,
        }
        base_water_ml += climate_addition.get(climate, 0)

        # Health condition adjustments
        condition_addition = 0
        for condition in health_conditions:
            if condition == "Pregnant":
                condition_addition += 300
            elif condition == "Breastfeeding":
                condition_addition += 700
            elif condition == "Fever":
                condition_addition += 500
            elif condition == "Diarrhea/Vomiting":
                condition_addition += 1000
            elif condition == "Kidney disease":
                condition_addition = -500
            elif condition == "Heart disease":
                condition_addition = -300

        base_water_ml += condition_addition
        base_water_ml = max(1000, base_water_ml)

        total_liters = base_water_ml / 1000
        glasses = base_water_ml / 250

        st.divider()
        st.markdown("### Your Daily Water Requirements")

        result_cols = st.columns(3)
        with result_cols[0]:
            st.metric("Total Water (liters)", f"{total_liters:.1f} L")
        with result_cols[1]:
            st.metric("Total Water (ml)", f"{int(base_water_ml)} ml")
        with result_cols[2]:
            st.metric("Glasses (250ml)", f"{glasses:.0f} glasses")

        st.divider()
        st.markdown("### Breakdown")

        st.write(f"- **Base requirement (body weight):** {int(weight * 35)} ml")
        st.write(f"- **Gender adjustment:** {'+10%' if gender == 'Male' else '-5%'}")
        st.write(f"- **Activity adjustment:** {activity_multiplier.get(activity, 1.0)}x multiplier")
        st.write(f"- **Climate adjustment:** +{climate_addition.get(climate, 0)} ml")
        if health_conditions and "None" not in health_conditions:
            st.write(f"- **Health condition adjustment:** {condition_addition:+d} ml")

        st.divider()
        st.markdown("### Tips for Staying Hydrated")
        st.info(" Start your day with 1-2 glasses of water on an empty stomach. Sip water throughout the day rather than drinking large amounts at once. Monitor urine color — pale yellow indicates good hydration. Increase intake during exercise, hot weather, and illness.")

        st.caption("These calculations are based on ICMR (Indian Council of Medical Research) and WHO guidelines. Individual needs may vary. Consult a healthcare provider for personalized advice, especially if you have medical conditions.")

# ============================================================
# SAVE SESSION SNAPSHOT (runs at the end of every script run)
# ------------------------------------------------------------
# Attaches the current page + scan results to the login token,
# so a mobile page reload restores exactly what the user was
# looking at - no re-login, no lost scan.
# ============================================================

try:
    if st.session_state.get("logged_in"):
        _snap_token = st.session_state.get("login_token")
        if _snap_token and _snap_token in _LOGIN_TOKENS:
            _LOGIN_TOKENS[_snap_token]["snapshot"] = {
                "page": st.session_state.get("page", "Home"),
                "analysis_result": st.session_state.get("analysis_result"),
                "nutribot_messages": st.session_state.get(
                    "nutribot_messages", []
                ),
                "smart_swap_product_name": st.session_state.get(
                    "smart_swap_product_name", ""
                ),
            }
except Exception:
    pass
