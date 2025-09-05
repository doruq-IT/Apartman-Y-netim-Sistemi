from app import create_app
import firebase_admin
from firebase_admin import credentials
import os
# --- YENİ EKLENEN IMPORT ---
from dotenv import load_dotenv

# --- .env DOSYASINI YÜKLE ---
# Bu komut, projenin kök dizinindeki .env dosyasını bulur ve
# içindeki değişkenleri ortam değişkeni olarak yükler.
load_dotenv()
# --- YÜKLEME SONU ---


# Flask uygulamasını oluştur
app = create_app()

# --- YENİ EKLENEN HMS AYARLARI ---
# Ortam değişkenlerinden okunan HMS ayarlarını Flask'ın config'ine yükle.
# Bu sayede uygulamanın her yerinden current_app.config ile erişilebilir.
app.config['HMS_APP_ID'] = os.environ.get('HMS_APP_ID')
app.config['HMS_APP_SECRET'] = os.environ.get('HMS_APP_SECRET')
# --- AYARLARIN SONU ---


# =================================================================
# FIREBASE BAŞLATMA KODU (Bu kısım aynı kalıyor)
# =================================================================
try:
    # Projenin ana dizinindeki anahtar dosyasının yolunu al
    key_path = os.path.join(os.path.dirname(__file__), 'firebase_credentials.json')
    
    # Kimlik bilgilerini bu dosyadan oku
    cred = credentials.Certificate(key_path)
    
    # Firebase uygulamasını bu kimlik bilgileriyle başlat
    # Zaten başlatılıp başlatılmadığını kontrol et
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK başarıyla başlatıldı.")
    else:
        print("Firebase Admin SDK zaten başlatılmış.")

except FileNotFoundError:
    print("Firebase servis anahtarı dosyası (firebase_credentials.json) bulunamadı. Bildirimler çalışmayacak.")
except Exception as e:
    print(f"Firebase Admin SDK başlatılırken hata oluştu: {e}")
# =================================================================
# KODUN SONU
# =================================================================


if __name__ == "__main__":
    app.run(debug=True)
