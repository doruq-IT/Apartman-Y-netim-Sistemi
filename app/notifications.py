# app/notifications.py

import firebase_admin
import requests
import time
from firebase_admin import credentials, messaging
from flask import current_app
# DEĞİŞİKLİK: Artık sadece PushToken modelini import ediyoruz
from .models import PushToken

# --- Huawei için yardımcı fonksiyonlar ve değişkenler ---
_hms_access_token = None
_hms_token_expiration = 0
HMS_TOKEN_URL = "https://oauth-login.cloud.huawei.com/oauth2/v2/token"
HMS_PUSH_URL_TEMPLATE = "https://push-api.cloud.huawei.com/v1/{app_id}/messages:send"
# -------------------------------------------------------------


def _get_hms_access_token():
    """Huawei Push Kit için geçerli bir Access Token alır."""
    global _hms_access_token, _hms_token_expiration
    if _hms_access_token and time.time() < _hms_token_expiration:
        return _hms_access_token

    app_id = current_app.config.get("HMS_APP_ID")
    app_secret = current_app.config.get("HMS_APP_SECRET")
    # --- YENİ EKLENEN KONTROL KODU ---
    print(f"!!! KONTROL: app/notifications.py içindeki HMS_APP_ID: {app_id}")
    if app_secret:
        print(f"!!! KONTROL: app/notifications.py içindeki HMS_APP_SECRET (ilk 5 karakter): {app_secret[:5]}...")
    else:
        print(f"!!! KONTROL: app/notifications.py içindeki HMS_APP_SECRET: {app_secret}")
    # --- KONTROL KODU SONU ---
    if not app_id or not app_secret:
        current_app.logger.error("HMS_APP_ID veya HMS_APP_SECRET yapılandırılmamış.")
        return None

    payload = {'grant_type': 'client_credentials', 'client_id': app_id, 'client_secret': app_secret}
    try:
        response = requests.post(HMS_TOKEN_URL, data=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        _hms_access_token = data['access_token']
        _hms_token_expiration = time.time() + int(data['expires_in']) - 60
        current_app.logger.info("Yeni HMS Access Token başarıyla alındı.")
        return _hms_access_token
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"HMS Access Token alınırken hata oluştu: {e}")
        return None


def _send_to_fcm(tokens, title, body, notification_type, item_id):
    """Belirtilen FCM token listesine bildirim gönderir."""
    if not tokens:
        return
    data_payload = {"type": notification_type, "id": str(item_id) if item_id is not None else ""}
    message = messaging.MulticastMessage(
        tokens=tokens,
        data=data_payload,
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        # Android için ses ve yüksek öncelik
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(sound="default")
        ),
        # iOS için ses
        apns=messaging.APNSConfig(
            headers={
                "apns-priority": "10",  # Anında teslimat için en yüksek öncelik
                "apns-push-type": "alert" # iOS 13+ için bunun bir kullanıcı uyarısı olduğunu belirtir
            },
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound="default")
            )
        )
    )
    try:
        # DEĞİŞİKLİK: send_multicast -> send_each_for_multicast (HTTP v1 uyumlu)
        response = messaging.send_each_for_multicast(message)
        current_app.logger.info(f"{response.success_count} adet FCM bildirimi başarıyla gönderildi.")
    except Exception as e:
        current_app.logger.error(f"FCM bildirimi gönderilirken hata oluştu: {e}")


def _send_to_hms(tokens, title, body, notification_type, item_id):
    """Belirtilen HMS token listesine bildirim gönderir."""
    if not tokens:
        return
    access_token = _get_hms_access_token()
    if not access_token:
        return

    app_id = current_app.config.get("HMS_APP_ID")
    push_url = HMS_PUSH_URL_TEMPLATE.format(app_id=app_id)
    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
    payload = {
        "validate_only": False,
        "message": {
            "notification": {"title": title, "body": body},
            "android": {
                "urgency": "HIGH",  # <-- YENİ EKLENEN "UYANDIRMA" AYARI
                "notification": {
                    "click_action": {"type": 3},
                    "sound": "/raw/default"
                }
            },
            "data": f'{{"type":"{notification_type}", "id":"{str(item_id) if item_id is not None else ""}"}}',
            "token": tokens
        }
    }
    try:
        response = requests.post(push_url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        current_app.logger.info(f"HMS bildirimi başarıyla gönderildi. Yanıt: {response.json()}")
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"HMS bildirimi gönderilirken hata oluştu: {e}")


def send_push_notification(user_id, title, body, notification_type, item_id=None):
    """
    [TEK KULLANICI] Belirtilen kullanıcıya, cihazının türüne göre bildirim gönderir.
    (Talep yanıtlama, makbuz onayı gibi tekil durumlar için kullanılır)
    """
    user_tokens = PushToken.query.filter_by(user_id=user_id).all()
    if not user_tokens:
        current_app.logger.warning(f"Kullanıcının (ID: {user_id}) push token'ı yok.")
        return

    fcm_tokens = [pt.token for pt in user_tokens if pt.service == 'fcm']
    hms_tokens = [pt.token for pt in user_tokens if pt.service == 'hms']
    
    _send_to_fcm(fcm_tokens, title, body, notification_type, item_id)
    _send_to_hms(hms_tokens, title, body, notification_type, item_id)


# ===== YENİ EKlenen OPTİMİZE EDİLMİŞ FONKSİYON =====
def send_notification_to_users(users, title, body, notification_type, item_id=None):
    """
    [ÇOKLU KULLANICI] Verilen kullanıcı listesine tek seferde bildirim gönderir.
    (Duyuru, anket gibi toplu durumlar için kullanılır)
    """
    if not users:
        return

    user_ids = [user.id for user in users]
    all_tokens = PushToken.query.filter(PushToken.user_id.in_(user_ids)).all()

    if not all_tokens:
        current_app.logger.warning("Toplu bildirim için hiçbir kullanıcıda push token'ı bulunamadı.")
        return

    fcm_tokens = [pt.token for pt in all_tokens if pt.service == 'fcm']
    hms_tokens = [pt.token for pt in all_tokens if pt.service == 'hms']

    current_app.logger.info(f"Toplu bildirim gönderiliyor: {len(fcm_tokens)} FCM, {len(hms_tokens)} HMS alıcısı.")

    _send_to_fcm(fcm_tokens, title, body, notification_type, item_id)
    _send_to_hms(hms_tokens, title, body, notification_type, item_id)
# ===== YENİ FONKSİYON SONU =====
