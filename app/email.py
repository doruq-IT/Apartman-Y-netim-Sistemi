# app/email.py
"""
SendGrid + Brevo ile e-posta gönderimi.
Kural: Microsoft domainlerine (outlook/hotmail/live/msn) Brevo SMTP,
diğer tüm adreslere SendGrid API üzerinden gönder.
`send_email()` proje genelinde tek çağrı noktasıdır.
"""

from flask import current_app, render_template
from threading import Thread
import os
import re
import ssl
import smtplib
import sendgrid
from email.message import EmailMessage
from sendgrid.helpers.mail import Mail as SGMail, Email
from python_http_client.exceptions import HTTPError

# ──────────────────────────────────────────────────────────────
# 0) Microsoft domainleri seti
# ──────────────────────────────────────────────────────────────
MICROSOFT_DOMAINS = {
    "outlook.com", "hotmail.com", "live.com", "msn.com",
    "outlook.com.tr", "windowslive.com"
}

def _domain_of(addr: str) -> str:
    return (addr or "").rsplit("@", 1)[-1].lower().strip()

def _is_ms(addr: str) -> bool:
    return _domain_of(addr) in MICROSOFT_DOMAINS

# ──────────────────────────────────────────────────────────────
# 1) SendGrid istemcisi
# ──────────────────────────────────────────────────────────────
def _get_sg_client():
    """
    SendGrid client'i gönderim anında oluştur.
    Önce current_app.config, sonra os.environ kontrol edilir.
    """
    app = current_app._get_current_object()
    api_key = app.config.get("SENDGRID_API_KEY") or os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        raise RuntimeError("SENDGRID_API_KEY yok: SendGrid kanalı kullanılamaz.")
    return sendgrid.SendGridAPIClient(api_key=api_key)

# ──────────────────────────────────────────────────────────────
# 2) Brevo SMTP bilgileri
# ──────────────────────────────────────────────────────────────
def _get_brevo_config():
    """
    Brevo ayarlarını o anki uygulama context'inden (config) çeker.
    """
    app = current_app._get_current_object()
    return {
        "host": app.config.get("BREVO_SMTP_HOST"),
        "port": app.config.get("BREVO_SMTP_PORT"),
        "login": app.config.get("BREVO_SMTP_LOGIN"),
        "password": app.config.get("BREVO_SMTP_PASSWORD")
    }

def _brevo_ready() -> bool:
    """Brevo ayarlarının tam olup olmadığını kontrol eder."""
    config = _get_brevo_config()
    return all(config.values())

# ──────────────────────────────────────────────────────────────
# 3) Yardımcılar
# ──────────────────────────────────────────────────────────────
def _html_to_text(html: str) -> str:
    """Basit bir fallback plain-text üretimi (HTML etiketlerini temizle)."""
    text = re.sub(r"<\s*br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"<\s*/p\s*>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()

# ──────────────────────────────────────────────────────────────
# 4) Arka planda gerçek gönderimler
# ──────────────────────────────────────────────────────────────
def _async_sendgrid(app, msg: SGMail) -> None:
    """SendGrid çağrısını app context’iyle çalıştır."""
    with app.app_context():
        try:
            sg_client = _get_sg_client()
            resp = sg_client.send(msg)
            app.logger.info("Mail OK (SendGrid) → %s (status %s)", msg.to, resp.status_code)
        except HTTPError as exc:
            body = exc.body.decode() if hasattr(exc.body, "decode") else exc.body
            app.logger.error("SendGrid %s | Body: %s", getattr(exc, "status_code", "?"), body)
        except Exception as exc:
            app.logger.error("SendGrid exception: %s", exc)

# --- DEĞİŞİKLİK 1: _async_brevo fonksiyonu artık 'brevo_config' parametresi alıyor ---
def _async_brevo(app, sender_addr: str, to: str, subject: str, html_body: str, text_body: str, brevo_config: dict) -> None:
    """Brevo SMTP ile gönderim. Ayarları parametre olarak alır."""
    # brevo_config = _get_brevo_config() <-- BU SATIR KALDIRILDI

    msg = EmailMessage()
    from_name = app.config.get("MAIL_FROM_NAME", "Apartman Yönetim Sistemi")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{sender_addr}>"
    msg["To"] = to
    msg.set_content(text_body or _html_to_text(html_body))
    msg.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    with app.app_context():
        try:
            with smtplib.SMTP(brevo_config["host"], brevo_config["port"], timeout=10) as server:
                server.starttls(context=context)
                server.login(brevo_config["login"], brevo_config["password"])
                server.send_message(msg)
            app.logger.info("Mail OK (Brevo) → %s", to)
        except Exception as exc:
            app.logger.error("Brevo SMTP exception: %s", exc)

# ──────────────────────────────────────────────────────────────
# 5) Dışa açık yardımcı
# ──────────────────────────────────────────────────────────────
def send_email(to: str, subject: str, template: str, **kwargs) -> None:
    """
    send_email("user@mail.com", "Hoş Geldiniz", "email/welcome", username="Okan")
    • `template`  ⇒  templates/<template>.html  (uzantı ekleme)
    • `kwargs`    ⇒  Jinja2 şablonuna parametre olarak geçilir
    KURAL: Microsoft domainleri → Brevo, diğerleri → SendGrid
    """
    app = current_app._get_current_object()
    debug_mode = app.config.get("MAIL_DEBUG_MODE") == "True"
    sender_raw = app.config.get("MAIL_DEFAULT_SENDER", "noreply@flatnetsite.com")
    sender_addr = sender_raw[-1] if isinstance(sender_raw, (tuple, list)) else sender_raw
    from_email = Email(sender_addr, name=app.config.get("MAIL_FROM_NAME", "Apartman Yönetim Sistemi"))
    html_body = render_template(f"{template}.html", **kwargs)
    text_body = _html_to_text(html_body)

    if debug_mode:
        print("── DEBUG MAIL ──")
        print("Konu     :", subject)
        print("Gönderen :", sender_addr)
        print("Alıcı    :", to)
        print("──────── HTML ───────────────")
        print(html_body)
        print("─────────────────────────────")
        return

    use_brevo = _is_ms(to) and _brevo_ready()
    if use_brevo:
        # --- DEĞİŞİKLİK 2: Brevo ayarlarını arka plana göndermeden ÖNCE alıyoruz ---
        brevo_cfg = _get_brevo_config()
        # Thread'e 'kwargs' olarak ayarları iletiyoruz.
        Thread(target=_async_brevo, args=(app, sender_addr, to, subject, html_body, text_body), kwargs={'brevo_config': brevo_cfg}, daemon=True).start()
        return

    msg = SGMail(
        from_email=from_email,
        to_emails=[to],
        subject=subject,
        html_content=html_body,
    )
    Thread(target=_async_sendgrid, args=(app, msg), daemon=True).start()