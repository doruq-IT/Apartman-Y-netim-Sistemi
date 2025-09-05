# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()
basedir = os.path.abspath(os.path.dirname(__file__))

def _env_list(key, default):
    val = os.environ.get(key)
    if not val:
        return default
    return [item.strip() for item in val.split(",") if item.strip()]

class Config:
    # ─────────────────────────── Güvenlik
    SECRET_KEY      = os.environ.get("SECRET_KEY")
    JWT_SECRET_KEY  = os.environ.get("JWT_SECRET_KEY")

    # ─────────────────────────── Veritabanı
    SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ─────────────────────────── Upload
    UPLOAD_FOLDER   = os.path.join(basedir, "app", "static", "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB

    # ─────────────────────────── E-posta
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@flatnetsite.com")
    MAIL_FROM_NAME      = os.environ.get("MAIL_FROM_NAME", "FlatNetSite")
    MAIL_DEBUG_MODE     = os.environ.get("MAIL_DEBUG_MODE", "False")

    # SendGrid (email.py zaten os.environ'dan da okuyor)
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
    
    # Brevo SMTP (Microsoft domainleri için)
    BREVO_SMTP_HOST = os.environ.get("BREVO_SMTP_HOST")
    BREVO_SMTP_PORT = int(os.environ.get("BREVO_SMTP_PORT", 587))
    BREVO_SMTP_LOGIN = os.environ.get("BREVO_SMTP_LOGIN")
    BREVO_SMTP_PASSWORD = os.environ.get("BREVO_SMTP_PASSWORD")

    # (Opsiyonel/eski SMTP ayarları – kullanmıyorsan kalsın, zararı yok)
    MAIL_SERVER   = "smtp.sendgrid.net"
    MAIL_PORT     = 2525
    MAIL_USE_TLS  = True
    MAIL_USERNAME = "apikey"
    MAIL_PASSWORD = SENDGRID_API_KEY

    ADMIN_EMAIL   = os.environ.get("ADMIN_EMAIL")

    # Cloud Storage
    GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
    
    # --- DOCUMENT AI AYARLARI ---
    DOCAI_PROCESSOR_ID = '90480319095c8879'
    DOCAI_LOCATION = 'eu'

    # ─────────────────────────── BİLDİRİM SERVİSLERİ (YENİ EKLENDİ)
    # Huawei Push Kit (HMS) için ayarlar
    HMS_APP_ID = os.environ.get("HMS_APP_ID")
    HMS_APP_SECRET = os.environ.get("HMS_APP_SECRET")
    # ─────────────────────────── EKLEME SONU

    # ─────────────────────────── CORS
    CORS_ORIGINS = _env_list(
        "CORS_ORIGINS",
        [
            "capacitor://localhost",
            "ionic://localhost",
            "http://localhost",
            "http://127.0.0.1",
            "http://127.0.0.1:19006",
            "https://www.flatnetsite.com",
            "https://flatnetsite.com",
            "https://api.flatnetsite.com",
        ],
    )
    JWT_ACCESS_TOKEN_EXPIRES = False
